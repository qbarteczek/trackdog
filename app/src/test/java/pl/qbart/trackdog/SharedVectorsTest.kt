package pl.qbart.trackdog

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File
import java.util.Locale

/** The Android app against the shared test vectors (shared/vectors.json); the desktop version runs the same ones. */
class SharedVectorsTest {
    private val t0 = 1_800_000_000_000L
    private val v = JSONObject(
        listOf(File("../shared/vectors.json"), File("shared/vectors.json")).first { it.exists() }.readText()
    )

    private fun JSONObject.optDoubleOrNull(k: String): Double? = if (isNull(k)) null else getDouble(k)

    private fun field(r: Report, k: String): Any? = when (k) {
        "tracker" -> r.tracker
        "status" -> r.status
        "lat" -> r.lat
        "lon" -> r.lon
        "stale" -> r.stale
        "battPct" -> r.battPct
        "battMv" -> r.battMv
        "tempC" -> r.tempC
        "sats" -> r.sats
        "speedKmh" -> r.speedKmh
        "course" -> r.course
        "activity" -> r.activity
        "seq" -> r.seq
        "lowBatt" -> r.lowBatt
        "snr" -> r.snr
        "hasFix" -> r.hasFix
        "hasPos" -> r.hasPos
        "sos" -> r.sos
        "alarm" -> r.alarm
        "hdop" -> r.hdop
        "posture" -> r.posture
        "idleMin" -> r.idleMin
        else -> throw AssertionError("unknown field $k")
    }

    private fun trailReports(case: JSONObject): List<Report> {
        val rs = case.getJSONArray("reports")
        return (0 until rs.length()).map { i ->
            val r = rs.getJSONObject(i)
            Report(
                time = t0 + (r.getDouble("min") * 60_000).toLong(), tracker = "TRK1",
                status = r.optString("status", "idzie"), lat = r.getDouble("lat"), lon = r.optDouble("lon", 21.0),
                stale = r.optBoolean("stale", false), battPct = 90, battMv = 4100, tempC = 10.0, sats = 10,
                speedKmh = if (r.has("speed")) r.getDouble("speed") else null, course = null, activity = null,
                seq = r.getInt("seq"), lowBatt = false,
            )
        }
    }

