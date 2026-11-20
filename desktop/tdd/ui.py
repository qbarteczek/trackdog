"""Main window: Live, Trail and Device tabs (MainActivity.kt + TrackService.kt in the Android app)."""
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox, QStackedWidget, QSystemTrayIcon, QTabWidget,
                               QVBoxLayout, QWidget, QMenu)

from . import VERSION, demo, fmt, gpx, i18n, link as linkmod, theme, trackerset
from .i18n import T
from .mapview import SOURCES, MapView, TileCache
from .report import Trail, bearing, cardinal, dist_m, parse
from .store import Store
from .widgets import Compass, SpeedChart, Tile

MIN_TIME = 1_700_000_000_000   # 2023: older = the tracker has no time yet
FRESH_MS = 10 * 60_000
LIVE_HOURS = 3


def data_dir():
    d = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Config:
    DEFAULTS = {"device": None, "device_name": None, "tracker": None, "demo": False, "lang": None,
                "me": None, "me_radio": True, "tiles": "osm", "tray": True, "tracker_device": None}

    def __init__(self, path):
        self.path = path
        self.v = dict(self.DEFAULTS)
        try:
            self.v.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.v.get(k)

    def __setitem__(self, k, val):
        self.v[k] = val
        self.path.write_text(json.dumps(self.v, indent=1, ensure_ascii=False), encoding="utf-8")


class Bridge(QObject, linkmod.Listener):
    """the link calls from its own thread; signals carry the calls to the window's thread"""
    state = Signal(str, str)
    name = Signal(str)
    battery = Signal(int)
    position = Signal(float, float)
    text = Signal(str, object, object)

    def on_link_state(self, state, detail=""):
        self.state.emit(state, detail)

    def on_base_name(self, name):
        self.name.emit(name)

    def on_base_battery(self, millivolts):
        self.battery.emit(millivolts)

    def on_base_position(self, lat, lon):
        self.position.emit(lat, lon)

    def on_channel_text(self, text, sender_time, snr):
        self.text.emit(text, sender_time, snr)


def card(*widgets, margins=14):
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(margins, margins, margins, margins)
    for w in widgets:
        if isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return f


def muted(text=""):
    l = QLabel(text)
    l.setObjectName("muted")
    l.setWordWrap(True)
    return l


