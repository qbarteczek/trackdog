package pl.qbart.trackdog

import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/** One report of a tracker, as posted on the MeshCore channel. */
data class Report(
    val time: Long,            // ms since epoch (clock of the tracker, set from GPS)
    val tracker: String,       // node name of the tracker
    val status: String,        // start, idzie, stoi, OK, SOS, brak GPS
    val lat: Double?,
    val lon: Double?,
    val stale: Boolean,        // the position is the last known one, not a fix of this report
    val battPct: Int?,
    val battMv: Int?,
    val tempC: Double?,
    val sats: Int?,
    val speedKmh: Double?,     // GPS speed (firmware trk7+), else null
    val course: Int?,          // degrees (trk7+, only when moving)
    val activity: Int?,        // accelerometer, 0..99 (trk7+)
    val seq: Int?,             // report counter of the tracker: gaps = lost reports
    val lowBatt: Boolean,
    val snr: Double? = null,   // of the packet, as heard by the companion
    val id: Long = 0,
) {
    val hasFix: Boolean get() = lat != null && lon != null && !stale
    val hasPos: Boolean get() = lat != null && lon != null
    val sos: Boolean get() = status == ST_SOS
    val moving: Boolean get() = status == ST_MOVING

    companion object {
        const val ST_START = "start"
        const val ST_MOVING = "idzie"
        const val ST_STILL = "stoi"
        const val ST_OK = "OK"
        const val ST_SOS = "SOS"
        const val ST_NO_GPS = "brak GPS"
    }
}

/**
 * Parses the text the tracker firmware posts (meshcore-tracker, TrackerMode.cpp), e.g.
 *
 *     TRK1: idzie 93% 4,18V 9,3°C 12sat 5,4km/h k270 a12 nr81 https://maps.google.com/?q=52.22970,21.01220
 *
 * Every field but the status and the counter is optional, so reports of older firmware (no speed) and of
 * a tracker without a fix ("brak GPS ... ost. https://...") parse too. Anything else on the channel
 * (people talking) gives null.
 */
object ReportParser {
    private val STATUS = Regex("^(start|idzie|stoi|OK|SOS|brak GPS)(?= |$)")
    private val SEQ = Regex("(?:^| )nr(\\d+)(?= |$)")
    private val PCT = Regex("(?:^| )(\\d{1,3})%")
    private val VOLT = Regex("(?:^| )(\\d+)[,.](\\d+)V(?= |$)")
    private val TEMP = Regex("(?:^| )(-?\\d+(?:[,.]\\d+)?)°C")
    private val SATS = Regex("(?:^| )(\\d+)sat(?= |$)")
    private val SPEED = Regex("(?:^| )(\\d+(?:[,.]\\d+)?)km/h")
    private val COURSE = Regex("(?:^| )k(\\d{1,3})(?= |$)")
    private val ACT = Regex("(?:^| )a(\\d{1,2})(?= |$)")
    private val POS = Regex("[?&]q=(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)")

    fun parse(text: String, timeMs: Long, snr: Double? = null): Report? {
        val cut = text.indexOf(": ")
        if (cut <= 0) return null
        val tracker = text.substring(0, cut).trim()
        val body = text.substring(cut + 2).trim()
        val status = STATUS.find(body)?.groupValues?.get(1) ?: return null
        val seq = SEQ.find(body)?.groupValues?.get(1)?.toIntOrNull() ?: return null
        val pos = POS.find(body)
        val lat = pos?.groupValues?.get(1)?.toDoubleOrNull()
        val lon = pos?.groupValues?.get(2)?.toDoubleOrNull()
        val okPos = lat != null && lon != null && lat in -90.0..90.0 && lon in -180.0..180.0
        val volt = VOLT.find(body)?.let { m ->
            ("${m.groupValues[1]}.${m.groupValues[2]}").toDoubleOrNull()?.let { (it * 1000).roundToInt() }
        }
        return Report(
            time = timeMs,
            tracker = tracker,
            status = status,
            lat = if (okPos) lat else null,
            lon = if (okPos) lon else null,
            stale = status == Report.ST_NO_GPS || body.contains(" ost. "),
            battPct = PCT.find(body)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(0, 100),
            battMv = volt,
            tempC = num(TEMP, body),
            sats = SATS.find(body)?.groupValues?.get(1)?.toIntOrNull(),
            speedKmh = num(SPEED, body),
            course = COURSE.find(body)?.groupValues?.get(1)?.toIntOrNull()?.takeIf { it in 0..359 },
            activity = ACT.find(body)?.groupValues?.get(1)?.toIntOrNull(),
            seq = seq,
            lowBatt = body.contains("bateria!"),
            snr = snr,
        )
    }

