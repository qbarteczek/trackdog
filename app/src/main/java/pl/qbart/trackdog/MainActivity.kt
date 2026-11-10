package pl.qbart.trackdog

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.GeomagneticField
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.provider.OpenableColumns
import android.text.SpannableString
import android.text.style.ForegroundColorSpan
import android.graphics.Rect
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ListView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import org.mapsforge.map.android.graphics.AndroidGraphicFactory
import org.mapsforge.map.reader.MapFile
import java.io.File
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import kotlin.math.abs

class MainActivity : Activity(), SensorEventListener, LocationListener {
    private lateinit var store: Store
    private lateinit var prefs: Prefs
    private val main = Handler(Looper.getMainLooper())

    private lateinit var pages: List<View>
    private lateinit var tabs: List<TextView>
    private lateinit var compass: CompassView
    private lateinit var trailView: TrailView
    private lateinit var chart: SpeedChartView
    private lateinit var swDemo: Switch
    private lateinit var trailBox: FrameLayout
    private lateinit var trailMap: TrailMap
    private lateinit var gestures: GestureDetector
    private var mapPhone: Location? = null
    private var tab = 0

    // what is on screen
    private var tracker: String? = null
    private var last: Report? = null        // newest report of the tracker
    private var pos: Report? = null         // newest report with a position (may be older than [last])
    private var lastSpeed: Double? = null
    private var day: String? = null         // yyyy-MM-dd shown on the trail page
    private var days: List<String> = emptyList()
    private var trail: Trail? = null
    private var trailKey = ""

    // the phone itself
    private var phone: Location? = null
    private var heading: Float? = null
    private val rot = FloatArray(9)
    private val orient = FloatArray(3)