class MainWindow(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.data = data_dir()
        self.store = Store(self.data / "trackdog.db")
        self.tiles = TileCache(self.data / "tiles")
        self.bridge = Bridge()
        self.link = linkmod.Link(self.bridge)
        self.link_state = linkmod.OFF
        self.link_detail = ""
        self.base_name = cfg["device_name"]
        self.base_mv = None
        self.base_pos = None
        self.revision = 0
        self.walk = None
        self.quitting = False

        # what is on screen
        self.tracker = None
        self.last = None
        self.pos = None
        self.last_speed = None
        self.day = None
        self.days = []
        self.trail = None
        self.trail_key = ""

        self.setWindowTitle("TrackDog")
        self.setWindowIcon(theme.logo_icon())
        self.resize(1200, 780)
        self._build()
        self._tray()

        self.bridge.state.connect(self._on_state)
        self.bridge.name.connect(self._on_name)
        self.bridge.battery.connect(self._on_battery)
        self.bridge.position.connect(self._on_base_pos)
        self.bridge.text.connect(self.on_channel_text)

        self.ticker = QTimer(self)
        self.ticker.timeout.connect(self.live)
        self.ticker.start(1000)
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self._demo_tick)

        self.apply_service()
        self.tabs.setCurrentIndex(2 if cfg["device"] is None and not cfg["demo"] else 0)
        self.reload()

    # ------------------------------------------------------------------ layout

    def _build(self):
        root = QWidget()
        root.setObjectName("page")
        v = QVBoxLayout(root)
        v.setContentsMargins(16, 10, 16, 12)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(theme.logo_icon().pixmap(36, 36))
        head.addWidget(logo)
        self.head_tracker = QPushButton("")
        self.head_tracker.setFlat(True)
        self.head_tracker.setStyleSheet("font-size: 15pt; font-weight: 700; border: none; background: transparent;")
        self.head_tracker.clicked.connect(self.pick_tracker)
        head.addWidget(self.head_tracker)
        head.addStretch(1)
        self.head_link = QLabel()
        self.head_link.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(self.head_link)
        v.addLayout(head)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._live_page(), T("tab_live"))
        self.tabs.addTab(self._trail_page(), T("tab_trail"))
        self.tabs.addTab(self._device_page(), T("tab_device"))
        self.tabs.currentChanged.connect(self._tab)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(theme.STYLE)

    def _live_page(self):
        page = QWidget()
        page.setObjectName("page")
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 10, 0, 0)
        self.live_map = MapView(self.tiles)
        self.live_map.set_source(self.cfg["tiles"])
        self.live_map.empty_text = T("no_reports")
        self.live_map.me_set.connect(self._set_me)
        h.addWidget(self.live_map, 1)

        side = QVBoxLayout()
        side.setSpacing(10)
        self.compass = Compass()
        self.status_line = QLabel()
        self.status_line.setObjectName("head")
        self.status_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_line.setWordWrap(True)
        side.addWidget(card(self.compass, self.status_line))
        grid = QGridLayout()
        grid.setSpacing(8)
        self.t_speed, self.t_batt = Tile(T("lbl_speed")), Tile(T("lbl_battery"))
        self.t_gps, self.t_signal = Tile(T("lbl_gps")), Tile(T("lbl_signal"))
        for i, t in enumerate((self.t_speed, self.t_batt, self.t_gps, self.t_signal)):
            grid.addWidget(t, i // 2, i % 2)
        side.addLayout(grid)
        self.me_label = muted()
        row = QHBoxLayout()
        b_dog = QPushButton(T("map_center_dog"))
        b_dog.clicked.connect(self._center_dog)
        b_fit = QPushButton(T("map_fit"))
        b_fit.clicked.connect(self.live_map.fit)
        row.addWidget(b_dog)
        row.addWidget(b_fit)
        side.addLayout(row)
        side.addWidget(self.me_label)
        side.addStretch(1)
        box = QWidget()
        box.setLayout(side)
        box.setFixedWidth(330)
        h.addWidget(box)
        return page

    def _trail_page(self):
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 10, 0, 0)
        top = QHBoxLayout()
        self.day_prev = QPushButton("◀")
        self.day_prev.clicked.connect(lambda: self.step_day(-1))
        self.day_next = QPushButton("▶")
        self.day_next.clicked.connect(lambda: self.step_day(1))
        self.day_title = QLabel("—")
        self.day_title.setObjectName("head")
        self.day_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.day_prev)
        top.addWidget(self.day_title, 1)
        top.addWidget(self.day_next)
        v.addLayout(top)
        h = QHBoxLayout()
        left = QVBoxLayout()
        self.trail_map = MapView(self.tiles)
        self.trail_map.set_source(self.cfg["tiles"])
        self.trail_map.empty_text = T("no_trail")
        self.trail_map.me_set.connect(self._set_me)
        left.addWidget(self.trail_map, 1)
        self.chart = SpeedChart()
        left.addWidget(card(self.chart, margins=6))
        h.addLayout(left, 1)
        side = QVBoxLayout()
        self.t_dist, self.t_moving = Tile(T("lbl_distance")), Tile(T("lbl_moving"))
        self.t_avg, self.t_max = Tile(T("lbl_avg")), Tile(T("lbl_max"))
        for t in (self.t_dist, self.t_moving, self.t_avg, self.t_max):
            side.addWidget(t)
        b_fit = QPushButton(T("map_fit"))
        b_fit.clicked.connect(self.trail_map.fit)
        b_gpx = QPushButton(T("btn_gpx_export"))
        b_gpx.clicked.connect(self.save_gpx)
        side.addWidget(b_fit)
        side.addWidget(b_gpx)
        side.addStretch(1)
        box = QWidget()
        box.setLayout(side)
        box.setFixedWidth(240)
        h.addWidget(box)
        v.addLayout(h, 1)
        return page

    def _device_page(self):
        page = QWidget()
        page.setObjectName("page")
        inner = QWidget()
        inner.setObjectName("page")
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 10, 8, 10)
        v.setSpacing(12)

        # companion radio
        self.dev_name = QLabel()
        self.dev_name.setObjectName("head")
        self.dev_state = muted()
        b_pick = QPushButton(T("btn_pick_pc"))
        b_pick.setObjectName("primary")
        b_pick.clicked.connect(self.pick_radio)
        self.b_disconnect = QPushButton(T("btn_disconnect"))
        self.b_disconnect.clicked.connect(self.disconnect_radio)
        row = QHBoxLayout()
        row.addWidget(b_pick)
        row.addWidget(self.b_disconnect)
        row.addStretch(1)
        lbl = muted(T("lbl_link"))
        v.addWidget(card(lbl, self.dev_name, self.dev_state, row))

        # tracker, demo, stored reports
        self.dev_tracker = QPushButton()
        self.dev_tracker.clicked.connect(self.pick_tracker)
        self.sw_demo = QCheckBox(T("demo_switch"))
        self.sw_demo.setChecked(bool(self.cfg["demo"]))
        self.sw_demo.toggled.connect(self._toggle_demo)
        self.dev_stored = muted()
        b_import = QPushButton(T("btn_import"))
        b_import.clicked.connect(self.import_file)
        b_export = QPushButton(T("btn_export_pc"))
        b_export.clicked.connect(self.export_db)
        b_clear = QPushButton(T("btn_clear"))
        b_clear.setObjectName("danger")
        b_clear.clicked.connect(self.clear_data)
        r1 = QHBoxLayout()
        r1.addWidget(muted(T("lbl_tracker")))
        r1.addWidget(self.dev_tracker, 1)
        r2 = QHBoxLayout()
        for b in (b_import, b_export, b_clear):
            r2.addWidget(b)
        r2.addStretch(1)
        v.addWidget(card(r1, self.sw_demo, self.dev_stored, muted(T("import_hint")), r2))

        # the tracker itself: report intervals over Bluetooth
        b_ts = QPushButton(T("btn_tracker_settings"))
        b_ts.clicked.connect(self.tracker_settings)
        r_ts = QHBoxLayout()
        r_ts.addWidget(b_ts)
        r_ts.addStretch(1)
        v.addWidget(card(muted(T("ts_title")), muted(T("ts_open_hint")), r_ts))

        # map
        self.map_src = QComboBox()
        for key, (name, *_rest) in SOURCES.items():
            self.map_src.addItem(name, key)
        self.map_src.setCurrentIndex(max(0, self.map_src.findData(self.cfg["tiles"])))
        self.map_src.currentIndexChanged.connect(self._map_source)
        self.map_cache = muted()
        b_tiles = QPushButton(T("map_cache_clear"))
        b_tiles.clicked.connect(self._clear_tiles)
        r3 = QHBoxLayout()
        r3.addWidget(muted(T("map_source")))
        r3.addWidget(self.map_src, 1)
        r4 = QHBoxLayout()
        r4.addWidget(self.map_cache, 1)
        r4.addWidget(b_tiles)
        v.addWidget(card(r3, muted(T("map_offline_note")), r4))

        # program
        self.lang_box = QComboBox()
        self.lang_box.addItem("Polski", "pl")
        self.lang_box.addItem("English", "en")
        self.lang_box.setCurrentIndex(0 if i18n.lang() == "pl" else 1)
        self.lang_box.currentIndexChanged.connect(self._lang)
        self.sw_tray = QCheckBox(T("lbl_tray"))
        self.sw_tray.setChecked(bool(self.cfg["tray"]))
        self.sw_tray.toggled.connect(lambda on: self.cfg.__setitem__("tray", on))
        r5 = QHBoxLayout()
        r5.addWidget(muted(T("lbl_language")))
        r5.addWidget(self.lang_box, 1)
        ver = muted(T("version_fmt", VERSION) + " · " + T("data_dir", str(self.data)))
        ver.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(card(r5, self.sw_tray, muted(T("info_desktop")), ver))
        v.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)
        return page

    def _tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(theme.logo_icon(), self)
        m = QMenu()
        show = QAction(T("tray_show"), m)
        show.triggered.connect(self._show)
        quit_ = QAction(T("tray_quit"), m)
        quit_.triggered.connect(self.quit)
        m.addAction(show)
        m.addAction(quit_)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda reason: self._show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.setToolTip("TrackDog")
        self.tray.show()

    def _tab(self, i):
        if i == 1:
            self.load_trail()
            self.live()
        elif i == 2:
            self.map_cache.setText(T("map_cache", self.tiles.size_mb()))

    def _show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, ev):
        if not self.quitting and self.tray is not None and self.cfg["tray"]:
            ev.ignore()
            self.hide()
            if not self.cfg["tray_told"]:
                self.tray.showMessage("TrackDog", T("tray_still"), theme.logo_icon(), 4000)
                self.cfg["tray_told"] = True
            return
        self.quit()

    def quit(self):
        self.quitting = True
        self.link.stop()
        QApplication.quit()

    # ------------------------------------------------------------------ link, demo

    def apply_service(self):
        """listen whenever there is something to listen to"""
        self.demo_timer.stop()
        self.walk = None
        if self.cfg["demo"]:
            self.link.stop()
            self.store.delete_tracker(demo.NAME)
            self.walk = demo.Walk(int(time.time() * 1000))
            for text, t, snr in self.walk.history():
                self.on_channel_text(text, t, snr, quiet=True)
            self.demo_timer.start(demo.TICK_S * 1000)
        elif self.cfg["device"]:
            self.link.start(self.cfg["device"])
        else:
            self.link.stop()
        self.reload()

    def _demo_tick(self):
        if self.walk:
            text, t, snr = self.walk.report(int(time.time() * 1000))
            self.on_channel_text(text, t, snr)

    def _on_state(self, state, detail):
        self.link_state = state
        self.link_detail = detail
        if state != linkmod.CONNECTED:
            self.base_mv = None
        self.reload()

    def _on_name(self, name):
        self.base_name = name
        self.cfg["device_name"] = name
        self.reload()

    def _on_battery(self, mv):
        self.base_mv = mv
        self.reload()

    def _on_base_pos(self, lat, lon):
        self.base_pos = (lat, lon)
        self.reload()

    def on_channel_text(self, text, sender_time, snr, quiet=False):
        now = int(time.time() * 1000)
        # the tracker stamps reports with GPS time; believe it unless it is clearly off
        t = sender_time * 1000
        when = t if MIN_TIME <= t <= now + 10 * 60_000 else now
        r = parse(text, when, snr)
        if r is None or not self.store.insert(r):
            return
        self.revision += 1
        chosen = self.cfg["tracker"]
        if not quiet and (chosen is None or chosen == r.tracker or self.cfg["demo"]):
            shown = self.last if self.last and self.last.tracker == r.tracker else None
            fresh = now - r.time < FRESH_MS
            if fresh and r.sos:
                self.alarm(T("notif_sos", r.tracker))
            if fresh and r.low_batt and not (shown and shown.low_batt):
                self.alarm(T("notif_low", r.tracker))
        self.reload()

    def alarm(self, text):
        QApplication.beep()
        QApplication.alert(self, 0)
        if self.tray is not None:
            self.tray.showMessage("TrackDog", text, QSystemTrayIcon.MessageIcon.Critical, 30_000)

    # ------------------------------------------------------------------ data -> screen

    def me(self):
        """(lat, lon, source) of the walker: the radio's own position, or one set by hand on the map"""
        if self.cfg["me_radio"] and self.base_pos:
            return self.base_pos[0], self.base_pos[1], T("me_radio")
        m = self.cfg["me"]
        if m:
            return m[0], m[1], T("me_manual")
        return None

    def reload(self):
        trackers = self.store.trackers()
        chosen = self.cfg["tracker"]
        self.tracker = demo.NAME if self.cfg["demo"] else chosen if chosen in trackers else (trackers[0] if trackers else None)
        self.last = self.store.last(self.tracker) if self.tracker else None
        self.pos = self.last if self.last and self.last.has_pos else (self.store.last_fix(self.tracker) if self.tracker else None)
        self.last_speed = None
        l = self.last
        if l:
            # older firmware sends no speed: take it from the last two fixes
            self.last_speed = l.speed_kmh
            if self.last_speed is None:
                pts = Trail(self.store.between(self.tracker, l.time - 10 * 60_000, l.time + 1)).points
                if pts and pts[-1].r.time == l.time:
                    self.last_speed = pts[-1].speed_kmh

        self.head_tracker.setText(self.tracker or "TrackDog")
        self.t_speed.set(fmt.kmh(self.last_speed) if self.last_speed is not None else "—")
        if l is None or l.batt_pct is None:
            self.t_batt.set("—")
        else:
            self.t_batt.set(f"{l.batt_pct}% · {fmt.volts(l.batt_mv)}" if l.batt_mv else f"{l.batt_pct}%")
        if l is None:
            self.t_gps.set("—")
        elif not l.has_fix:
            self.t_gps.set(T("st_no_gps"))
        else:
            self.t_gps.set(T("satellites", l.sats or 0) + (f" · {l.temp_c:.0f}°C" if l.temp_c is not None else ""))
        self.t_signal.set(f"SNR {fmt.num(l.snr)} dB" if l and l.snr is not None else "—")

        # link chip and device page
        st = self.link_state
        is_demo = self.cfg["demo"]
        dev = self.cfg["device"]
        color = theme.GREEN if is_demo or st == linkmod.CONNECTED else theme.MUTED if st == linkmod.OFF else theme.GOLD
        if is_demo:
            link_text = T("link_demo")
        elif not dev:
            link_text = T("link_none")
        elif st == linkmod.CONNECTED:
            link_text = self.base_name or fmt.link(st)
        else:
            link_text = fmt.link(st)
        self.head_link.setText(f'<span style="color:{color.name()}">●</span> {link_text}')
        self.head_link.setToolTip(T("link_not_seen") if self.link_detail == linkmod.NOT_SEEN and st == linkmod.WAITING
                                  else "")
        self.dev_name.setText(T("link_demo") if is_demo else T("link_none") if not dev
                              else self.base_name or dev.get("address"))
        state = ""
        if dev and not is_demo:
            state = fmt.link(st) + (f" · {fmt.volts(self.base_mv)}" if self.base_mv else "")
            state += f" · {dev['kind'].upper()} {dev['address']}"
            if st == linkmod.WAITING and self.link_detail:
                state += "\n" + (T("link_not_seen") if self.link_detail == linkmod.NOT_SEEN
                                  else T("conn_error", self.link_detail))
        self.dev_state.setText(state)
        self.b_disconnect.setEnabled(bool(dev))
        self.dev_tracker.setText(self.tracker or "—")
        self.dev_stored.setText(T("stored_fmt", self.store.count()))
        if self.sw_demo.isChecked() != bool(is_demo):
            self.sw_demo.blockSignals(True)
            self.sw_demo.setChecked(bool(is_demo))
            self.sw_demo.blockSignals(False)

        # live map: the last hours of the trail
        now = int(time.time() * 1000)
        recent = self.store.between(self.tracker, now - LIVE_HOURS * 3600_000, now + 3600_000) if self.tracker else []
        self.live_map.set_trail(Trail(recent).points, key=self.tracker)
        if self.tabs.currentIndex() == 1:
            self.load_trail()
        self.live()

    def live(self):
        """everything that changes with time alone: age of the report, distance, direction"""
        l = self.last
        now = int(time.time() * 1000)
        self.status_line.setText(T("no_reports") if l is None else f"{fmt.status(l)} · {fmt.age(now - l.time)}")
        p = self.pos
        me = self.me()
        alarm = l is not None and l.sos and now - l.time < 15 * 60_000
        old = p is not None and (p is not l or p.stale or now - p.time > FRESH_MS)
        self.live_map.set_dog(p, old, alarm)
        self.trail_map.set_dog(p if self.day == date.today().isoformat() else None, old, alarm)
        self.live_map.set_me(me[:2] if me else None)
        self.trail_map.set_me(me[:2] if me else None)
        if p is None:
            self.compass.set(None, "—", T("no_reports") if l is None else T("no_dog_pos"), alarm)
        elif me is None:
            self.compass.set(None, "—", T("me_none"), alarm)
        else:
            b = bearing(me[0], me[1], p.lat, p.lon)
            d = fmt.dist(dist_m(me[0], me[1], p.lat, p.lon))
            sub = (T("last_known") + " · " + fmt.age(now - p.time)) if old else f"{cardinal(b)} · {int(b)}°"
            self.compass.set(b, d, sub, alarm)
        self.me_label.setText(T("lbl_me") + ": " + (me[2] if me else T("me_none")))

    # ------------------------------------------------------------------ trail page

    def load_trail(self):
        self.days = self.store.days(self.tracker) if self.tracker else []
        if self.day is None or self.day not in self.days:
            self.day = self.days[-1] if self.days else None
        d = self.day
        key = f"{self.tracker}|{d}|{self.revision}"
        if key != self.trail_key:
            self.trail_key = key
            reports = []
            if d:
                start = datetime.combine(date.fromisoformat(d), datetime.min.time())
                end = start + timedelta(days=1)
                reports = self.store.between(self.tracker, int(start.timestamp() * 1000), int(end.timestamp() * 1000))
            t = Trail(reports)
            self.trail = t
            self.trail_map.set_trail(t.points, key=f"{self.tracker}|{d}")
            self.chart.set(t.points)
            if d:
                label = QLocale_day(date.fromisoformat(d))
                self.day_title.setText(T("day_fmt", label, t.received, t.lost))
            else:
                self.day_title.setText("—")
            self.t_dist.set(fmt.dist(t.distance_m))
            self.t_moving.set(fmt.duration(t.moving_ms))
            self.t_avg.set(fmt.kmh(t.avg_moving_kmh))
            self.t_max.set(fmt.kmh(t.max_kmh))
        i = self.days.index(d) if d in self.days else -1
        self.day_prev.setEnabled(i > 0)
        self.day_next.setEnabled(0 <= i < len(self.days) - 1)

    def step_day(self, step):
        if self.day in self.days:
            i = self.days.index(self.day) + step
            if 0 <= i < len(self.days):
                self.day = self.days[i]
                self.load_trail()
                self.live()

    def save_gpx(self):
        if not self.trail or not self.trail.points:
            QMessageBox.information(self, "TrackDog", T("gpx_empty"))
            return
        name = f"trackdog-{self.tracker or 'trail'}-{self.day or ''}"
        start = str(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)) / f"{name}.gpx")
        path, _ = QFileDialog.getSaveFileName(self, T("btn_gpx_export"), start, "GPX (*.gpx)")
        if not path:
            return
        try:
            Path(path).write_text(gpx.gpx(name, self.trail.points), encoding="utf-8")
        except OSError:
            QMessageBox.warning(self, "TrackDog", T("gpx_failed"))

    # ------------------------------------------------------------------ actions

    def _set_me(self, pos):
        self.cfg["me"] = list(pos) if pos else None
        # a position set by hand wins over the radio's until it is forgotten
        self.cfg["me_radio"] = pos is None
        self.live()

    def _center_dog(self):
        if self.pos is not None:
            self.live_map.center_on(self.pos.lat, self.pos.lon, max(self.live_map.z, 16))

    def pick_tracker(self):
        trackers = self.store.trackers()
        if not trackers:
            return
        items = [T("tracker_auto")] + trackers
        cur = items.index(self.cfg["tracker"]) if self.cfg["tracker"] in trackers else 0
        item, ok = QInputDialog.getItem(self, "TrackDog", T("lbl_tracker"), items, cur, False)
        if ok:
            self.cfg["tracker"] = None if item == items[0] else item
            self.trail_key = ""
            self.reload()

    def pick_radio(self):
        dlg = ConnectDialog(self, self.link, self.cfg["device"])
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.device:
            self.cfg["device"] = dlg.device
            self.cfg["device_name"] = dlg.device_name
            self.base_name = dlg.device_name
            self.base_pos = None
            if self.cfg["demo"]:
                self.cfg["demo"] = False
                self.store.delete_tracker(demo.NAME)
            self.apply_service()

    def tracker_settings(self):
        dlg = ConnectDialog(self, self.link, self.cfg["tracker_device"], title=T("ts_title"))
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.device:
            self.cfg["tracker_device"] = dlg.device
            TrackerSettingsDialog(self, self.link, dlg.device, dlg.device_name).exec()

    def disconnect_radio(self):
        self.cfg["device"] = None
        self.cfg["device_name"] = None
        self.base_name = None
        self.base_pos = None
        self.apply_service()

    def _toggle_demo(self, on):
        self.cfg["demo"] = on
        if not on:
            self.store.delete_tracker(demo.NAME)
            self.revision += 1
        self.trail_key = ""
        self.apply_service()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, T("btn_import"), "",
                                              "TrackDog (*.db *.sqlite *.gpx);;SQLite (*.db *.sqlite);;GPX (*.gpx)")
        if not path:
            return
        try:
            if path.lower().endswith(".gpx"):
                found, reports = gpx.read_gpx(path)
                who = found
                if not who:
                    who, ok = QInputDialog.getText(self, "TrackDog", T("import_gpx_tracker"), text=self.tracker or "")
                    if not ok or not who.strip():
                        return
                    for r in reports:
                        r.tracker = who.strip()
                total = len(reports)
                new = self.store.insert_many(reports)
            else:
                import sqlite3
                src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                total = src.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
                src.close()
                new = self.store.merge_db(path)
        except Exception as e:  # noqa: BLE001  (not our file, broken file)
            logging.getLogger("trackdog").warning("import %s: %r", path, e)
            QMessageBox.warning(self, "TrackDog", T("import_bad") + f"\n\n{e}")
            return
        self.revision += 1
        self.trail_key = ""
        self.reload()
        QMessageBox.information(self, "TrackDog", T("import_done", new, total))

    def export_db(self):
        name = f"trackdog-{date.today().isoformat()}.db"
        start = str(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)) / name)
        path, _ = QFileDialog.getSaveFileName(self, T("btn_export_pc"), start, "SQLite (*.db)")
        if path:
            self.store.export_db(path)
            QMessageBox.information(self, "TrackDog", T("export_done_pc", path))

    def clear_data(self):
        if confirm(self, T("clear_confirm_pc"), T("yes")):
            self.store.clear()
            self.revision += 1
            self.trail_key = ""
            self.reload()

    def _map_source(self):
        src = self.map_src.currentData()
        self.cfg["tiles"] = src
        self.live_map.set_source(src)
        self.trail_map.set_source(src)

    def _clear_tiles(self):
        self.tiles.clear()
        self._tab(2)

    def _lang(self):
        self.cfg["lang"] = self.lang_box.currentData()
        QMessageBox.information(self, "TrackDog", T("restart_lang"))


