"""Main screen rules (Panel.kt in the Android app), checked against shared/vectors.json ("panel").

Battery, temperature and satellites come from the last report that has them: firmware trk9 sends them in
every 10th report only. The data is live when the radio is connected and the last report is fresh; SNR
belongs to live reception, so it is not shown for old data.
"""
from dataclasses import dataclass

FRESH_MS = 10 * 60_000


@dataclass
class Model:
    live: bool
    snr: float | None
    batt: object        # Report with the battery, or None
    batt_age: int | None    # ms; None = the battery is from the last report itself
    temp: object
    temp_age: int | None
    sats: object
    sats_age: int | None


def _age(rep, last, now):
    return None if rep is None or rep.time == last.time else now - rep.time


def build(last, batt, temp, sats, link_up, now):
    if last is None:
        return Model(False, None, None, None, None, None, None, None)
    live = bool(link_up) and now - last.time < FRESH_MS
    return Model(live, last.snr if live else None, batt, _age(batt, last, now), temp, _age(temp, last, now),
                 sats, _age(sats, last, now))
