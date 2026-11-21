"""Tracker settings (TrackerSettings.kt in the Android app): the report intervals of firmware meshcore-tracker
are custom vars of the tracker, read and written over Bluetooth while its configuration window is open
(button held 2-6 s). Field table and rules are checked against shared/vectors.json ("trackerSettings")."""
from dataclasses import dataclass

AIR_PER_REPORT_S = 2.4   # 2 copies of ~1.2 s on air


@dataclass(frozen=True)
class Field:
    key: str
    label: str      # string id (strings.xml)
    unit: str       # "s" or "min"
    lo: int
    hi: int
    default: int
    trk8: bool = False   # only newer firmware has it (trk8: nap, beat; trk10: idle, home); missing = disabled


FIELDS = [
    Field("trk_fast", "ts_fast", "s", 15, 3600, 20),
    Field("trk_move", "ts_move", "s", 15, 3600, 30),
    Field("trk_still", "ts_still", "s", 15, 3600, 300),
    Field("trk_nap", "ts_nap", "min", 0, 1440, 60, trk8=True),
    Field("trk_beat", "ts_beat", "min", 15, 1440, 120, trk8=True),
    Field("trk_idle", "ts_idle", "min", 0, 1440, 15, trk8=True),
    Field("trk_home_r", "ts_home_r", "m", 30, 5000, 150, trk8=True),
]
BY_KEY = {f.key: f for f in FIELDS}


def clamp(key, value):
    f = BY_KEY[key]
    return max(f.lo, min(f.hi, int(value)))


def airtime_pct(interval_s):
    return round(AIR_PER_REPORT_S / interval_s * 100)


def parse_vars(text):
    """'k:v,k:v' as the companion sends custom vars"""
    out = {}
    for pair in text.split(","):
        k, sep, v = pair.partition(":")
        if sep and k:
            out[k] = v
    return out


def home_value(lat, lon):
    """trk_home for a position (trk10): only in the tracker, never in the repository"""
    return f"{lat:.6f} {lon:.6f}"


def is_tracker(vars_):
    return "tracker" in vars_ and "trk_move" in vars_
