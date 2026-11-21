"""Map with the trail: OpenStreetMap tiles, kept on disk so places seen once show without the internet.

Draws the trail coloured by speed like the Android app (grey: resting, gold: walking, red: running),
the dog, and the walker's own position.
"""
import math
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QMenu, QWidget

from . import theme
from .fmt import FAST_KMH
from .i18n import T
from .report import MAX_GAP_MS

TILE = 256
SOURCES = {
    "osm": ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19, "© OpenStreetMap"),
    "topo": ("OpenTopoMap", "https://a.tile.opentopomap.org/{z}/{x}/{y}.png", 17, "© OpenStreetMap, SRTM · OpenTopoMap"),
}
REFRESH_S = 30 * 86400         # tiles older than this are fetched again when online, but still shown
USER_AGENT = b"TrackDog-desktop (+https://github.com/qbarteczek/trackdog)"


def world_px(lat, lon, z):
    n = TILE * (1 << z)
    lat = max(-85.0511, min(85.0511, lat))
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def latlon(x, y, z):
    n = TILE * (1 << z)
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def speed_color(kmh):
    if kmh is None or kmh < 1.0:
        return theme.MUTED
    return theme.GOLD if kmh < FAST_KMH else theme.RED


class TileCache:
    def __init__(self, root):
        self.root = Path(root)
        self.mem = OrderedDict()
        self.pending = set()
        self.failed = {}                       # key -> time of the last failure (offline: do not hammer)
        self.net = QNetworkAccessManager()
        self.on_tile = None

    def path(self, src, z, x, y):
        return self.root / src / str(z) / str(x) / f"{y}.png"

    def get(self, src, z, x, y):
        key = (src, z, x, y)
        pm = self.mem.get(key)
        if pm is not None:
            self.mem.move_to_end(key)
            return pm
        p = self.path(src, z, x, y)
        if p.exists():
            pm = QPixmap(str(p))
            if not pm.isNull():
                self._keep(key, pm)
                if time.time() - p.stat().st_mtime > REFRESH_S:
                    self._fetch(key)
                return pm
        self._fetch(key)
        return None

    def cached(self, src, z, x, y):
        """only what is in memory or on disk, never the network (fallback tiles)"""
        key = (src, z, x, y)
        pm = self.mem.get(key)
        if pm is None and self.path(*key).exists():
            pm = QPixmap(str(self.path(*key)))
            if not pm.isNull():
                self._keep(key, pm)
        return pm

    def _keep(self, key, pm):
        self.mem[key] = pm
        while len(self.mem) > 600:
            self.mem.popitem(last=False)

    def _fetch(self, key):
        if key in self.pending or time.time() - self.failed.get(key, 0) < 60:
            return
        src, z, x, y = key
        req = QNetworkRequest(QUrl(SOURCES[src][1].format(z=z, x=x, y=y)))
        req.setRawHeader(QByteArray(b"User-Agent"), QByteArray(USER_AGENT))
        reply = self.net.get(req)
        self.pending.add(key)
        reply.finished.connect(lambda: self._done(key, reply))

    def _done(self, key, reply):
        self.pending.discard(key)
        data = bytes(reply.readAll())
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        reply.deleteLater()
        pm = QPixmap()
        if not ok or not pm.loadFromData(data):
            self.failed[key] = time.time()
            return
        p = self.path(*key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self._keep(key, pm)
        if self.on_tile:
            self.on_tile()

    def size_mb(self):
        if not self.root.exists():
            return 0
        return round(sum(f.stat().st_size for f in self.root.rglob("*.png")) / 1_000_000, 1)

    def clear(self):
        import shutil
        self.mem.clear()
        shutil.rmtree(self.root, ignore_errors=True)


class MapView(QWidget):
    me_set = Signal(object)    # (lat, lon) or None

    def __init__(self, tiles, parent=None):
        super().__init__(parent)
        self.tiles = tiles
        tiles.on_tile = self.update
        self.source = "osm"
        self.z = 15
        self.cx, self.cy = world_px(52.0756, 21.3013, self.z)   # centre in world pixels at zoom z
        self.points = []          # Trail points
        self.dog = None           # Report with a position
        self.dog_old = False      # the position is not fresh (stale or old)
        self.alarm = False
        self.me = None            # (lat, lon)
        self.empty_text = ""
        self._drag = None
        self._fitted_key = None
        self.setMouseTracking(True)
        self.setMinimumSize(240, 200)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    # ------------------------------------------------------------------ data

    def set_trail(self, points, key=None):
        self.points = points
        if key is not None and key != self._fitted_key:
            self._fitted_key = key
            self.fit()
        self.update()

    def set_dog(self, report, old=False, alarm=False):
        self.dog, self.dog_old, self.alarm = report, old, alarm
        self.update()

    def set_me(self, pos):
        self.me = pos
        self.update()

    def set_source(self, src):
        if src in SOURCES:
            self.source = src
            if self.z > SOURCES[src][2]:
                self.zoom_to(SOURCES[src][2])
            self.update()

    # ------------------------------------------------------------------ view

    def center_on(self, lat, lon, z=None):
        if z is not None:
            self.z = max(2, min(SOURCES[self.source][2], z))
        self.cx, self.cy = world_px(lat, lon, self.z)
        self.update()

    def zoom_to(self, z, anchor=None):
        z = max(2, min(SOURCES[self.source][2], z))
        if z == self.z:
            return
        ax, ay = anchor if anchor else (self.width() / 2, self.height() / 2)
        wx = self.cx + ax - self.width() / 2
        wy = self.cy + ay - self.height() / 2
        k = 2 ** (z - self.z)
        self.cx = wx * k - (ax - self.width() / 2)
        self.cy = wy * k - (ay - self.height() / 2)
        self.z = z
        self.update()

    def fit(self):
        pts = [(p.r.lat, p.r.lon) for p in self.points]
        if self.dog is not None and self.dog.has_pos:
            pts.append((self.dog.lat, self.dog.lon))
        if not pts:
            return
        w, h = max(self.width(), 300) - 60, max(self.height(), 240) - 60
        for z in range(SOURCES[self.source][2], 1, -1):
            xs, ys = zip(*(world_px(la, lo, z) for la, lo in pts))
            if max(xs) - min(xs) <= w and max(ys) - min(ys) <= h:
                break
        self.z = min(z, 17)
        xs, ys = zip(*(world_px(la, lo, self.z) for la, lo in pts))
        self.cx, self.cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        self.update()

    def screen(self, lat, lon):
        x, y = world_px(lat, lon, self.z)
        return QPointF(x - self.cx + self.width() / 2, y - self.cy + self.height() / 2)

    def at(self, sx, sy):
        return latlon(self.cx + sx - self.width() / 2, self.cy + sy - self.height() / 2, self.z)

    # ------------------------------------------------------------------ painting

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), theme.BG)
        self._paint_tiles(p)
        self._paint_trail(p)
        if self.me:
            self._paint_me(p)
        if self.dog is not None and self.dog.has_pos:
            self._paint_dog(p)
        if not self.points and not (self.dog and self.dog.has_pos) and self.empty_text:
            p.setPen(theme.CREAM)
            f = QFont(self.font())
            f.setPointSizeF(f.pointSizeF() * 1.2)
            p.setFont(f)
            r = QRectF(self.rect()).adjusted(20, 20, -20, -20)
            p.fillRect(QRectF(r.center().x() - 170, r.center().y() - 22, 340, 44), QColor(18, 36, 31, 210))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.empty_text)
        # credit, required by the tile servers
        p.setFont(QFont(self.font().family(), 8))
        credit = SOURCES[self.source][3]
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(credit) + 10
        box = QRectF(self.width() - w, self.height() - fm.height() - 4, w, fm.height() + 4)
        p.fillRect(box, QColor(255, 255, 255, 190))
        p.setPen(QColor(40, 40, 40))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, credit)
        p.end()

    def _paint_tiles(self, p):
        z = self.z
        n = 1 << z
        left = self.cx - self.width() / 2
        top = self.cy - self.height() / 2
        x0, x1 = int(left // TILE), int((left + self.width()) // TILE)
        y0, y1 = int(top // TILE), int((top + self.height()) // TILE)
        for ty in range(max(0, y0), min(n - 1, y1) + 1):
            for tx in range(x0, x1 + 1):
                wx = tx % n
                target = QRectF(tx * TILE - left, ty * TILE - top, TILE, TILE)
                pm = self.tiles.get(self.source, z, wx, ty)
                if pm is not None:
                    p.drawPixmap(target, pm, QRectF(0, 0, pm.width(), pm.height()))
                    continue
                # not here yet: a coarser tile from the disk, scaled up
                for up in range(1, 6):
                    pz = z - up
                    if pz < 0:
                        break
                    pp = self.tiles.cached(self.source, pz, wx >> up, ty >> up)
                    if pp is not None:
                        part = pp.width() / (1 << up)
                        src = QRectF((wx % (1 << up)) * part, (ty % (1 << up)) * part, part, part)
                        p.drawPixmap(target, pp, src)
                        break
        # the map is dimmed a little, so the trail stands out like on the phone
        p.fillRect(self.rect(), QColor(18, 36, 31, 40))

    def _paint_trail(self, p):
        pts = self.points
        if len(pts) < 2:
            return
        for i in range(1, len(pts)):
            a, b = pts[i - 1], pts[i]
            gap = b.r.time - a.r.time > MAX_GAP_MS
            pen = QPen(theme.LINE if gap else speed_color(b.speed_kmh), 2.5 if gap else 5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if gap:
                pen.setStyle(Qt.PenStyle.DashLine)
            # a dark edge under the colour keeps the line readable on a busy map
            if not gap:
                edge = QPen(QColor(18, 36, 31, 200), 8)
                edge.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(edge)
                p.drawLine(self.screen(a.r.lat, a.r.lon), self.screen(b.r.lat, b.r.lon))
            p.setPen(pen)
            p.drawLine(self.screen(a.r.lat, a.r.lon), self.screen(b.r.lat, b.r.lon))
        start = self.screen(pts[0].r.lat, pts[0].r.lon)
        p.setPen(QPen(theme.BG, 2))
        p.setBrush(theme.CREAM)
        p.drawEllipse(start, 5, 5)

    def _paint_me(self, p):
        c = self.screen(*self.me)
        p.setPen(QPen(QColor(255, 255, 255), 3))
        p.setBrush(theme.BLUE)
        p.drawEllipse(c, 8, 8)

    def _paint_dog(self, p):
        r = self.dog
        c = self.screen(r.lat, r.lon)
        color = theme.RED if self.alarm else theme.MUTED if self.dog_old else theme.GOLD
        if self.alarm:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(228, 87, 46, 70))
            p.drawEllipse(c, 30, 30)
        if r.course is not None and not self.dog_old:
            a = math.radians(r.course)
            tip = QPointF(c.x() + 26 * math.sin(a), c.y() - 26 * math.cos(a))
            l = QPointF(c.x() + 13 * math.sin(a - 0.5), c.y() - 13 * math.cos(a - 0.5))
            rr = QPointF(c.x() + 13 * math.sin(a + 0.5), c.y() - 13 * math.cos(a + 0.5))
            path = QPainterPath(tip)
            path.lineTo(l)
            path.lineTo(rr)
            path.closeSubpath()
            p.setPen(QPen(theme.BG, 1.5))
            p.setBrush(color)
            p.drawPath(path)
        p.setPen(QPen(theme.BG, 3))
        p.setBrush(color)
        p.drawEllipse(c, 12, 12)
        theme.draw_dog(p, c, 15, theme.BG)
        label = r.tracker
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(label) + 12
        box = QRectF(c.x() - w / 2, c.y() + 16, w, fm.height() + 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 36, 31, 220))
        p.drawRoundedRect(box, 4, 4)
        p.setPen(theme.CREAM)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = (ev.position(), self.cx, self.cy)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, ev):
        if self._drag:
            start, cx, cy = self._drag
            d = ev.position() - start
            self.cx, self.cy = cx - d.x(), cy - d.y()
            self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self.unsetCursor()

    def mouseDoubleClickEvent(self, ev):
        self.zoom_to(self.z + 1, (ev.position().x(), ev.position().y()))

    def wheelEvent(self, ev):
        step = 1 if ev.angleDelta().y() > 0 else -1
        self.zoom_to(self.z + step, (ev.position().x(), ev.position().y()))

    def contextMenuEvent(self, ev):
        lat, lon = self.at(ev.pos().x(), ev.pos().y())
        m = QMenu(self)
        here = QAction(T("me_here"), m)
        here.triggered.connect(lambda: self.me_set.emit((lat, lon)))
        m.addAction(here)
        if self.me:
            forget = QAction(T("me_clear"), m)
            forget.triggered.connect(lambda: self.me_set.emit(None))
            m.addAction(forget)
        m.addSeparator()
        if self.dog is not None and self.dog.has_pos:
            dog = QAction(T("map_center_dog"), m)
            dog.triggered.connect(lambda: self.center_on(self.dog.lat, self.dog.lon, max(self.z, 16)))
            m.addAction(dog)
        if self.points:
            fit = QAction(T("map_fit"), m)
            fit.triggered.connect(self.fit)
            m.addAction(fit)
        osm = QAction(T("map_open_osm"), m)
        osm.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(
            f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map={self.z}/{lat:.5f}/{lon:.5f}")))
        m.addAction(osm)
        m.exec(ev.globalPos())
