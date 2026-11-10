package pl.qbart.trackdog

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * The trail of one day drawn to scale, north up, coloured by speed. No map tiles: the picture works
 * with no network at all. The same trail opens in Organic Maps for the real map.
 */
class TrailView @JvmOverloads constructor(ctx: Context, attrs: AttributeSet? = null) : View(ctx, attrs) {

    var points: List<Trail.Point> = emptyList()
        set(v) { field = v; invalidate() }

    /** position of the phone (lat, lon), drawn when it is near the trail */
    var phone: Pair<Double, Double>? = null
        set(v) { field = v; invalidate() }

    var emptyText: String = ""

    private val dp = resources.displayMetrics.density
    private val gold = ctx.getColor(R.color.gold)
    private val cream = ctx.getColor(R.color.cream)
    private val muted = ctx.getColor(R.color.muted)
    private val red = ctx.getColor(R.color.red)
    private val blue = ctx.getColor(R.color.blue)
    private val bg = ctx.getColor(R.color.bg)
    private val lineColor = ctx.getColor(R.color.line)

    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
    }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }
    private val dash = DashPathEffect(floatArrayOf(4 * dp, 7 * dp), 0f)
    private val path = Path()

    private fun speedColor(kmh: Double?) = when {
        kmh == null || kmh < 1.0 -> muted
        kmh < Fmt.FAST_KMH -> gold
        else -> red
    }

    override fun onDraw(c: Canvas) {
        val pts = points
        if (pts.isEmpty()) {
            text.color = muted
            text.textSize = 15 * dp
            text.textAlign = Paint.Align.CENTER
            c.drawText(emptyText, width / 2f, height / 2f, text)
            return
        }

        // bounds in metres around the middle of the trail (flat-earth is fine at this size)
        var minLat = pts.minOf { it.r.lat!! }
        var maxLat = pts.maxOf { it.r.lat!! }
        var minLon = pts.minOf { it.r.lon!! }
        var maxLon = pts.maxOf { it.r.lon!! }
        val lat0 = (minLat + maxLat) / 2
        val lon0 = (minLon + maxLon) / 2
        val mLat = 110_540.0
        val mLon = 111_320.0 * cos(Math.toRadians(lat0))
        // the phone joins the picture only when it does not shrink the trail to a dot
        val ph = phone?.takeIf {
            val span = max((maxLat - minLat) * mLat, (maxLon - minLon) * mLon).coerceAtLeast(200.0)
            Geo.distM(lat0, lon0, it.first, it.second) < span * 2
        }
        if (ph != null) {
            minLat = min(minLat, ph.first); maxLat = max(maxLat, ph.first)
            minLon = min(minLon, ph.second); maxLon = max(maxLon, ph.second)
        }
        val cLat = (minLat + maxLat) / 2
        val cLon = (minLon + maxLon) / 2
        val spanX = max((maxLon - minLon) * mLon, 120.0)
        val spanY = max((maxLat - minLat) * mLat, 120.0)
        val pad = 30 * dp
        val scale = min((width - 2 * pad) / spanX, (height - 2 * pad) / spanY).toFloat()   // px per metre
        fun x(lon: Double) = width / 2f + ((lon - cLon) * mLon).toFloat() * scale
        fun y(lat: Double) = height / 2f - ((lat - cLat) * mLat).toFloat() * scale

        // trail: one segment per pair of fixes, coloured by the speed on arrival
        stroke.strokeWidth = 3.5f * dp
        for (i in 1 until pts.size) {
            val a = pts[i - 1].r
            val b = pts[i].r
            val gap = b.time - a.time > Trail.MAX_GAP_MS
            stroke.color = if (gap) lineColor else speedColor(pts[i].speedKmh)
            stroke.pathEffect = if (gap) dash else null
            c.drawLine(x(a.lon!!), y(a.lat!!), x(b.lon!!), y(b.lat!!), stroke)
        }
        stroke.pathEffect = null

        // fixes
        if (pts.size <= 400) {
            fill.color = bg
            for (p in pts) c.drawCircle(x(p.r.lon!!), y(p.r.lat!!), 1.6f * dp, fill)
        }

        // start: a ring
        val first = pts.first().r
        stroke.color = cream
        stroke.strokeWidth = 2 * dp
        fill.color = bg
        c.drawCircle(x(first.lon!!), y(first.lat!!), 5 * dp, fill)
        c.drawCircle(x(first.lon), y(first.lat), 5 * dp, stroke)

        // phone
        if (ph != null) {
            fill.color = blue
            fill.alpha = 60
            c.drawCircle(x(ph.second), y(ph.first), 11 * dp, fill)
            fill.alpha = 255
            c.drawCircle(x(ph.second), y(ph.first), 5 * dp, fill)
        }

        // the dog now: a gold disc with a halo
        val last = pts.last().r
        val lx = x(last.lon!!)
        val ly = y(last.lat!!)
        fill.color = gold
        fill.alpha = 50
        c.drawCircle(lx, ly, 15 * dp, fill)
        fill.alpha = 255
        c.drawCircle(lx, ly, 7.5f * dp, fill)
        stroke.color = bg
        stroke.strokeWidth = 2 * dp
        c.drawCircle(lx, ly, 7.5f * dp, stroke)

        // scale bar: a round number of metres about a quarter of the width
        val target = width / 4f / scale
        val mag = 10.0.pow(kotlin.math.floor(kotlin.math.log10(target.toDouble())))
        val nice = listOf(1.0, 2.0, 5.0, 10.0).map { it * mag }.last { it <= target * 1.4 }
        val barW = (nice * scale).toFloat()
        val bx = 14 * dp
        val by = height - 14 * dp
        stroke.color = muted
        stroke.strokeWidth = 2 * dp
        path.rewind()
        path.moveTo(bx, by - 5 * dp); path.lineTo(bx, by); path.lineTo(bx + barW, by); path.lineTo(bx + barW, by - 5 * dp)
        c.drawPath(path, stroke)
        text.color = muted
        text.textSize = 11 * dp
        text.textAlign = Paint.Align.LEFT
        c.drawText(Fmt.dist(nice), bx + 4 * dp, by - 6 * dp, text)

        // north
        val nx = width - 20 * dp
        val ny = 26 * dp
        fill.color = red
        path.rewind()
        path.moveTo(nx, ny - 14 * dp); path.lineTo(nx - 5 * dp, ny - 2 * dp); path.lineTo(nx + 5 * dp, ny - 2 * dp); path.close()
        c.drawPath(path, fill)
        text.textAlign = Paint.Align.CENTER
        c.drawText("N", nx, ny + 10 * dp, text)
    }
}