    @Test
    fun parse() {
        val cases = v.getJSONArray("parse")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val name = c.getString("name")
            val r = ReportParser.parse(c.getString("text"), t0, c.optDoubleOrNull("snr"))
            if (c.isNull("expect")) {
                assertNull(name, r)
                continue
            }
            assertNotNull(name, r)
            val e = c.getJSONObject("expect")
            for (k in e.keys()) {
                val got = field(r!!, k)
                when {
                    e.isNull(k) -> assertNull("$name: $k", got)
                    e.get(k) is Boolean || e.get(k) is String -> assertEquals("$name: $k", e.get(k), got)
                    got is Int -> assertEquals("$name: $k", e.getInt(k), got)
                    else -> assertEquals("$name: $k", e.getDouble(k), (got as Number).toDouble(), 1e-9)
                }
            }
        }
    }

    @Test
    fun trail() {
        val cases = v.getJSONArray("trail")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val name = c.getString("name")
            val t = Trail(trailReports(c))
            val e = c.getJSONObject("expect")
            assertEquals(name, e.getDouble("distanceM"), t.distanceM, e.getDouble("distanceTol"))
            assertEquals(name, e.getLong("movingMs"), t.movingMs)
            assertEquals(name, e.getDouble("maxKmh"), t.maxKmh, e.getDouble("maxTol"))
            if (e.has("avgMovingKmh")) assertEquals(name, e.getDouble("avgMovingKmh"), t.avgMovingKmh, e.getDouble("maxTol"))
            assertEquals(name, e.getInt("lost"), t.lost)
            assertEquals(name, e.getInt("received"), t.received)
            assertEquals(name, e.getInt("points"), t.points.size)
            val speeds = e.getJSONArray("speeds")
            for (j in 0 until speeds.length()) {
                if (speeds.isNull(j)) assertNull("$name: speed $j", t.points[j].speedKmh)
                else assertEquals("$name: speed $j", speeds.getDouble(j), t.points[j].speedKmh!!, 0.05)
            }
        }
    }

    @Test
    fun geo() {
        val g = v.getJSONObject("geo")
        fun rows(k: String): List<JSONArray> = g.getJSONArray(k).let { a -> (0 until a.length()).map { a.getJSONArray(it) } }
        for (r in rows("bearing")) {
            assertEquals(r.getDouble(4), Geo.bearing(r.getDouble(0), r.getDouble(1), r.getDouble(2), r.getDouble(3)), g.getDouble("bearingTol"))
        }
        for (r in rows("dist")) {
            assertEquals(r.getDouble(4), Geo.distM(r.getDouble(0), r.getDouble(1), r.getDouble(2), r.getDouble(3)), g.getDouble("distTol"))
        }
        for (r in rows("cardinal")) assertEquals(r.getString(1), Geo.cardinal(r.getDouble(0)))
    }

    @Test
    fun format() {
        val before = Locale.getDefault()
        Locale.setDefault(Locale.US)
        try {
            val f = v.getJSONObject("format")
            val dist = f.getJSONArray("dist")
            for (i in 0 until dist.length()) {
                assertEquals(dist.getJSONArray(i).getString(1), Fmt.dist(dist.getJSONArray(i).getDouble(0)))
            }
            val dur = f.getJSONArray("duration")
            for (i in 0 until dur.length()) {
                assertEquals(dur.getJSONArray(i).getString(1), Fmt.duration(dur.getJSONArray(i).getLong(0)))
            }
        } finally {
            Locale.setDefault(before)
        }
    }

    @Test
    fun gpx() {
        val g = v.getJSONObject("gpx")
        val cases = v.getJSONArray("trail")
        val case = (0 until cases.length()).map { cases.getJSONObject(it) }.first { it.getString("name") == g.getString("trail") }
        assertEquals(g.getString("expect"), Maps.gpx(g.getString("name"), Trail(trailReports(case)).points))
    }

    @Test
    fun trackerSettings() {
        val ts = v.getJSONObject("trackerSettings")
        val fields = ts.getJSONArray("fields")
        assertEquals(fields.length(), TrackerSettings.FIELDS.size)
        TrackerSettings.FIELDS.forEachIndexed { i, f ->
            val e = fields.getJSONObject(i)
            assertEquals(e.getString("key"), f.key)
            assertEquals(e.getString("unit"), f.unit)
            assertEquals(e.getInt("min"), f.min)
            assertEquals(e.getInt("max"), f.max)
            assertEquals(e.getInt("default"), f.default)
        }
        val clamp = ts.getJSONArray("clamp")
        for (i in 0 until clamp.length()) {
            val c = clamp.getJSONObject(i)
            assertEquals(c.toString(), c.getInt("out"), TrackerSettings.clamp(c.getString("key"), c.getInt("in")))
        }
        val air = ts.getJSONArray("airtimePct")
        for (i in 0 until air.length()) {
            val c = air.getJSONObject(i)
            assertEquals(c.toString(), c.getInt("pct"), TrackerSettings.airtimePct(c.getInt("interval")))
        }
        val pv = ts.getJSONObject("parseVars")
        val got = TrackerSettings.parseVars(pv.getString("text"))
        val exp = pv.getJSONObject("expect")
        for (k in exp.keys()) assertEquals(k, exp.getString(k), got[k])
        assertEquals(true, TrackerSettings.isTracker(got))
        val hv = ts.getJSONObject("homeValue")
        assertEquals(hv.getString("expect"), TrackerSettings.homeValue(hv.getDouble("lat"), hv.getDouble("lon")))
    }

    @Test
    fun panel() {
        val pv = v.getJSONObject("panel")
        assertEquals(pv.getInt("freshMin") * 60_000L, Panel.FRESH_MS)
        val now = t0 + 3_600_000
        fun rep(o: JSONObject, k: String): Report? = if (o.isNull(k)) null else Report(
            time = now - o.getInt(k) * 60_000L, tracker = "TRK1", status = "idzie", lat = 52.0, lon = 21.0, stale = false,
            battPct = 90, battMv = 4100, tempC = 10.0, sats = 9, speedKmh = null, course = null, activity = null,
            seq = 1, lowBatt = false, snr = -5.0)
        val cases = pv.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val e = c.getJSONObject("expect")
            val m = Panel.build(rep(c, "last"), rep(c, "batt"), rep(c, "temp"), rep(c, "sats"), c.getBoolean("link"), now)
            val name = c.getString("name")
            assertEquals(name, e.getBoolean("live"), m.live)
            assertEquals(name, e.getBoolean("snr"), m.snr != null)
            for ((k, got) in listOf("battAge" to m.battAge, "tempAge" to m.tempAge, "satsAge" to m.satsAge)) {
                assertEquals("$name $k", if (e.isNull(k)) null else e.getInt(k).toLong(), got?.div(60_000))
            }
        }
    }
}
