"""Demo mode: a simulated walk (as in TrackService.kt), in the exact text format of the firmware,
so the demo exercises the real parser."""
import math

from .report import bearing, dist_m

NAME = "Demo"
LAT = 52.0756    # forest car park near Otwock, PL
LON = 21.3013
HISTORY = 60     # minutes of history (a report a minute) before the live reports
TICK_S = 5


def _resting(minute):
    return 20.0 <= math.fmod(minute, 45) <= 25.0   # fmod: the remainder of Kotlin's %, also below zero


def _pos(minute):
    """a wandering loop in a forest, about 1 km across; the dog rests for 5 minutes now and then"""
    phase = math.fmod(minute, 45)
    walked = minute - int(minute / 45) * 5 - (5.0 if phase > 25 else phase - 20 if phase > 20 else 0.0)
    a = walked * 0.085
    north = 420 * math.sin(a) + 130 * math.sin(3.1 * a) + 35 * math.sin(9.7 * a)
    east = 560 * (1 - math.cos(a)) + 150 * math.sin(2.3 * a) + 30 * math.cos(8.3 * a)
    return LAT + north / 111_320.0, LON + east / (111_320.0 * math.cos(math.radians(LAT)))


class Walk:
    def __init__(self, start_ms):
        self.start = start_ms
        self.seq = 0

    def history(self):
        """(text, time_s, snr) of the hour before the start"""
        return [self.report(self.start - (HISTORY - i) * 60_000) for i in range(HISTORY)]

    def report(self, time_ms):
        minute = HISTORY + (time_ms - self.start) / 60_000.0
        lat, lon = _pos(minute)
        p_lat, p_lon = _pos(minute - 0.25)
        kmh = dist_m(p_lat, p_lon, lat, lon) / 15.0 * 3.6
        resting = _resting(minute)
        self.seq += 1
        seq = self.seq
        status = "start" if seq == 1 else "stoi" if resting else "idzie"
        pct = int(97 - minute / 8)
        volt = f"{3.6 + pct * 0.006:.2f}V".replace(".", ",")
        speed = f"{0.0 if resting else kmh:.1f}km/h".replace(".", ",")
        course = f" k{int(bearing(p_lat, p_lon, lat, lon))}" if not resting and kmh >= 2 else ""
        act = 1 if resting else min(int(kmh * 4), 99)
        # like firmware trk9: battery, temperature and satellites in every 10th report only
        tele = f"{pct}% {volt} 8,5°C {9 + seq % 4}sat " if seq % 10 == 1 else ""
        # like trk10: HDOP, posture and minutes without motion (lying on its side while resting)
        extra = f" hdop1,1 bok bz{int(math.fmod(minute, 45) - 20)}" if resting else " hdop1,1 pion"
        text = (f"{NAME}: {status} {tele}{speed}{course} a{act}{extra} nr{seq} "
                f"https://maps.google.com/?q={lat:.5f},{lon:.5f}")
        return text, time_ms // 1000, -4.0 - seq % 7
