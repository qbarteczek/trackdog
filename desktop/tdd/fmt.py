"""Texts for people (Fmt in the Android app, Util.kt)."""
from . import i18n
from .i18n import T
from .report import ST_ASLEEP, ST_MOVING, ST_NO_GPS, ST_OK, ST_SOS, ST_START, ST_STILL

FAST_KMH = 7.0   # the same threshold as the firmware uses for its short interval


def _dec(s):
    return s.replace(".", ",") if i18n.lang() == "pl" else s


def status(r):
    if r.status == ST_START:
        return T("st_start")
    if r.status == ST_MOVING:
        return T("st_fast") if (r.speed_kmh or 0.0) >= FAST_KMH else T("st_moving")
    return T({ST_STILL: "st_still", ST_ASLEEP: "st_asleep", ST_OK: "st_ok", ST_SOS: "st_sos"}.get(r.status, "st_no_gps"))


def link(state):
    return T({"off": "link_off", "connecting": "link_connecting", "pairing": "link_pairing",
              "connected": "link_connected", "waiting": "link_waiting"}[state])


def age(ms):
    s = ms // 1000
    if s < 5:
        return T("age_now")
    if s < 90:
        return T("age_s", s)
    if s < 3600:
        return T("age_min", s // 60)
    if s < 48 * 3600:
        return T("age_h", s // 3600, s % 3600 // 60)
    return T("age_d", s // 86400)


def kmh(v):
    return _dec(f"{v:.1f} km/h")


def dist(m):
    if m < 1000:
        return f"{m:.0f} m"
    if m < 10_000:
        return _dec(f"{m / 1000:.2f} km")
    return _dec(f"{m / 1000:.1f} km")


def duration(ms):
    minutes = ms // 60_000
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h {minutes % 60} min"


def volts(mv):
    return _dec(f"{mv / 1000:.2f} V")


def num(v, digits=1):
    return _dec(f"{v:.{digits}f}")


__all__ = ["status", "link", "age", "kmh", "dist", "duration", "volts", "num", "FAST_KMH", "ST_NO_GPS"]
