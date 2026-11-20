"""Tracker reports, the trail of a day and a little geometry.

The same rules as the Android app (app/src/main/java/pl/qbart/trackdog/Report.kt); both are checked
against the shared test vectors in shared/vectors.json, so change them together.
"""
import math
import re
from dataclasses import dataclass, field
from typing import Optional

ST_START = "start"
ST_MOVING = "idzie"
ST_STILL = "stoi"
ST_ASLEEP = "śpi"   # firmware trk8: still for an hour, GPS off, heartbeat only
ST_OK = "OK"
ST_SOS = "SOS"
ST_NO_GPS = "brak GPS"


@dataclass
class Report:
    """One report of a tracker, as posted on the MeshCore channel."""
    time: int                      # ms since epoch (clock of the tracker, set from GPS)
    tracker: str                   # node name of the tracker
    status: str                    # start, idzie, stoi, śpi, OK, SOS, brak GPS
    lat: Optional[float] = None
    lon: Optional[float] = None
    stale: bool = False            # the position is the last known one, not a fix of this report
    batt_pct: Optional[int] = None
    batt_mv: Optional[int] = None
    temp_c: Optional[float] = None
    sats: Optional[int] = None
    speed_kmh: Optional[float] = None   # GPS speed (firmware trk7+), else None
    course: Optional[int] = None        # degrees (trk7+, only when moving)
    activity: Optional[int] = None      # accelerometer, 0..99 (trk7+)
    seq: Optional[int] = None           # report counter of the tracker: gaps = lost reports
    low_batt: bool = False
    snr: Optional[float] = None         # of the packet, as heard by the companion
    id: int = field(default=0, compare=False)

    @property
    def has_fix(self):
        return self.lat is not None and self.lon is not None and not self.stale

    @property
    def has_pos(self):
        return self.lat is not None and self.lon is not None

    @property
    def sos(self):
        return self.status == ST_SOS

    @property
    def moving(self):
        return self.status == ST_MOVING


_STATUS = re.compile(r"^(start|idzie|stoi|śpi|OK|SOS|brak GPS)(?= |$)")
_SEQ = re.compile(r"(?:^| )nr(\d+)(?= |$)")
_PCT = re.compile(r"(?:^| )(\d{1,3})%")
_VOLT = re.compile(r"(?:^| )(\d+)[,.](\d+)V(?= |$)")
_TEMP = re.compile(r"(?:^| )(-?\d+(?:[,.]\d+)?)°C")
_SATS = re.compile(r"(?:^| )(\d+)sat(?= |$)")
_SPEED = re.compile(r"(?:^| )(\d+(?:[,.]\d+)?)km/h")
_COURSE = re.compile(r"(?:^| )k(\d{1,3})(?= |$)")
_ACT = re.compile(r"(?:^| )a(\d{1,2})(?= |$)")
_POS = re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)")


def _int(rx, body):
    m = rx.search(body)
    return int(m.group(1)) if m else None


def _num(rx, body):
    m = rx.search(body)
    return float(m.group(1).replace(",", ".")) if m else None


def parse(text, time_ms, snr=None):
    """Parses the text the tracker firmware posts (meshcore-tracker, TrackerMode.cpp), e.g.

        TRK1: idzie 93% 4,18V 9,3°C 12sat 5,4km/h k270 a12 nr81 https://maps.google.com/?q=52.22970,21.01220

    Every field but the status and the counter is optional. Anything else on the channel gives None.
    """
    cut = text.find(": ")
    if cut <= 0:
        return None
    tracker = text[:cut].strip()
    body = text[cut + 2:].strip()
    m = _STATUS.search(body)
    if not m:
        return None
    status = m.group(1)
    seq = _int(_SEQ, body)
    if seq is None:
        return None
    lat = lon = None
    pos = _POS.search(body)
    if pos:
        la, lo = float(pos.group(1)), float(pos.group(2))
        if -90 <= la <= 90 and -180 <= lo <= 180:
            lat, lon = la, lo
    volt = _VOLT.search(body)
    pct = _int(_PCT, body)
    course = _int(_COURSE, body)
    return Report(
        time=time_ms, tracker=tracker, status=status, lat=lat, lon=lon,
        stale=status == ST_NO_GPS or " ost. " in body,
        batt_pct=None if pct is None else max(0, min(100, pct)),
        batt_mv=round(float(f"{volt.group(1)}.{volt.group(2)}") * 1000) if volt else None,
        temp_c=_num(_TEMP, body), sats=_int(_SATS, body), speed_kmh=_num(_SPEED, body),
        course=course if course is not None and 0 <= course <= 359 else None,
        activity=_int(_ACT, body), seq=seq, low_batt="bateria!" in body, snr=snr,
    )


# ---------------------------------------------------------------------------------------------- geometry

_R = 6371000.0


def dist_m(lat1, lon1, lat2, lon2):
    k = math.pi / 180
    d_lat = (lat2 - lat1) * k
    d_lon = (lon2 - lon1) * k
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1 * k) * math.cos(lat2 * k) * math.sin(d_lon / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(max(0.0, min(1.0, h))))


def bearing(lat1, lon1, lat2, lon2):
    """initial bearing from point 1 to point 2, degrees 0..360"""
    k = math.pi / 180
    y = math.sin((lon2 - lon1) * k) * math.cos(lat2 * k)
    x = math.cos(lat1 * k) * math.sin(lat2 * k) - math.sin(lat1 * k) * math.cos(lat2 * k) * math.cos((lon2 - lon1) * k)
    return (math.atan2(y, x) / k + 360) % 360


def cardinal(deg):
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return names[int(((deg % 360 + 360) % 360 + 22.5) / 45) % 8]


# ---------------------------------------------------------------------------------------------- trail

MAX_GAP_MS = 15 * 60_000     # a gap longer than this is not one movement (tracker off, out of range)
NOISE_M = 40.0               # GPS noise while lying still must not add up to kilometres


class Point:
    __slots__ = ("r", "speed_kmh")

    def __init__(self, r, speed_kmh):
        self.r = r
        self.speed_kmh = speed_kmh


class Trail:
    """A day (or any stretch) of reports, turned into what the trail screen shows."""

    def __init__(self, reports):
        self.received = len(reports)
        fixes = sorted((r for r in reports if r.has_fix), key=lambda r: r.time)
        pts = []
        dist = 0.0
        moving = 0
        top = 0.0
        prev = None
        for r in fixes:
            speed = r.speed_kmh
            if prev is not None:
                d = dist_m(prev.lat, prev.lon, r.lat, r.lon)
                dt = r.time - prev.time
                joined = 1 <= dt <= MAX_GAP_MS
                if speed is None and joined and dt >= 15_000:
                    speed = d / (dt / 1000.0) * 3.6
                if joined and (r.moving or d > NOISE_M):
                    dist += d
                    moving += dt
            if speed is not None and top < speed < 80:
                top = speed
            pts.append(Point(r, speed))
            prev = r
        self.points = pts
        self.distance_m = dist
        self.moving_ms = moving
        self.max_kmh = top
        self.avg_moving_kmh = dist / (moving / 1000.0) * 3.6 if moving > 0 else 0.0

        # lost reports: gaps in the counter (it starts again from 1 when the tracker restarts)
        gaps = 0
        last = None
        for r in sorted(reports, key=lambda r: r.time):
            if r.seq is None:
                continue
            if last is not None and r.seq > last + 1 and r.seq - last < 500:
                gaps += r.seq - last - 1
            last = r.seq
        self.lost = gaps