/** Speed over the time of the day's trail. */
class SpeedChartView @JvmOverloads constructor(ctx: Context, attrs: AttributeSet? = null) : View(ctx, attrs) {

    var points: List<Trail.Point> = emptyList()
        set(v) { field = v; invalidate() }

    private val dp = resources.displayMetrics.density
    private val gold = ctx.getColor(R.color.gold)
    private val muted = ctx.getColor(R.color.muted)
    private val lineColor = ctx.getColor(R.color.line)
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND
    }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }
    private val path = Path()
    private val clock = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault())

    override fun onDraw(c: Canvas) {
        val pts = points.filter { it.speedKmh != null }
        if (pts.size < 2) return
        val t0 = pts.first().r.time
        val t1 = pts.last().r.time
        if (t1 <= t0) return
        val top = max(8.0, pts.maxOf { it.speedKmh!! }.coerceAtMost(60.0) * 1.15)
        val left = 12 * dp
        val right = width - 12 * dp
        val bottom = height - 18 * dp
        val topY = 16 * dp
        fun x(t: Long) = left + (right - left) * (t - t0).toFloat() / (t1 - t0)
        fun y(v: Double) = bottom - (bottom - topY) * (v.coerceAtMost(top) / top).toFloat()

        // the "running" threshold
        stroke.color = lineColor
        stroke.strokeWidth = 1 * dp
        c.drawLine(left, y(Fmt.FAST_KMH), right, y(Fmt.FAST_KMH), stroke)
        c.drawLine(left, bottom, right, bottom, stroke)

        path.rewind()
        path.moveTo(x(t0), bottom)
        for (p in pts) path.lineTo(x(p.r.time), y(p.speedKmh!!))
        path.lineTo(x(t1), bottom)
        path.close()
        fill.color = gold
        fill.alpha = 45
        c.drawPath(path, fill)

        path.rewind()
        pts.forEachIndexed { i, p -> if (i == 0) path.moveTo(x(p.r.time), y(p.speedKmh!!)) else path.lineTo(x(p.r.time), y(p.speedKmh!!)) }
        stroke.color = gold
        stroke.strokeWidth = 2 * dp
        c.drawPath(path, stroke)

        text.color = muted
        text.textSize = 10.5f * dp
        text.textAlign = Paint.Align.LEFT
        c.drawText(clock.format(java.util.Date(t0)), left, height - 4 * dp, text)
        c.drawText("km/h", left, 11 * dp, text)
        text.textAlign = Paint.Align.RIGHT
        c.drawText(clock.format(java.util.Date(t1)), right, height - 4 * dp, text)
    }
}
