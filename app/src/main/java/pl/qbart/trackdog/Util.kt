package pl.qbart.trackdog

import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Texts for people. */
object Fmt {
    const val FAST_KMH = 7.0   // the same threshold as the firmware uses for its short interval

    fun status(ctx: Context, r: Report): String = ctx.getString(
        when (r.status) {
            Report.ST_START -> R.string.st_start
            Report.ST_MOVING -> if ((r.speedKmh ?: 0.0) >= FAST_KMH) R.string.st_fast else R.string.st_moving
            Report.ST_STILL -> R.string.st_still
            Report.ST_OK -> R.string.st_ok
            Report.ST_SOS -> R.string.st_sos
            else -> R.string.st_no_gps
        }
    )

    fun link(ctx: Context, s: MeshLink.State): String = ctx.getString(
        when (s) {
            MeshLink.State.OFF -> R.string.link_off
            MeshLink.State.CONNECTING -> R.string.link_connecting
            MeshLink.State.PAIRING -> R.string.link_pairing
            MeshLink.State.CONNECTED -> R.string.link_connected
            MeshLink.State.WAITING -> R.string.link_waiting
        }
    )

    fun age(ctx: Context, ms: Long): String {
        val s = ms / 1000
        return when {
            s < 5 -> ctx.getString(R.string.age_now)
            s < 90 -> ctx.getString(R.string.age_s, s)
            s < 3600 -> ctx.getString(R.string.age_min, s / 60)
            s < 48 * 3600 -> ctx.getString(R.string.age_h, s / 3600, s % 3600 / 60)
            else -> ctx.getString(R.string.age_d, s / 86400)
        }
    }

    fun kmh(v: Double): String = String.format(Locale.getDefault(), "%.1f km/h", v)

    fun dist(m: Double): String = when {
        m < 1000 -> String.format(Locale.getDefault(), "%.0f m", m)
        m < 10_000 -> String.format(Locale.getDefault(), "%.2f km", m / 1000)
        else -> String.format(Locale.getDefault(), "%.1f km", m / 1000)
    }

    fun duration(ms: Long): String {
        val min = ms / 60_000
        return if (min < 60) "$min min" else "${min / 60} h ${min % 60} min"
    }
}

/** Handing positions and trails over to a map app; Organic Maps first (offline maps, open source). */
object Maps {
    private const val ORGANIC_MAPS = "app.organicmaps"

    private fun hasOrganicMaps(ctx: Context) =
        runCatching { ctx.packageManager.getPackageInfo(ORGANIC_MAPS, 0) }.isSuccess

    fun showPoint(ctx: Context, lat: Double, lon: Double, label: String) {
        val uri = Uri.parse(String.format(Locale.ROOT, "geo:%.6f,%.6f?q=%.6f,%.6f(%s)", lat, lon, lat, lon, Uri.encode(label)))
        val intent = Intent(Intent.ACTION_VIEW, uri)
        if (hasOrganicMaps(ctx)) intent.setPackage(ORGANIC_MAPS)
        try {
            ctx.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(ctx, R.string.om_missing, Toast.LENGTH_LONG).show()
        }
    }

    /** writes the trail as GPX into Downloads/TrackDog and opens it (Organic Maps imports it as a track) */
    fun showTrail(ctx: Context, name: String, points: List<Trail.Point>) {
        if (points.isEmpty()) {
            Toast.makeText(ctx, R.string.gpx_empty, Toast.LENGTH_SHORT).show()
            return
        }
        val uri = try {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, "$name.gpx")
                put(MediaStore.Downloads.MIME_TYPE, GPX_MIME)
                put(MediaStore.Downloads.RELATIVE_PATH, "Download/TrackDog")
            }
            val u = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)!!
            ctx.contentResolver.openOutputStream(u)!!.use { it.write(gpx(name, points).toByteArray()) }
            u
        } catch (e: Exception) {
            Toast.makeText(ctx, R.string.gpx_failed, Toast.LENGTH_LONG).show()
            return
        }
        val view = Intent(Intent.ACTION_VIEW).setDataAndType(uri, GPX_MIME).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        if (hasOrganicMaps(ctx)) view.setPackage(ORGANIC_MAPS)
        try {
            ctx.startActivity(view)
        } catch (e: ActivityNotFoundException) {
            // nobody opens GPX directly: let the user pick where to send the file
            val send = Intent(Intent.ACTION_SEND).setType(GPX_MIME).putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            ctx.startActivity(Intent.createChooser(send, name))
        }
    }

    fun gpx(name: String, points: List<Trail.Point>): String {
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ROOT).apply { timeZone = TimeZone.getTimeZone("UTC") }
        val sb = StringBuilder()
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        sb.append("<gpx version=\"1.1\" creator=\"TrackDog\" xmlns=\"http://www.topografix.com/GPX/1/1\">\n")
        sb.append("<trk><name>").append(xml(name)).append("</name>\n<trkseg>\n")
        var prev: Report? = null
        for (p in points) {
            val r = p.r
            // a long silence starts a new segment, so the map does not draw a straight line across it
            if (prev != null && r.time - prev.time > Trail.MAX_GAP_MS) sb.append("</trkseg>\n<trkseg>\n")
            sb.append(String.format(Locale.ROOT, "<trkpt lat=\"%.6f\" lon=\"%.6f\"><time>%s</time>", r.lat, r.lon, iso.format(Date(r.time))))
            p.speedKmh?.let { sb.append(String.format(Locale.ROOT, "<extensions><speed>%.2f</speed></extensions>", it / 3.6)) }
            sb.append("</trkpt>\n")
            prev = r
        }
        sb.append("</trkseg></trk>\n</gpx>\n")
        return sb.toString()
    }

    private fun xml(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    private const val GPX_MIME = "application/gpx+xml"
}
