package pl.qbart.trackdog

import android.app.Activity
import android.content.Context
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import org.mapsforge.core.graphics.Cap
import org.mapsforge.core.graphics.Join
import org.mapsforge.core.graphics.Paint
import org.mapsforge.core.graphics.Style
import org.mapsforge.core.model.BoundingBox
import org.mapsforge.core.model.LatLong
import org.mapsforge.core.model.MapPosition
import org.mapsforge.core.util.LatLongUtils
import org.mapsforge.map.android.graphics.AndroidGraphicFactory
import org.mapsforge.map.android.util.AndroidUtil
import org.mapsforge.map.android.view.MapView
import org.mapsforge.map.datastore.MultiMapDataStore
import org.mapsforge.map.layer.Layer
import org.mapsforge.map.layer.cache.TileCache
import org.mapsforge.map.layer.overlay.FixedPixelCircle
import org.mapsforge.map.layer.overlay.Polyline
import org.mapsforge.map.layer.renderer.TileRendererLayer
import org.mapsforge.map.reader.MapFile
import org.mapsforge.map.scalebar.DefaultMapScaleBar
import org.mapsforge.map.rendertheme.internal.MapsforgeThemes
import java.io.File

/** The offline map files of the app: Mapsforge .map files in the app's own folder. */
object MapFiles {
    fun dir(ctx: Context): File = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "maps").apply { mkdirs() }
    fun list(ctx: Context): List<File> =
        dir(ctx).listFiles { f -> f.isFile && f.name.endsWith(".map") }?.sortedBy { it.name } ?: emptyList()
}

/**
 * The trail on a real map, drawn on the phone from offline vector maps (Mapsforge, OpenStreetMap data).
 * Lives inside [box], on top of the plain [TrailView] that stays as the picture for "no map loaded".
 */
class TrailMap(private val activity: Activity, private val box: FrameLayout) {
    private val gf = AndroidGraphicFactory.INSTANCE
    private val dp = activity.resources.displayMetrics.density
    private var mapView: MapView? = null
    private var tileCache: TileCache? = null
    private var loaded: List<String> = emptyList()
    private val overlays = ArrayList<Layer>()
    private var fitKey = ""
    private var bounds: BoundingBox? = null

    val view: View? get() = mapView
    val active: Boolean get() = mapView != null

