"""The trail: every report ever received, in SQLite.

The table is the same as in the Android app (Store.kt), so a database exported from the phone
can be merged in as it is.
"""
import sqlite3

from .report import Report

SCHEMA = """CREATE TABLE IF NOT EXISTS reports(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    t INTEGER NOT NULL, tracker TEXT NOT NULL, status TEXT NOT NULL,
    lat REAL, lon REAL, stale INTEGER NOT NULL,
    pct INTEGER, mv INTEGER, temp REAL, sats INTEGER,
    speed REAL, course INTEGER, act INTEGER, seq INTEGER,
    low INTEGER NOT NULL, snr REAL,
    UNIQUE(tracker, t))"""

COLS = "t, tracker, status, lat, lon, stale, pct, mv, temp, sats, speed, course, act, seq, low, snr"


def _row(r):
    return (r.time, r.tracker, r.status, r.lat, r.lon, int(r.stale), r.batt_pct, r.batt_mv, r.temp_c, r.sats,
            r.speed_kmh, r.course, r.activity, r.seq, int(r.low_batt), r.snr)


def _read(c):
    return Report(time=c["t"], tracker=c["tracker"], status=c["status"], lat=c["lat"], lon=c["lon"],
                  stale=bool(c["stale"]), batt_pct=c["pct"], batt_mv=c["mv"], temp_c=c["temp"], sats=c["sats"],
                  speed_kmh=c["speed"], course=c["course"], activity=c["act"], seq=c["seq"],
                  low_batt=bool(c["low"]), snr=c["snr"], id=c["id"])


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        self.db.execute("CREATE INDEX IF NOT EXISTS reports_t ON reports(t)")
        self.db.commit()

    def insert(self, r):
        """False = this report is already stored (the companion delivered it twice)"""
        cur = self.db.execute(f"INSERT OR IGNORE INTO reports({COLS}) VALUES ({','.join('?' * 16)})", _row(r))
        self.db.commit()
        return cur.rowcount > 0

    def insert_many(self, reports):
        """number of reports that were new"""
        before = self.count()
        self.db.executemany(f"INSERT OR IGNORE INTO reports({COLS}) VALUES ({','.join('?' * 16)})",
                            [_row(r) for r in reports])
        self.db.commit()
        return self.count() - before

    def merge_db(self, path):
        """Merges a TrackDog database (exported from the phone or another computer); number of new reports."""
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        try:
            rows = [_read(c) for c in src.execute("SELECT * FROM reports")]
        finally:
            src.close()
        return self.insert_many(rows)

    def export_db(self, path):
        """a standalone copy with the same table, for the phone or another computer"""
        out = sqlite3.connect(str(path))
        try:
            out.execute("DROP TABLE IF EXISTS reports")
            out.execute(SCHEMA)
            out.executemany(f"INSERT OR IGNORE INTO reports({COLS}) VALUES ({','.join('?' * 16)})",
                            [_row(r) for r in self._query(None, (), "t ASC", None)])
            out.commit()
        finally:
            out.close()

    def last(self, tracker):
        return next(iter(self._query(None if tracker is None else "tracker = ?",
                                     () if tracker is None else (tracker,), "t DESC", 1)), None)

    def last_fix(self, tracker):
        """the last report that carries a fresh fix"""
        where = "stale = 0 AND lat IS NOT NULL" + ("" if tracker is None else " AND tracker = ?")
        return next(iter(self._query(where, () if tracker is None else (tracker,), "t DESC", 1)), None)

    def between(self, tracker, from_ms, to_ms):
        where = "t >= ? AND t < ?" + ("" if tracker is None else " AND tracker = ?")
        args = (from_ms, to_ms) if tracker is None else (from_ms, to_ms, tracker)
        return self._query(where, args, "t ASC", None)

    def trackers(self):
        return [c[0] for c in self.db.execute("SELECT tracker FROM reports GROUP BY tracker ORDER BY MAX(t) DESC")]

    def days(self, tracker):
        """local days that have reports, oldest first, as "yyyy-MM-dd" """
        where = "" if tracker is None else " WHERE tracker = ?"
        return [c[0] for c in self.db.execute(
            f"SELECT DISTINCT date(t / 1000, 'unixepoch', 'localtime') FROM reports{where} ORDER BY 1",
            () if tracker is None else (tracker,))]

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    def clear(self):
        self.db.execute("DELETE FROM reports")
        self.db.commit()

    def delete_tracker(self, tracker):
        self.db.execute("DELETE FROM reports WHERE tracker = ?", (tracker,))
        self.db.commit()

    def _query(self, where, args, order, limit):
        sql = "SELECT * FROM reports" + (f" WHERE {where}" if where else "") + f" ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [_read(c) for c in self.db.execute(sql, args)]
