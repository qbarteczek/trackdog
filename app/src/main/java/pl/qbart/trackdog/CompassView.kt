package pl.qbart.trackdog

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/**
 * The signature screen: a compass whose dial turns with the phone and a retriever head that sits on
 * the rim in the direction of the dog. Distance in the middle.
 */
class CompassView @JvmOverloads constructor(ctx: Context, attrs: AttributeSet? = null) : View(ctx, attrs) {

    /** where the top of the phone points, degrees from true north; null = no sensor (dial stays north-up) */
    var heading: Float? = null
        set(v) { field = v; invalidate() }

    /** direction from the phone to the dog, degrees from north; null = unknown */
    var bearing: Float? = null
        set(v) { field = v; invalidate() }

    var title: String = ""
        set(v) { field = v; invalidate() }
    var subtitle: String = ""
        set(v) { field = v; invalidate() }
    var alarm: Boolean = false
        set(v) { field = v; invalidate() }

    private val dp = resources.displayMetrics.density
    private val gold = ctx.getColor(R.color.gold)
    private val cream = ctx.getColor(R.color.cream)
    private val muted = ctx.getColor(R.color.muted)
    private val red = ctx.getColor(R.color.red)
    private val surface = ctx.getColor(R.color.surface)
    private val line = ctx.getColor(R.color.line)

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply { textAlign = Paint.Align.CENTER }
    private val light = Typeface.create("sans-serif-light", Typeface.NORMAL)
    private val medium = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    private val dog = ctx.getDrawable(R.drawable.ic_stat_dog)!!.mutate()
    private val path = Path()
    private val arc = RectF()

    override fun onMeasure(widthSpec: Int, heightSpec: Int) {
        val w = MeasureSpec.getSize(widthSpec)
        val h = MeasureSpec.getSize(heightSpec)
        // a square as large as the space allows
        val side = if (MeasureSpec.getMode(heightSpec) == MeasureSpec.UNSPECIFIED) w else min(w, h)
        setMeasuredDimension(w, if (MeasureSpec.getMode(heightSpec) == MeasureSpec.EXACTLY) h else side)
    }

    override fun onDraw(c: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val r = min(width, height) / 2f - 22 * dp
        if (r <= 0) return
        val accent = if (alarm) red else gold
        val head = heading ?: 0f

        // face
        fill.color = surface
        c.drawCircle(cx, cy, r, fill)
        stroke.color = accent
        stroke.strokeWidth = 3 * dp
        c.drawCircle(cx, cy, r, stroke)
        stroke.color = line
        stroke.strokeWidth = 1 * dp
        c.drawCircle(cx, cy, r * 0.62f, stroke)

        // marker of the phone's own direction, fixed at the top
        fill.color = cream
        path.rewind()
        path.moveTo(cx, cy - r - 5 * dp)
        path.lineTo(cx - 7 * dp, cy - r - 17 * dp)
        path.lineTo(cx + 7 * dp, cy - r - 17 * dp)
        path.close()
        c.drawPath(path, fill)

        // dial: turns against the heading, so N stays on north
        c.save()
        c.rotate(-head, cx, cy)
        for (deg in 0 until 360 step 5) {
            val major = deg % 30 == 0
            val len = if (deg % 90 == 0) 13 * dp else if (major) 10 * dp else 5 * dp
            stroke.color = if (major) accent else line
            stroke.strokeWidth = (if (major) 2f else 1.2f) * dp
            val a = Math.toRadians(deg.toDouble())
            val sx = sin(a).toFloat()
            val sy = -cos(a).toFloat()
            c.drawLine(cx + sx * (r - 5 * dp), cy + sy * (r - 5 * dp), cx + sx * (r - 5 * dp - len), cy + sy * (r - 5 * dp - len), stroke)
        }
        text.typeface = medium
        text.textSize = 17 * dp
        val letters = arrayOf("N", "E", "S", "W")
        for (i in 0..3) {
            c.save()
            c.rotate(i * 90f, cx, cy)
            text.color = if (i == 0) red else muted
            c.drawText(letters[i], cx, cy - r + 38 * dp, text)
            c.restore()
        }
        c.restore()

        // the dog: a glowing sector, a pointer on the rim and the head itself, always upright
        bearing?.let { b ->
            val rel = b - head
            fill.color = accent
            fill.alpha = 46
            arc.set(cx - r, cy - r, cx + r, cy + r)
            c.drawArc(arc, rel - 90 - 14, 28f, true, fill)
            fill.alpha = 255

            c.save()
            c.rotate(rel, cx, cy)
            path.rewind()
            path.moveTo(cx, cy - r - 3 * dp)
            path.lineTo(cx - 9 * dp, cy - r + 15 * dp)
            path.lineTo(cx, cy - r + 10 * dp)
            path.lineTo(cx + 9 * dp, cy - r + 15 * dp)
            path.close()
            c.drawPath(path, fill)
            c.restore()

            val a = Math.toRadians(rel.toDouble())
            val hx = cx + sin(a).toFloat() * r * 0.72f
            val hy = cy - cos(a).toFloat() * r * 0.72f
            val hs = 17 * dp
            fill.color = surface
            c.drawCircle(hx, hy, hs + 7 * dp, fill)
            stroke.color = accent
            stroke.strokeWidth = 1.5f * dp
            c.drawCircle(hx, hy, hs + 7 * dp, stroke)
            dog.setTint(accent)
            dog.setBounds((hx - hs).toInt(), (hy - hs).toInt(), (hx + hs).toInt(), (hy + hs).toInt())
            dog.draw(c)
        }

        // middle: distance and a line under it
        text.typeface = light
        text.color = cream
        text.textSize = min(r * 0.36f, 56 * dp)
        // shrink a long text (e.g. a message instead of a distance) to the inner ring
        val maxW = r * 1.1f
        val w = text.measureText(title)
        if (w > maxW) text.textSize *= maxW / w
        c.drawText(title, cx, cy + text.textSize * 0.2f, text)
        text.typeface = medium
        text.color = if (alarm) red else muted
        text.textSize = 13 * dp
        c.drawText(subtitle, cx, cy + r * 0.30f, text)
    }
}
