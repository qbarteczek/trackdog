"""The desktop version against the shared test vectors (shared/vectors.json); the Android app runs the same ones.

    python -m unittest discover -s tests
"""
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("LANG", "en_US.UTF-8")

from tdd import fmt, gpx, i18n, report, trackerset  # noqa: E402

V = json.loads((HERE.parent.parent / "shared" / "vectors.json").read_text(encoding="utf-8"))
T0 = 1_800_000_000_000

# names of the fields in the vectors (as in Report.kt) -> attributes of the Python Report
FIELDS = {"battPct": "batt_pct", "battMv": "batt_mv", "tempC": "temp_c", "speedKmh": "speed_kmh",
          "lowBatt": "low_batt", "hasFix": "has_fix", "hasPos": "has_pos"}


def trail_reports(case):
    return [report.Report(time=T0 + int(r["min"] * 60_000), tracker="TRK1", status=r.get("status", "idzie"),
                          lat=r["lat"], lon=r.get("lon", 21.0), stale=r.get("stale", False), batt_pct=90,
                          batt_mv=4100, temp_c=10.0, sats=10, speed_kmh=r.get("speed"), seq=r["seq"])
            for r in case["reports"]]


class SharedVectors(unittest.TestCase):
    def test_parse(self):
        for case in V["parse"]:
            with self.subTest(case["name"]):
                r = report.parse(case["text"], T0, case.get("snr"))
                if case["expect"] is None:
                    self.assertIsNone(r)
                    continue
                self.assertIsNotNone(r)
                for k, want in case["expect"].items():
                    got = getattr(r, FIELDS.get(k, k))
                    if isinstance(want, float):
                        self.assertAlmostEqual(got, want, places=9, msg=k)
                    else:
                        self.assertEqual(got, want, k)

    def test_trail(self):
        for case in V["trail"]:
            with self.subTest(case["name"]):
                t = report.Trail(trail_reports(case))
                e = case["expect"]
                self.assertAlmostEqual(t.distance_m, e["distanceM"], delta=e["distanceTol"])
                self.assertEqual(t.moving_ms, e["movingMs"])
                self.assertAlmostEqual(t.max_kmh, e["maxKmh"], delta=e["maxTol"])
                if "avgMovingKmh" in e:
                    self.assertAlmostEqual(t.avg_moving_kmh, e["avgMovingKmh"], delta=e["maxTol"])
                self.assertEqual(t.lost, e["lost"])
                self.assertEqual(t.received, e["received"])
                self.assertEqual(len(t.points), e["points"])
                for p, want in zip(t.points, e["speeds"]):
                    if want is None:
                        self.assertIsNone(p.speed_kmh)
                    else:
                        self.assertAlmostEqual(p.speed_kmh, want, delta=0.05)

    def test_geo(self):
        g = V["geo"]
        for a, b, c, d, want in g["bearing"]:
            self.assertAlmostEqual(report.bearing(a, b, c, d), want, delta=g["bearingTol"])
        for a, b, c, d, want in g["dist"]:
            self.assertAlmostEqual(report.dist_m(a, b, c, d), want, delta=g["distTol"])
        for deg, want in g["cardinal"]:
            self.assertEqual(report.cardinal(deg), want)

    def test_format(self):
        i18n.set_lang("en")
        for m, want in V["format"]["dist"]:
            self.assertEqual(fmt.dist(m), want)
        for ms, want in V["format"]["duration"]:
            self.assertEqual(fmt.duration(ms), want)

    def test_gpx(self):
        g = V["gpx"]
        case = next(c for c in V["trail"] if c["name"] == g["trail"])
        self.assertEqual(gpx.gpx(g["name"], report.Trail(trail_reports(case)).points), g["expect"])


class DesktopOnly(unittest.TestCase):
    def test_gpx_round_trip(self):
        import tempfile
        case = V["trail"][0]
        pts = report.Trail(trail_reports(case)).points
        with tempfile.NamedTemporaryFile("w", suffix=".gpx", delete=False, encoding="utf-8") as f:
            f.write(gpx.gpx("trackdog-TRK1-2027-01-15", pts))
        found, reps = gpx.read_gpx(f.name)
        os.unlink(f.name)
        self.assertEqual(found, "TRK1")
        self.assertEqual([r.time for r in reps], [p.r.time for p in pts])
        self.assertAlmostEqual(reps[1].lat, pts[1].r.lat, places=6)

    def test_store_merge(self):
        import tempfile
        from tdd.store import Store
        d = Path(tempfile.mkdtemp())
        a, b = Store(d / "a.db"), Store(d / "b.db")
        reps = trail_reports(V["trail"][1])
        a.insert_many(reps[:4])
        b.insert_many(reps[2:])
        b.export_db(d / "export.db")
        self.assertEqual(a.merge_db(d / "export.db"), 2)
        self.assertEqual(a.count(), len(reps))
        self.assertFalse(a.insert(reps[0]))

    def test_android_strings(self):
        i18n.set_lang("pl")
        self.assertEqual(i18n.T("st_moving"), "idzie")
        self.assertEqual(i18n.T("age_h", 2, 5), "2 h 5 min temu")
        self.assertEqual(i18n.T("day_fmt", "pt., 14 lis", 10, 2), "pt., 14 lis · 10 meld. · 2 zgub.")
        i18n.set_lang("en")
        self.assertEqual(i18n.T("age_h", 2, 5), "2 h 5 min ago")

    def test_tracker_settings(self):
        ts = V["trackerSettings"]
        self.assertEqual([(f.key, f.unit, f.lo, f.hi, f.default) for f in trackerset.FIELDS],
                         [(f["key"], f["unit"], f["min"], f["max"], f["default"]) for f in ts["fields"]])
        for c in ts["clamp"]:
            self.assertEqual(trackerset.clamp(c["key"], c["in"]), c["out"], c)
        for c in ts["airtimePct"]:
            self.assertEqual(trackerset.airtime_pct(c["interval"]), c["pct"], c)
        got = trackerset.parse_vars(ts["parseVars"]["text"])
        for k, val in ts["parseVars"]["expect"].items():
            self.assertEqual(got[k], val, k)
        self.assertTrue(trackerset.is_tracker(got))
        i18n.set_lang("pl")
        self.assertEqual(i18n.T("st_asleep"), "śpi")
        self.assertEqual(i18n.T("ts_air", 12, 8)[:30], "Nadawanie: bieg 12%, spacer 8%")


if __name__ == "__main__":
    unittest.main()
