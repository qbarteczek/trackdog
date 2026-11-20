"""Texts in English and Polish.

The texts both versions show (statuses, ages, labels, alarms) are read from the Android app's
strings.xml, so a fix of a text there reaches the desktop too. Texts of the desktop alone are in DESKTOP.
"""
import locale
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
# the repository first: the bundled copy left behind by build.py would hide newer texts when run from source
_CANDIDATES = [HERE.parent.parent / "app" / "src" / "main" / "res",  # in the repository
               HERE / "res"]                                         # bundled copy (PyInstaller, build.py)

# key: (English, Polish)
DESKTOP = {
    "tab_live": ("Live", "Na żywo"),
    "btn_pick_pc": ("Choose the companion radio…", "Wybierz radio…"),
    "lbl_me": ("My position", "Moja pozycja"),
    "lbl_status": ("Status", "Stan"),
    "lbl_age": ("Report", "Meldunek"),
    "lbl_direction": ("Direction", "Kierunek"),
    "me_none": ("set on the map (right click)", "ustaw na mapie (prawy przycisk)"),
    "me_radio": ("from the radio", "z radia"),
    "me_manual": ("set by hand", "ustawiona ręcznie"),
    "me_here": ("I am here", "Tu jestem"),
    "me_clear": ("Forget my position", "Zapomnij moją pozycję"),
    "me_use_radio": ("Use the position of the radio", "Pozycja z radia"),
    "map_center_dog": ("Centre on the dog", "Pokaż psa"),
    "map_fit": ("Whole trail", "Cały ślad"),
    "map_open_osm": ("Open in the browser (OpenStreetMap)", "Otwórz w przeglądarce (OpenStreetMap)"),
    "map_source": ("Map", "Mapa"),
    "map_cache": ("Map tiles on disk: %1$s MB", "Kafelki mapy na dysku: %1$s MB"),
    "map_cache_clear": ("Delete the map tiles", "Usuń kafelki mapy"),
    "map_offline_note": ("Map tiles you have seen are kept on disk, so these places show without the internet too.",
                         "Obejrzane kafelki mapy zostają na dysku, więc te miejsca widać też bez internetu."),
    "map_credit": ("© OpenStreetMap contributors", "© autorzy OpenStreetMap"),
    "trail_hours": ("last %1$d h", "ostatnie %1$d h"),
    "btn_gpx_export": ("Save the trail as GPX…", "Zapisz ślad jako GPX…"),
    "btn_day_prev": ("◀", "◀"),
    "btn_day_next": ("▶", "▶"),
    "btn_import": ("Import from the phone…", "Import z telefonu…"),
    "btn_export_pc": ("Export the reports (for the phone)…", "Eksportuj meldunki (na telefon)…"),
    "import_hint": ("A database exported from TrackDog (Device → Export the reports), or a GPX file. "
                    "Reports already stored are skipped.",
                    "Baza wyeksportowana z TrackDog (Urządzenie → Eksportuj meldunki) albo plik GPX. "
                    "Meldunki, które już są, zostają pominięte."),
    "import_gpx_tracker": ("Name of the tracker for this GPX trail:", "Nazwa trackera dla tego śladu GPX:"),
    "export_done_pc": ("Saved %1$s", "Zapisano %1$s"),
    "conn_title": ("Connect to the companion radio", "Połączenie z radiem"),
    "conn_ble": ("Bluetooth", "Bluetooth"),
    "conn_serial": ("USB cable", "Kabel USB"),
    "conn_tcp": ("Wi-Fi (TCP)", "Wi-Fi (TCP)"),
    "conn_scan": ("Search", "Szukaj"),
    "conn_scanning": ("Searching for MeshCore radios…", "Szukam radiów MeshCore…"),
    "conn_none_found": ("No MeshCore radio is advertising. Is it on, near and not connected to the phone?",
                        "Żadne radio MeshCore się nie ogłasza. Czy jest włączone, blisko i niepołączone z telefonem?"),
    "conn_paired_wait": ("A paired radio can be chosen anyway: TrackDog connects as soon as it is on and free.",
                         "Sparowane radio można wybrać mimo to: TrackDog połączy się, gdy tylko będzie włączone i wolne."),
    "link_not_seen": ("The radio is not advertising: it is off, out of range or connected to another device (the phone). "
                      "TrackDog connects as soon as it is free.",
                      "Radio się nie ogłasza: jest wyłączone, za daleko albo połączone z innym urządzeniem (telefonem). "
                      "TrackDog połączy się, gdy tylko będzie wolne."),
    "conn_pin": ("PIN", "PIN"),
    "conn_port": ("Port", "Port"),
    "conn_host": ("Address (host:port)", "Adres (host:port)"),
    "conn_refresh": ("Refresh", "Odśwież"),
    "conn_connect": ("Connect", "Połącz"),
    "conn_one_link": ("A radio talks to one device at a time: disconnect the phone from it first.",
                      "Radio rozmawia naraz tylko z jednym urządzeniem: najpierw odłącz od niego telefon."),
    "conn_linux_pair": ("On Linux pair the radio once: bluetoothctl → pair ADDRESS, then enter the PIN shown on the radio "
                        "(default 123456).",
                        "Na Linuksie sparuj radio raz: bluetoothctl → pair ADRES, potem PIN z ekranu radia "
                        "(domyślnie 123456)."),
    "conn_error": ("Connection failed: %1$s", "Nie udało się połączyć: %1$s"),
    "lbl_language": ("Language", "Język"),
    "lbl_tray": ("Keep listening in the tray when the window is closed",
                 "Po zamknięciu okna słuchaj dalej (ikona przy zegarze)"),
    "tray_show": ("Show TrackDog", "Pokaż TrackDog"),
    "tray_quit": ("Quit", "Zakończ"),
    "tray_still": ("TrackDog keeps listening here.", "TrackDog słucha dalej tutaj."),
    "restart_lang": ("The language changes after a restart.", "Język zmieni się po ponownym uruchomieniu."),
    "info_desktop": ("TrackDog for the computer listens to the same tracker reports as the phone: it connects to a MeshCore "
                     "companion radio by Bluetooth, USB cable or Wi-Fi, takes every report out of the radio at once and "
                     "stores the trail on the computer. It never transmits over LoRa. The map tiles come from "
                     "OpenStreetMap and stay on disk.",
                     "TrackDog na komputer słucha tych samych meldunków trackera co telefon: łączy się z radiem MeshCore "
                     "(companion) przez Bluetooth, kabel USB albo Wi-Fi, od razu zabiera z niego każdy meldunek i zapisuje "
                     "ślad na komputerze. Niczego nie nadaje przez LoRa. Kafelki mapy pochodzą z OpenStreetMap i zostają "
                     "na dysku."),
    "data_dir": ("Data folder: %1$s", "Folder danych: %1$s"),
    "clear_confirm_pc": ("Delete all stored reports from this computer?", "Usunąć wszystkie meldunki z tego komputera?"),
}