    private val hubListener: () -> Unit = { reload() }
    private val ticker = object : Runnable {
        override fun run() {
            live()
            if (prefs.mapDownload != 0L) pollMapDownload()
            main.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AndroidGraphicFactory.createInstance(application)   // before any map view
        setContentView(R.layout.activity_main)
        store = Store(this)
        prefs = Prefs(this)

        pages = listOf(findViewById(R.id.pageCompass), findViewById(R.id.pageTrail), findViewById(R.id.pageDevice))
        tabs = listOf(findViewById(R.id.tabCompass), findViewById(R.id.tabTrail), findViewById(R.id.tabDevice))
        tabs.forEachIndexed { i, t -> t.setOnClickListener { showTab(i) } }
        compass = findViewById(R.id.compass)
        trailView = findViewById(R.id.trail)
        trailView.emptyText = getString(R.string.no_trail)
        chart = findViewById(R.id.chart)
        swDemo = findViewById(R.id.swDemo)
        trailBox = findViewById(R.id.trailBox)
        trailBox.clipToOutline = true   // the map gets the rounded corners of the card
        trailMap = TrailMap(this, trailBox)
        findViewById<View>(R.id.mapFit).setOnClickListener { trailMap.fit() }
        findViewById<View>(R.id.btnMapDownload).setOnClickListener { downloadMap() }
        findViewById<View>(R.id.btnMapImport).setOnClickListener {
            startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"), REQ_MAP)
        }
        findViewById<View>(R.id.btnMapDelete).setOnClickListener {
            AlertDialog.Builder(this).setMessage(R.string.map_delete_confirm)
                .setPositiveButton(R.string.yes) { _, _ ->
                    trailMap.destroy()
                    MapFiles.list(this).forEach { it.delete() }
                    mapsChanged()
                }
                .setNegativeButton(R.string.no, null).show()
        }

        // tabs also change with a horizontal swipe; on the map a swipe moves the map
        val box = Rect()
        gestures = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, velocityX: Float, velocityY: Float): Boolean {
                val start = e1 ?: return false
                if (tab == 1 && trailMap.active && trailBox.getGlobalVisibleRect(box) &&
                    box.contains(start.rawX.toInt(), start.rawY.toInt())) return false
                val dx = e2.x - start.x
                val dy = e2.y - start.y
                if (abs(dx) < 90 * resources.displayMetrics.density || abs(dx) < 2 * abs(dy)) return false
                val next = tab + if (dx < 0) 1 else -1
                if (next in pages.indices) showTab(next)
                return false
            }
        })

        findViewById<View>(R.id.btnPoint).setOnClickListener {
            val p = pos
            if (p != null) Maps.showPoint(this, p.lat!!, p.lon!!, p.tracker)
            else Toast.makeText(this, R.string.no_dog_pos, Toast.LENGTH_SHORT).show()
        }
        findViewById<View>(R.id.btnTrail).setOnClickListener {
            Maps.showTrail(this, "trackdog-${tracker ?: "trail"}-${day ?: ""}", trail?.points ?: emptyList())
        }
        findViewById<View>(R.id.dayPrev).setOnClickListener { stepDay(-1) }
        findViewById<View>(R.id.dayNext).setOnClickListener { stepDay(1) }
        findViewById<View>(R.id.btnPick).setOnClickListener { pickRadio() }
        findViewById<View>(R.id.btnDisconnect).setOnClickListener {
            prefs.mac = null
            prefs.macName = null
            Hub.baseName = null
            applyService()
        }
        findViewById<View>(R.id.cardTracker).setOnClickListener { pickTracker() }
        findViewById<View>(R.id.btnClear).setOnClickListener {
            AlertDialog.Builder(this).setMessage(R.string.clear_confirm)
                .setPositiveButton(R.string.yes) { _, _ ->
                    store.clear()
                    Hub.revision++
                    reload()
                }
                .setNegativeButton(R.string.no, null).show()
        }
        // for screenshots and tests: adb shell am start -n pl.qbart.trackdog/.MainActivity --ez demo true
        if (intent.hasExtra("demo")) prefs.demo = intent.getBooleanExtra("demo", false)
        swDemo.isChecked = prefs.demo
        swDemo.setOnCheckedChangeListener { _, on ->
            prefs.demo = on
            if (!on) {
                store.deleteTracker(TrackService.DEMO_NAME)
                Hub.revision++
            }
            applyService()
        }
        findViewById<TextView>(R.id.devVersion).text = getString(R.string.version_fmt, BuildConfig.VERSION_NAME)

        showTab(if (prefs.mac == null && !prefs.demo) 2 else 0)
        askPermissions()
    }

    override fun onStart() {
        super.onStart()
        Hub.listen(hubListener)
        val sm = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        sm.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)?.let { sm.registerListener(this, it, SensorManager.SENSOR_DELAY_UI) }
        startLocation()
        applyService()
        reload()
        main.post(ticker)
    }

    override fun onStop() {
        main.removeCallbacks(ticker)
        Hub.unlisten(hubListener)
        (getSystemService(Context.SENSOR_SERVICE) as SensorManager).unregisterListener(this)
        (getSystemService(Context.LOCATION_SERVICE) as LocationManager).removeUpdates(this)
        super.onStop()
    }

    // ------------------------------------------------------------------ permissions, service

    private fun granted(p: String) = checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED

    private fun hasBluetooth() = Build.VERSION.SDK_INT < 31 ||
        (granted(Manifest.permission.BLUETOOTH_CONNECT) && granted(Manifest.permission.BLUETOOTH_SCAN))

    private fun askPermissions() {
        val want = ArrayList<String>()
        if (Build.VERSION.SDK_INT >= 31) {
            want += Manifest.permission.BLUETOOTH_CONNECT
            want += Manifest.permission.BLUETOOTH_SCAN
        }
        want += Manifest.permission.ACCESS_FINE_LOCATION
        if (Build.VERSION.SDK_INT >= 33) want += Manifest.permission.POST_NOTIFICATIONS
        val missing = want.filter { !granted(it) }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 1)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        startLocation()
        applyService()
    }

    /** the service runs whenever there is something to listen to */
    private fun applyService() {
        if ((prefs.mac != null || prefs.demo) && hasBluetooth()) TrackService.start(this)
        else {
            TrackService.stop(this)
            reload()
        }
    }

    // ------------------------------------------------------------------ data -> screen

    private fun reload() {
        val trackers = store.trackers()
        tracker = if (prefs.demo) TrackService.DEMO_NAME else prefs.tracker?.takeIf { it in trackers } ?: trackers.firstOrNull()
        last = tracker?.let { store.last(it) }
        pos = last?.takeIf { it.hasPos } ?: tracker?.let { store.lastFix(it) }
        lastSpeed = last?.let { l ->
            // older firmware sends no speed: take it from the last two fixes
            l.speedKmh ?: Trail(store.between(tracker, l.time - 10 * 60_000, l.time + 1)).points.lastOrNull()
                ?.takeIf { it.r.time == l.time }?.speedKmh
        }

        findViewById<TextView>(R.id.headTracker).text = tracker ?: ""
        val l = last
        findViewById<TextView>(R.id.tileSpeed).text = lastSpeed?.let { Fmt.kmh(it) } ?: "—"
        findViewById<TextView>(R.id.tileBattery).text = when {
            l?.battPct == null -> "—"
            l.battMv != null -> String.format(Locale.getDefault(), "%d%% · %.2f V", l.battPct, l.battMv / 1000.0)
            else -> "${l.battPct}%"
        }
        findViewById<TextView>(R.id.tileGps).text = when {
            l == null -> "—"
            !l.hasFix -> getString(R.string.st_no_gps)
            else -> getString(R.string.satellites, l.sats ?: 0) +
                (l.tempC?.let { String.format(Locale.getDefault(), " · %.0f°C", it) } ?: "")
        }
        findViewById<TextView>(R.id.tileSignal).text =
            l?.snr?.let { String.format(Locale.getDefault(), "SNR %.1f dB", it) } ?: "—"

        // link chip and device page
        val state = Hub.linkState
        val demo = prefs.demo
        val color = getColor(
            when {
                demo || state == MeshLink.State.CONNECTED -> R.color.green
                state == MeshLink.State.OFF -> R.color.muted
                else -> R.color.gold
            }
        )
        val linkText = when {
            demo -> getString(R.string.link_demo)
            prefs.mac == null -> getString(R.string.link_none)
            state == MeshLink.State.CONNECTED -> Hub.baseName ?: Fmt.link(this, state)
            else -> Fmt.link(this, state)
        }
        findViewById<TextView>(R.id.headLink).text = SpannableString("● $linkText").apply {
            setSpan(ForegroundColorSpan(color), 0, 1, 0)
        }
        findViewById<TextView>(R.id.devName).text = when {
            demo -> getString(R.string.link_demo)
            prefs.mac == null -> getString(R.string.link_none)
            else -> Hub.baseName ?: prefs.macName ?: prefs.mac
        }
        findViewById<TextView>(R.id.devState).text = when {
            demo || prefs.mac == null -> ""
            else -> Fmt.link(this, state) +
                (Hub.baseMillivolts?.let { String.format(Locale.getDefault(), " · %.2f V", it / 1000.0) } ?: "")
        }
        findViewById<TextView>(R.id.devTracker).text = tracker ?: "—"
        findViewById<TextView>(R.id.devStored).text = getString(R.string.stored_fmt, store.count())
        if (swDemo.isChecked != demo) swDemo.isChecked = demo
        if (prefs.mapDownload == 0L) updateMapInfo()

        if (tab == 1) loadTrail()
        live()
    }

    /** everything that changes with time alone: age of the report, distance, direction */
    private fun live() {
        val l = last
        val now = System.currentTimeMillis()
        findViewById<TextView>(R.id.statusLine).text =
            if (l == null) getString(R.string.no_reports)
            else Fmt.status(this, l) + " · " + Fmt.age(this, now - l.time)

        val p = pos
        val ph = phone
        compass.alarm = l != null && l.sos && now - l.time < 15 * 60_000
        compass.heading = heading
        when {
            p == null -> {
                compass.bearing = null
                compass.title = "—"
                compass.subtitle = getString(if (l == null) R.string.no_reports else R.string.no_dog_pos)
            }
            ph == null -> {
                compass.bearing = null
                compass.title = "—"
                compass.subtitle = getString(R.string.no_phone_gps)
            }
            else -> {
                val b = Geo.bearing(ph.latitude, ph.longitude, p.lat!!, p.lon!!)
                compass.bearing = b.toFloat()
                compass.title = Fmt.dist(Geo.distM(ph.latitude, ph.longitude, p.lat, p.lon))
                val old = p !== l || p.stale || now - p.time > 10 * 60_000
                compass.subtitle = if (old) getString(R.string.last_known) + " · " + Fmt.age(this, now - p.time)
                else Geo.cardinal(b) + " · " + b.toInt() + "°"
            }
        }
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        gestures.onTouchEvent(ev)
        return super.dispatchTouchEvent(ev)
    }

    override fun onDestroy() {
        trailMap.destroy()
        AndroidGraphicFactory.clearResourceMemoryCache()
        super.onDestroy()
    }

    private fun showTab(i: Int) {
        val from = tab
        tab = i
        pages.forEachIndexed { n, v -> v.visibility = if (n == i) View.VISIBLE else View.GONE }
        if (i != from && pages[i].width > 0) {   // the new page slides in from the side it lies on
            pages[i].translationX = pages[i].width * (if (i > from) 0.25f else -0.25f)
            pages[i].alpha = 0f
            pages[i].animate().translationX(0f).alpha(1f).setDuration(170).start()
        }
        tabs.forEachIndexed { n, t -> t.isSelected = n == i }
        if (i == 1) loadTrail()
    }

    // ------------------------------------------------------------------ trail page

    private val dayKey = SimpleDateFormat("yyyy-MM-dd", Locale.ROOT)

    private fun loadTrail() {
        days = store.days(tracker)
        if (day == null || day !in days) day = days.lastOrNull()
        val d = day
        val key = "$tracker|$d|${Hub.revision}"
        if (key != trailKey) {
            trailKey = key
            val reports = if (d == null) emptyList() else {
                val from = Calendar.getInstance().apply { time = dayKey.parse(d)!! }
                val to = (from.clone() as Calendar).apply { add(Calendar.DAY_OF_MONTH, 1) }
                store.between(tracker, from.timeInMillis, to.timeInMillis)
            }
            val t = Trail(reports)
            trail = t
            trailView.points = t.points
            chart.points = t.points
            findViewById<TextView>(R.id.dayTitle).text = if (d == null) "—" else getString(
                R.string.day_fmt, SimpleDateFormat("EEE, d MMM", Locale.getDefault()).format(dayKey.parse(d)!!), t.received, t.lost
            )
            findViewById<TextView>(R.id.tileDistance).text = Fmt.dist(t.distanceM)
            findViewById<TextView>(R.id.tileMoving).text = Fmt.duration(t.movingMs)
            findViewById<TextView>(R.id.tileAvg).text = Fmt.kmh(t.avgMovingKmh)
            findViewById<TextView>(R.id.tileMax).text = Fmt.kmh(t.maxKmh)
        }
        val i = days.indexOf(d)
        findViewById<View>(R.id.dayPrev).alpha = if (i > 0) 1f else 0.25f
        findViewById<View>(R.id.dayNext).alpha = if (i in 0 until days.size - 1) 1f else 0.25f
        val ph = phone?.let { Pair(it.latitude, it.longitude) }
        trailView.phone = ph
        val hasMap = trailMap.ensure()
        findViewById<View>(R.id.mapFit).visibility = if (hasMap) View.VISIBLE else View.GONE
        findViewById<View>(R.id.mapCredit).visibility = if (hasMap) View.VISIBLE else View.GONE
        findViewById<View>(R.id.mapHint).visibility = if (hasMap) View.GONE else View.VISIBLE
        trailView.visibility = if (hasMap) View.INVISIBLE else View.VISIBLE
        if (hasMap) {
            mapPhone = phone
            trailMap.show(trail?.points ?: emptyList(), ph, "$tracker|$d")
        }
    }

    // ------------------------------------------------------------------ offline maps

    /** after a map was added or removed */
    private fun mapsChanged() {
        updateMapInfo()
        if (tab == 1) loadTrail()
    }

    private fun updateMapInfo(progress: String? = null) {
        val files = MapFiles.list(this)
        val lines = files.map { getString(R.string.map_file_fmt, it.name, it.length() / 1_000_000) }.toMutableList()
        if (files.isEmpty() && progress == null) lines += getString(R.string.map_none)
        if (progress != null) lines += progress
        findViewById<TextView>(R.id.mapInfo).text = lines.joinToString("\n")
        findViewById<Button>(R.id.btnMapDownload).setText(
            if (prefs.mapDownload != 0L) R.string.btn_map_cancel else R.string.btn_map_download
        )
        findViewById<View>(R.id.btnMapDelete).visibility = if (files.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun downloadMap() {
        val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        if (prefs.mapDownload != 0L) {   // the button now means "cancel"
            dm.remove(prefs.mapDownload)
            prefs.mapDownload = 0
            updateMapInfo()
            return
        }
        AlertDialog.Builder(this).setMessage(R.string.map_download_confirm)
            .setPositiveButton(R.string.map_download_yes) { _, _ ->
                File(MapFiles.dir(this), MAP_PART).delete()
                val request = DownloadManager.Request(Uri.parse(MAP_URL))
                    .setTitle(getString(R.string.map_download_title))
                    .setDestinationInExternalFilesDir(this, "maps", MAP_PART)
                    .setAllowedOverMetered(false)
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                prefs.mapDownload = dm.enqueue(request)
                pollMapDownload()
            }
            .setNegativeButton(R.string.no, null).show()
    }

    /** follows the running download; when it ends, the file becomes a map */
    private fun pollMapDownload() {
        val id = prefs.mapDownload
        if (id == 0L) return
        val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        var status = -1
        var done = 0L
        var total = 0L
        dm.query(DownloadManager.Query().setFilterById(id))?.use { c ->
            if (c.moveToFirst()) {
                status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                done = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
            }
        }
        when (status) {
            DownloadManager.STATUS_SUCCESSFUL -> {
                prefs.mapDownload = 0
                val part = File(MapFiles.dir(this), MAP_PART)
                val ok = part.renameTo(File(MapFiles.dir(this), MAP_NAME))
                Toast.makeText(this, if (ok) R.string.map_ready else R.string.map_failed, Toast.LENGTH_LONG).show()
                mapsChanged()
            }
            DownloadManager.STATUS_FAILED, -1 -> {
                prefs.mapDownload = 0
                if (status != -1) dm.remove(id)
                Toast.makeText(this, R.string.map_failed, Toast.LENGTH_LONG).show()
                updateMapInfo()
            }
            DownloadManager.STATUS_RUNNING -> updateMapInfo(
                getString(R.string.map_downloading, if (total > 0) (done * 100 / total).toInt() else 0, done / 1_000_000, total.coerceAtLeast(0) / 1_000_000)
            )
            else -> updateMapInfo(getString(R.string.map_waiting))
        }
    }

    /** a .map file chosen by the user is copied into the app's own folder */
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        val uri = data?.data
        if (requestCode != REQ_MAP || resultCode != RESULT_OK || uri == null) return
        var name = "map.map"
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0)?.let { name = it }
        }
        name = name.replace(Regex("[^A-Za-z0-9._-]"), "_")
        if (!name.endsWith(".map")) name += ".map"
        val target = File(MapFiles.dir(this), name)
        val part = File(MapFiles.dir(this), "$name.part")
        val dialog = AlertDialog.Builder(this).setMessage(getString(R.string.map_copying, 0)).setCancelable(false).show()
        Thread {
            val ok = try {
                contentResolver.openInputStream(uri)!!.use { input ->
                    part.outputStream().use { out ->
                        val buf = ByteArray(1 shl 20)
                        var copied = 0L
                        while (true) {
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            copied += n
                            if (copied % (16L shl 20) < n) {
                                val mb = copied / 1_000_000
                                runOnUiThread { dialog.setMessage(getString(R.string.map_copying, mb)) }
                            }
                        }
                    }
                }
                MapFile(part).close()   // throws when the file is not a map
                target.delete()
                part.renameTo(target)
            } catch (e: Exception) {
                false
            }
            if (!ok) part.delete()
            runOnUiThread {
                dialog.dismiss()
                Toast.makeText(this, if (ok) R.string.map_ready else R.string.map_bad, Toast.LENGTH_LONG).show()
                mapsChanged()
            }
        }.start()
    }

    private fun stepDay(step: Int) {
        val i = days.indexOf(day) + step
        if (i in days.indices) {
            day = days[i]
            loadTrail()
        }
    }

    // ------------------------------------------------------------------ choosing the radio and the tracker

    @SuppressLint("MissingPermission")
    private fun pickRadio() {
        if (!hasBluetooth() || (Build.VERSION.SDK_INT < 31 && !granted(Manifest.permission.ACCESS_FINE_LOCATION))) {
            Toast.makeText(this, R.string.perm_needed, Toast.LENGTH_LONG).show()
            askPermissions()
            return
        }
        val adapter = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
        val scanner = adapter?.takeIf { it.isEnabled }?.bluetoothLeScanner
        if (scanner == null) {
            Toast.makeText(this, R.string.bt_off, Toast.LENGTH_LONG).show()
            return
        }
        val names = ArrayList<String>()
        val macs = ArrayList<String>()
        val list = ArrayAdapter(this, android.R.layout.simple_list_item_1, names)
        val view = ListView(this)
        val pad = (16 * resources.displayMetrics.density).toInt()
        view.addHeaderView(TextView(this).apply {
            setText(R.string.scan_hint)
            setTextColor(getColor(R.color.muted))
            setPadding(pad + pad / 2, pad / 2, pad, pad / 2)
        }, null, false)
        view.adapter = list

        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val name = result.scanRecord?.deviceName ?: result.device.name ?: return
                val uart = result.scanRecord?.serviceUuids?.contains(ParcelUuid(MeshLink.UART)) == true
                if (!name.startsWith("MeshCore") && !uart) return
                if (result.device.address in macs) return
                macs += result.device.address
                names += name.removePrefix("MeshCore-")
                list.notifyDataSetChanged()
            }
        }
        val dialog = AlertDialog.Builder(this).setTitle(R.string.scan_title).setView(view)
            .setNegativeButton(R.string.no, null)
            .setOnDismissListener { runCatching { scanner.stopScan(callback) } }
            .create()
        view.setOnItemClickListener { _, _, position, _ ->
            val i = position - 1   // the hint is row 0
            if (i !in macs.indices) return@setOnItemClickListener
            prefs.mac = macs[i]
            prefs.macName = names[i]
            prefs.demo = false
            Hub.baseName = names[i]
            dialog.dismiss()
            applyService()
            showTab(0)
        }
        scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback)
        main.postDelayed({ runCatching { scanner.stopScan(callback) } }, 30_000)
        dialog.show()
    }

    private fun pickTracker() {
        val trackers = store.trackers().filter { it != TrackService.DEMO_NAME }
        if (prefs.demo || trackers.isEmpty()) return
        val items = arrayOf(getString(R.string.tracker_auto)) + trackers
        AlertDialog.Builder(this).setTitle(R.string.lbl_tracker)
            .setItems(items) { _, which ->
                prefs.tracker = if (which == 0) null else trackers[which - 1]
                reload()
            }.show()
    }

    // ------------------------------------------------------------------ the phone: position and heading

    @SuppressLint("MissingPermission")
    private fun startLocation() {
        if (!granted(Manifest.permission.ACCESS_FINE_LOCATION)) return
        val lm = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            if (provider !in lm.allProviders) continue
            runCatching {
                lm.requestLocationUpdates(provider, 2000L, 1f, this)
                lm.getLastKnownLocation(provider)?.let { onLocationChanged(it) }
            }
        }
    }

    override fun onLocationChanged(loc: Location) {
        val cur = phone
        // GPS wins; the network position only fills in while GPS is silent
        val better = cur == null || loc.provider == LocationManager.GPS_PROVIDER ||
            loc.time - cur.time > 20_000 || (loc.hasAccuracy() && cur.hasAccuracy() && loc.accuracy < cur.accuracy)
        if (!better) return
        phone = loc
        if (tab == 1) {
            trailView.phone = Pair(loc.latitude, loc.longitude)
            // on the map the phone's dot moves only after a few metres: redrawing costs more there
            val shown = mapPhone
            if (trailMap.active && (shown == null || shown.distanceTo(loc) > 8)) loadTrail()
        }
        live()
    }

    @Deprecated("Deprecated in API 29, still called there")
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}

    override fun onSensorChanged(e: SensorEvent) {
        SensorManager.getRotationMatrixFromVector(rot, e.values)
        SensorManager.getOrientation(rot, orient)
        var deg = Math.toDegrees(orient[0].toDouble()).toFloat()
        // magnetic -> true north
        phone?.let {
            deg += GeomagneticField(it.latitude.toFloat(), it.longitude.toFloat(), it.altitude.toFloat(), System.currentTimeMillis()).declination
        }
        val old = heading
        // smooth, the short way round the circle
        heading = if (old == null) deg else (old + (((deg - old + 540f) % 360f) - 180f) * 0.2f + 360f) % 360f
        if (tab == 0) compass.heading = heading
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    companion object {
        private const val REQ_MAP = 2
        private const val MAP_NAME = "poland.map"
        private const val MAP_PART = "poland.map.download"
        // a mirror of download.mapsforge.org (the project asks to use mirrors for big files)
        private const val MAP_URL = "https://ftp-stud.hs-esslingen.de/pub/Mirrors/download.mapsforge.org/maps/v5/europe/poland.map"
    }
}