def QLocale_day(d):
    """'pt., 14 lis' / 'Fri, 14 Nov' in the program's language"""
    from PySide6.QtCore import QDate, QLocale
    loc = QLocale(QLocale.Language.Polish if i18n.lang() == "pl" else QLocale.Language.English)
    return loc.toString(QDate(d.year, d.month, d.day), "ddd, d MMM")


def confirm(parent, text, yes):
    box = QMessageBox(parent)
    box.setWindowTitle("TrackDog")
    box.setText(text)
    ok = box.addButton(yes, QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(T("no"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is ok


class ConnectDialog(QDialog):
    """Bluetooth (search), USB cable (port list) or TCP (host:port)."""
    scanned = Signal(object)

    def __init__(self, parent, link, current, title=None):
        super().__init__(parent)
        self.link = link
        self.device = None
        self.device_name = None
        self.setWindowTitle(title or T("conn_title"))
        self.resize(520, 460)
        v = QVBoxLayout(self)
        kinds = QHBoxLayout()
        self.group = QButtonGroup(self)
        self.stack = QStackedWidget()
        for i, (key, label) in enumerate((("ble", "conn_ble"), ("serial", "conn_serial"), ("tcp", "conn_tcp"))):
            rb = QRadioButton(T(label))
            self.group.addButton(rb, i)
            kinds.addWidget(rb)
        kinds.addStretch(1)
        v.addLayout(kinds)

        # Bluetooth
        ble = QWidget()
        bv = QVBoxLayout(ble)
        bv.setContentsMargins(0, 0, 0, 0)
        self.ble_list = QListWidget()
        self.ble_status = muted(T("scan_hint"))
        self.b_scan = QPushButton(T("conn_scan"))
        self.b_scan.clicked.connect(self.scan)
        self.pin = QLineEdit((current or {}).get("pin") or "123456")
        self.pin.setMaximumWidth(120)
        row = QHBoxLayout()
        row.addWidget(self.b_scan)
        row.addStretch(1)
        row.addWidget(QLabel(T("conn_pin")))
        row.addWidget(self.pin)
        bv.addLayout(row)
        bv.addWidget(self.ble_list, 1)
        bv.addWidget(self.ble_status)
        bv.addWidget(muted(T("conn_one_link")))
        if sys.platform.startswith("linux"):
            bv.addWidget(muted(T("conn_linux_pair")))
        self.stack.addWidget(ble)

        # USB
        usb = QWidget()
        uv = QVBoxLayout(usb)
        uv.setContentsMargins(0, 0, 0, 0)
        self.port_list = QListWidget()
        b_refresh = QPushButton(T("conn_refresh"))
        b_refresh.clicked.connect(self.refresh_ports)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("conn_port")))
        row.addStretch(1)
        row.addWidget(b_refresh)
        uv.addLayout(row)
        uv.addWidget(self.port_list, 1)
        self.stack.addWidget(usb)

        # TCP
        tcp = QWidget()
        tv = QVBoxLayout(tcp)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(QLabel(T("conn_host")))
        self.host = QLineEdit((current or {}).get("address", "") if (current or {}).get("kind") == "tcp" else "")
        self.host.setPlaceholderText("192.168.1.50:5000")
        tv.addWidget(self.host)
        tv.addStretch(1)
        self.stack.addWidget(tcp)

        v.addWidget(self.stack, 1)
        buttons = QDialogButtonBox()
        ok = buttons.addButton(T("conn_connect"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        buttons.addButton(T("no"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

        self.group.idToggled.connect(lambda i, on: self.stack.setCurrentIndex(i) if on else None)
        start = {"ble": 0, "serial": 1, "tcp": 2}.get((current or {}).get("kind"), 0)
        self.group.button(start).setChecked(True)
        self.stack.setCurrentIndex(start)
        self.scanned.connect(self._scanned)
        self.refresh_ports()
        if start == 0:
            QTimer.singleShot(100, self.scan)

    def scan(self):
        self.b_scan.setEnabled(False)
        self.ble_status.setText(T("conn_scanning"))
        self.ble_list.clear()
        import asyncio
        async def both():
            return await linkmod.paired_radios(), await linkmod.ble_scan(8)
        fut = asyncio.run_coroutine_threadsafe(both(), self.link.loop)
        fut.add_done_callback(lambda f: self.scanned.emit(f))

    def _scanned(self, fut):
        self.b_scan.setEnabled(True)
        try:
            paired, (found, heard) = fut.result()
        except Exception as e:  # noqa: BLE001  (no adapter, Bluetooth off)
            self.ble_status.setText(T("conn_error", e))
            return
        seen = {addr for _, addr, _ in found}
        for name, addr, rssi in found:
            it = QListWidgetItem(f"{name}    {addr}    {rssi} dBm")
            it.setData(Qt.ItemDataRole.UserRole, (name, addr))
            self.ble_list.addItem(it)
        # radios paired before are listed even when they do not advertise now (switched off, or busy with the phone)
        for name, addr in paired:
            if addr not in seen:
                it = QListWidgetItem(f"{name}{T('paired_suffix')}    {addr}")
                it.setData(Qt.ItemDataRole.UserRole, (name, addr))
                self.ble_list.addItem(it)
        if self.ble_list.count():
            self.ble_list.setCurrentRow(0)
        if heard == 0:
            self.ble_status.setText(T("scan_nothing"))
        elif not found:
            self.ble_status.setText(T("conn_none_found") + (" " + T("conn_paired_wait") if paired else ""))
        else:
            self.ble_status.setText(T("scan_hint"))

    def refresh_ports(self):
        self.port_list.clear()
        try:
            ports = linkmod.serial_ports()
        except Exception:  # noqa: BLE001
            ports = []
        for dev, desc in ports:
            it = QListWidgetItem(f"{dev}    {desc}")
            it.setData(Qt.ItemDataRole.UserRole, dev)
            self.port_list.addItem(it)
        if ports:
            self.port_list.setCurrentRow(0)

    def _accept(self):
        kind = self.group.checkedId()
        if kind == 0 and self.ble_list.currentItem():
            name, addr = self.ble_list.currentItem().data(Qt.ItemDataRole.UserRole)
            self.device = {"kind": "ble", "address": addr, "pin": self.pin.text().strip() or "123456"}
            self.device_name = name
        elif kind == 1 and self.port_list.currentItem():
            port = self.port_list.currentItem().data(Qt.ItemDataRole.UserRole)
            self.device = {"kind": "serial", "address": port}
            self.device_name = None
        elif kind == 2 and self.host.text().strip():
            self.device = {"kind": "tcp", "address": self.host.text().strip()}
            self.device_name = None
        else:
            return
        self.accept()


class TrackerSettingsDialog(QDialog):
    """Report intervals of the tracker (TrackerSettings.kt): read when opened, changed fields written on save."""
    done_ = Signal(object, object)

    def __init__(self, parent, link, device, name):
        super().__init__(parent)
        self.link = link
        self.device = device
        self.vars = {}
        self.setWindowTitle(T("ts_title") + (f" – {name}" if name else ""))
        self.resize(460, 0)
        v = QVBoxLayout(self)
        self.status = muted(T("ts_connecting"))
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        form = QFormLayout()
        self.boxes = {}
        for f in trackerset.FIELDS:
            box = QSpinBox()
            box.setRange(f.lo, f.hi)
            box.setValue(f.default)
            box.setSuffix(" " + T("ts_unit_" + f.unit))
            box.setEnabled(False)
            box.valueChanged.connect(self._air)
            self.boxes[f.key] = box
            form.addRow(T(f.label), box)
        v.addLayout(form)
        v.addWidget(muted(T("ts_nap_hint")))
        self.air = muted()
        self.air.setWordWrap(True)
        v.addWidget(self.air)
        buttons = QDialogButtonBox()
        self.b_save = buttons.addButton(T("ts_save"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_save.setObjectName("primary")
        self.b_save.setEnabled(False)
        buttons.addButton(T("no"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)
        self.done_.connect(self._done)
        self._air()
        self._call(None)

    def _call(self, changes):
        fut = self.link.submit(linkmod.tracker_settings(self.device, changes))
        fut.add_done_callback(lambda f: self.done_.emit(f, changes))

    def _air(self):
        self.air.setText(T("ts_air", trackerset.airtime_pct(self.boxes["trk_fast"].value()),
                           trackerset.airtime_pct(self.boxes["trk_move"].value())))

    def _done(self, fut, changes):
        try:
            vars_ = fut.result()
        except Exception as e:  # noqa: BLE001  (window closed, out of range, refused)
            logging.getLogger("trackdog").info("tracker settings: %r", e)
            self.status.setText(T("ts_save_failed" if changes else "ts_failed"))
            self.b_save.setEnabled(bool(self.vars))
            return
        if not trackerset.is_tracker(vars_):
            self.status.setText(T("ts_not_tracker"))
            return
        self.vars = vars_
        old = False
        for f in trackerset.FIELDS:
            box = self.boxes[f.key]
            if f.key in vars_:
                box.setValue(trackerset.clamp(f.key, vars_[f.key]))
                box.setEnabled(True)
            else:
                box.setEnabled(False)
                old = True
        self.b_save.setEnabled(True)
        self.status.setText(((T("ts_saved") if changes else "") + (" " + T("ts_old_fw") if old else "")).strip())

    def _save(self):
        changes = {k: box.value() for k, box in self.boxes.items()
                   if box.isEnabled() and str(box.value()) != self.vars.get(k)}
        if not changes:
            self.accept()
            return
        self.b_save.setEnabled(False)
        self.status.setText(T("ts_saving"))
        self._call(changes)