    private fun num(rx: Regex, body: String): Double? =
        rx.find(body)?.groupValues?.get(1)?.replace(',', '.')?.toDoubleOrNull()
}

object Geo {
    private const val R = 6371000.0

    fun distM(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val k = Math.PI / 180
        val dLat = (lat2 - lat1) * k
        val dLon = (lon2 - lon1) * k
        val h = sin(dLat / 2) * sin(dLat / 2) + cos(lat1 * k) * cos(lat2 * k) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * R * asin(sqrt(h.coerceIn(0.0, 1.0)))
    }

    /** initial bearing from point 1 to point 2, degrees 0..360 */
    fun bearing(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val k = Math.PI / 180
        val y = sin((lon2 - lon1) * k) * cos(lat2 * k)
        val x = cos(lat1 * k) * sin(lat2 * k) - sin(lat1 * k) * cos(lat2 * k) * cos((lon2 - lon1) * k)
        return (atan2(y, x) / k + 360) % 360
    }

    fun cardinal(deg: Double): String {
        val names = arrayOf("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        return names[(((deg % 360 + 360) % 360 + 22.5) / 45).toInt() % 8]
    }
}

/** A day (or any stretch) of reports, turned into what the trail screen shows. */
class Trail(reports: List<Report>) {
    class Point(val r: Report, val speedKmh: Double?)

    val points: List<Point>
    val distanceM: Double
    val movingMs: Long
    val maxKmh: Double
    val avgMovingKmh: Double
    val received: Int = reports.size
    val lost: Int

    init {
        val fixes = reports.filter { it.hasFix }.sortedBy { it.time }
        val pts = ArrayList<Point>(fixes.size)
        var dist = 0.0
        var moving = 0L
        var max = 0.0
        var prev: Report? = null
        for (r in fixes) {
            var speed = r.speedKmh
            val p = prev
            if (p != null) {
                val d = Geo.distM(p.lat!!, p.lon!!, r.lat!!, r.lon!!)
                val dt = r.time - p.time
                // a gap longer than this is not one movement (tracker off, out of range)
                val joined = dt in 1..MAX_GAP_MS
                if (speed == null && joined && dt >= 15_000) speed = d / (dt / 1000.0) * 3.6
                // GPS noise while lying still must not add up to kilometres
                if (joined && (r.moving || d > NOISE_M)) {
                    dist += d
                    moving += dt
                }
            }
            if (speed != null && speed > max && speed < 80) max = speed
            pts.add(Point(r, speed))
            prev = r
        }
        points = pts
        distanceM = dist
        movingMs = moving
        maxKmh = max
        avgMovingKmh = if (moving > 0) dist / (moving / 1000.0) * 3.6 else 0.0

        // lost reports: gaps in the counter (it starts again from 1 when the tracker restarts)
        var gaps = 0
        var last: Int? = null
        for (r in reports.sortedBy { it.time }) {
            val s = r.seq ?: continue
            val l = last
            if (l != null && s > l + 1 && s - l < 500) gaps += s - l - 1
            last = s
        }
        lost = gaps
    }

    companion object {
        const val MAX_GAP_MS = 15 * 60_000L
        const val NOISE_M = 40.0
    }
}