_lang = "en"
_android = {}


def system_lang():
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return "pl" if v.lower().startswith("pl") else "en"
    try:
        loc = locale.getlocale()[0] or ""
        if sys.platform == "win32":
            import ctypes
            loc = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), loc)
    except Exception:  # noqa: BLE001
        loc = ""
    return "pl" if loc.lower().startswith("pl") else "en"


def _load_xml(path):
    out = {}
    if not path.exists():
        return out
    for el in ET.parse(path).getroot().iter("string"):
        text = "".join(el.itertext())
        text = text.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
        out[el.get("name")] = text
    return out


def set_lang(lang):
    global _lang, _android
    _lang = "pl" if lang == "pl" else "en"
    for base in _CANDIDATES:
        if (base / "values" / "strings.xml").exists():
            _android = _load_xml(base / "values" / "strings.xml")
            if _lang == "pl":
                _android.update(_load_xml(base / "values-pl" / "strings.xml"))
            break


def lang():
    return _lang


_FMT = re.compile(r"%(?:(\d+)\$)?([ds%])")


def _format(s, args):
    """Android format strings (%d, %s, %1$d, %%) with the given arguments"""
    seq = iter(range(len(args)))

    def sub(m):
        if m.group(2) == "%":
            return "%"
        i = int(m.group(1)) - 1 if m.group(1) else next(seq)
        return str(args[i])
    return _FMT.sub(sub, s)


def T(key, *args):
    if key in DESKTOP:
        s = DESKTOP[key][1 if _lang == "pl" else 0]
    else:
        s = _android.get(key, key)
    return _format(s, args) if args else s.replace("%%", "%")


set_lang(system_lang())