    /** builds (or rebuilds) the map view when the set of map files changed; false = no usable map */
    fun ensure(): Boolean {
        val files = MapFiles.list(activity)
        val names = files.map { it.name + it.length() }
        if (names == loaded && (mapView != null || files.isEmpty())) return mapView != null
        destroy()
        loaded = names
        if (files.isEmpty()) return false

        val store = MultiMapDataStore(MultiMapDataStore.DataPolicy.RETURN_ALL)
        var good = 0
        for (f in files) {
            try {
                store.addMapDataStore(MapFile(f), false, false)
                good++
            } catch (e: Exception) {   // not a map, or a broken download
                Log.w("TrackDog", "map ${f.name} not usable: $e")
            }
        }
        if (good == 0) return false

        val mv = MapView(activity)
        mv.isClickable = true
        mv.mapScaleBar.isVisible = true
        (mv.mapScaleBar as? DefaultMapScaleBar)?.scaleBarMode = DefaultMapScaleBar.ScaleBarMode.SINGLE   // metres only
        mv.setBuiltInZoomControls(false)
        mv.model.mapViewPosition.zoomLevelMin = 7
        mv.model.mapViewPosition.zoomLevelMax = 20
        val cache = AndroidUtil.createTileCache(
            activity, "mapcache", mv.model.displayModel.tileSize, 1f, mv.model.frameBufferModel.overdrawFactor
        )
        val layer = TileRendererLayer(cache, store, mv.model.mapViewPosition, gf)
        layer.setXmlRenderTheme(MapsforgeThemes.DEFAULT)
        mv.layerManager.layers.add(layer)
        box.addView(mv, 1, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        mapView = mv
        tileCache = cache
        fitKey = ""
        return true
    }

    private fun paint(color: Int, widthDp: Float, style: Style): Paint = gf.createPaint().apply {
        setColor(color)
        setStrokeWidth(widthDp * dp)
        setStyle(style)
        setStrokeCap(Cap.ROUND)
        setStrokeJoin(Join.ROUND)
    }

    private fun speedColor(kmh: Double?) = when {
        kmh == null || kmh < 1.0 -> STILL
        kmh < Fmt.FAST_KMH -> WALK
        else -> FAST
    }

    /**
     * Draws the trail. The view moves to fit the trail only when [key] changes (another day or tracker),
     * so new reports do not undo the user's own panning and zooming.
     */
    fun show(points: List<Trail.Point>, phone: Pair<Double, Double>?, key: String) {
        val mv = mapView ?: return
        val layers = mv.layerManager.layers
        for (l in overlays) layers.remove(l)
        overlays.clear()

        if (points.isNotEmpty()) {
            // a dark casing under the coloured trail keeps it readable on any map colour
            var run = ArrayList<LatLong>()
            val casings = ArrayList<Polyline>()
            val colours = ArrayList<Polyline>()
            var colour = 0
            fun flush() {
                if (run.size < 2) return
                casings += Polyline(paint(CASING, 6.5f, Style.STROKE), gf).apply { setPoints(run) }
                colours += Polyline(paint(colour, 3.5f, Style.STROKE), gf).apply { setPoints(run) }
            }
            for (i in 1 until points.size) {
                val a = points[i - 1].r
                val b = points[i].r
                if (b.time - a.time > Trail.MAX_GAP_MS) {   // silence: no line across it
                    flush()
                    run = ArrayList()
                    continue
                }
                val c = speedColor(points[i].speedKmh)
                if (run.isEmpty() || c != colour) {
                    flush()
                    run = arrayListOf(LatLong(a.lat!!, a.lon!!))
                    colour = c
                }
                run.add(LatLong(b.lat!!, b.lon!!))
            }
            flush()
            overlays += casings
            overlays += colours

            // radii are in dp: the map scales them to the screen itself
            val first = points.first().r
            overlays += FixedPixelCircle(LatLong(first.lat!!, first.lon!!), 5f, paint(WHITE, 0f, Style.FILL), paint(CASING, 2f, Style.STROKE))
        }
        phone?.let {
            overlays += FixedPixelCircle(LatLong(it.first, it.second), 6f, paint(PHONE, 0f, Style.FILL), paint(WHITE, 2f, Style.STROKE))
        }
        if (points.isNotEmpty()) {
            val last = points.last().r
            overlays += FixedPixelCircle(LatLong(last.lat!!, last.lon!!), 8f, paint(DOG, 0f, Style.FILL), paint(CASING, 2.5f, Style.STROKE))
        }
        for (l in overlays) layers.add(l)

        bounds = if (points.isEmpty()) null else BoundingBox(
            points.minOf { it.r.lat!! }, points.minOf { it.r.lon!! }, points.maxOf { it.r.lat!! }, points.maxOf { it.r.lon!! }
        )
        if (key != fitKey) {
            fitKey = key
            fit()
        }
        mv.layerManager.redrawLayers()
    }

    /** shows the whole trail; without a trail the middle of the loaded map */
    fun fit() {
        val mv = mapView ?: return
        mv.post {
            val bb = bounds
            val dim = mv.dimension
            if (bb == null) {
                if (mv.model.mapViewPosition.center.latitude == 0.0) {
                    val all = runCatching { MapFile(MapFiles.list(activity).first()).boundingBox() }.getOrNull() ?: return@post
                    mv.model.mapViewPosition.mapPosition = MapPosition(all.centerPoint, 9)
                }
                return@post
            }
            if (dim.width <= 0 || dim.height <= 0) return@post
            val margin = bb.extendMeters(60)
            val zoom = LatLongUtils.zoomForBounds(dim, margin, mv.model.displayModel.tileSize).toInt().coerceIn(8, 17)
            mv.model.mapViewPosition.mapPosition = MapPosition(margin.centerPoint, zoom.toByte())
        }
    }

    fun destroy() {
        val mv = mapView ?: return
        box.removeView(mv)
        overlays.clear()
        mv.destroyAll()
        tileCache = null
        mapView = null
    }

    companion object {
        private const val CASING = 0xFF12241F.toInt()
        private const val STILL = 0xFF8FA69E.toInt()
        private const val WALK = 0xFFF2A91E.toInt()
        private const val FAST = 0xFFE4572E.toInt()
        private const val WHITE = 0xFFFFFFFF.toInt()
        private const val DOG = 0xFFE7B55C.toInt()
        private const val PHONE = 0xFF2F8FE0.toInt()
    }
}
