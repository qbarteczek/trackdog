package pl.qbart.trackdog

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.GeomagneticField
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.text.SpannableString
import android.text.style.ForegroundColorSpan
import android.view.View
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

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
            main.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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

    private fun showTab(i: Int) {
        tab = i
        pages.forEachIndexed { n, v -> v.visibility = if (n == i) View.VISIBLE else View.GONE }
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
        trailView.phone = phone?.let { Pair(it.latitude, it.longitude) }
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
        if (tab == 1) trailView.phone = Pair(loc.latitude, loc.longitude)
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
}
