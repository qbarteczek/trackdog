package pl.qbart.trackdog

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import java.util.Locale
import java.util.concurrent.CopyOnWriteArraySet
import kotlin.math.cos
import kotlin.math.sin

/** What the screens show; changed only on the main thread. */
object Hub {
    var linkState = MeshLink.State.OFF
    var baseName: String? = null
    var baseMillivolts: Int? = null
    var revision = 0           // grows with every stored report
    private val listeners = CopyOnWriteArraySet<() -> Unit>()

    fun listen(l: () -> Unit) { listeners.add(l) }
    fun unlisten(l: () -> Unit) { listeners.remove(l) }
    fun changed() { for (l in listeners) l() }
}

class Prefs(ctx: Context) {
    private val p = ctx.applicationContext.getSharedPreferences("trackdog", Context.MODE_PRIVATE)
    var mac: String?
        get() = p.getString("mac", null)
        set(v) = p.edit().putString("mac", v).apply()
    var macName: String?
        get() = p.getString("macName", null)
        set(v) = p.edit().putString("macName", v).apply()
    /** chosen tracker name; null = the one heard last */
    var tracker: String?
        get() = p.getString("tracker", null)
        set(v) = p.edit().putString("tracker", v).apply()
    var demo: Boolean
        get() = p.getBoolean("demo", false)
        set(v) = p.edit().putBoolean("demo", v).apply()
}

/**
 * Keeps the Bluetooth link to the companion radio alive while the phone is in a pocket, stores every
 * report and shows the last one in a notification. Runs as a foreground service, otherwise Android
 * would cut the connection soon after the screen goes off.
 */
class TrackService : Service(), MeshLink.Listener {
    private lateinit var store: Store
    private lateinit var prefs: Prefs
    private lateinit var link: MeshLink
    private val main = Handler(Looper.getMainLooper())
    private var lastShown: Report? = null
    private var demoOn = false
    private var demoStart = 0L
    private var demoSeq = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        store = Store(this)
        prefs = Prefs(this)
        link = MeshLink(this, this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CH_STATUS, getString(R.string.notif_channel_status), NotificationManager.IMPORTANCE_LOW)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_ALARM, getString(R.string.notif_channel_alarm), NotificationManager.IMPORTANCE_HIGH)
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        lastShown = store.last(prefs.tracker)
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIF_STATUS, statusNotification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            } else {
                startForeground(NOTIF_STATUS, statusNotification())
            }
        } catch (e: Exception) {   // no Bluetooth permission yet: the activity asks and starts us again
            Log.w(TAG, "cannot run in the foreground: $e")
        }
        main.removeCallbacks(demoTick)
        demoOn = prefs.demo
        val mac = prefs.mac
        if (demoOn) {
            link.stop()
            startDemo()
        } else if (mac != null) {
            Hub.baseName = prefs.macName
            link.start(mac)
        } else {
            link.stop()
        }
        Hub.changed()
        return START_STICKY
    }

    override fun onDestroy() {
        main.removeCallbacks(demoTick)
        link.stop()
        Hub.linkState = MeshLink.State.OFF
        Hub.changed()
        super.onDestroy()
    }

    // ------------------------------------------------------------------ link

    override fun onLinkState(state: MeshLink.State) {
        Hub.linkState = state
        if (state != MeshLink.State.CONNECTED) Hub.baseMillivolts = null
        updateStatus()
        Hub.changed()
    }

    override fun onBaseName(name: String) {
        Hub.baseName = name
        prefs.macName = name
        updateStatus()
        Hub.changed()
    }

    override fun onBaseBattery(millivolts: Int) {
        Hub.baseMillivolts = millivolts
        Hub.changed()
    }

    override fun onChannelText(text: String, senderTime: Long, snr: Double?) {
        val now = System.currentTimeMillis()
        // the tracker stamps reports with GPS time; believe it unless it is clearly off
        val t = senderTime * 1000
        val time = if (t in MIN_TIME..(now + 10 * 60_000)) t else now
        val r = ReportParser.parse(text, time, snr) ?: return
        if (!store.insert(r)) return
        Hub.revision++
        val chosen = prefs.tracker
        if (chosen == null || chosen == r.tracker) {
            val shown = lastShown
            if (shown == null || r.time >= shown.time) {
                lastShown = r
                updateStatus()
            }
            val fresh = now - r.time < 10 * 60_000
            if (fresh && r.sos) alarm(NOTIF_SOS, getString(R.string.notif_sos, r.tracker))
            if (fresh && r.lowBatt && shown?.lowBatt != true) alarm(NOTIF_LOW, getString(R.string.notif_low, r.tracker))
        }
        Hub.changed()
    }

    // ------------------------------------------------------------------ notifications

    private fun openApp(): PendingIntent = PendingIntent.getActivity(
        this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )

    private fun statusNotification(): Notification {
        val r = lastShown
        val title = if (r == null) getString(R.string.notif_idle) else buildString {
            append(r.tracker).append(" · ").append(Fmt.status(this@TrackService, r))
            r.speedKmh?.let { append(" · ").append(Fmt.kmh(it)) }
            r.battPct?.let { append(" · ").append(it).append('%') }
        }
        val link = when {
            demoOn -> getString(R.string.link_demo)
            else -> Fmt.link(this, Hub.linkState) + (Hub.baseName?.let { " · $it" } ?: "")
        }
        return Notification.Builder(this, CH_STATUS)
            .setSmallIcon(R.drawable.ic_stat_dog)
            .setColor(getColor(R.color.gold_dark))
            .setContentTitle(title)
            .setContentText(link)
            .setWhen(r?.time ?: System.currentTimeMillis())
            .setShowWhen(r != null)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openApp())
            .build()
    }

    private fun updateStatus() {
        getSystemService(NotificationManager::class.java).notify(NOTIF_STATUS, statusNotification())
    }

    private fun alarm(id: Int, text: String) {
        val n = Notification.Builder(this, CH_ALARM)
            .setSmallIcon(R.drawable.ic_stat_dog)
            .setColor(getColor(R.color.red))
            .setContentTitle(text)
            .setCategory(Notification.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(openApp())
            .build()
        getSystemService(NotificationManager::class.java).notify(id, n)
    }

    // ------------------------------------------------------------------ demo: a simulated walk

    private fun startDemo() {
        Hub.linkState = MeshLink.State.OFF
        store.deleteTracker(DEMO_NAME)
        demoStart = System.currentTimeMillis()
        demoSeq = 0
        // an hour of history (a report a minute), then live reports
        for (i in 0 until DEMO_HISTORY) feedDemo(demoStart - (DEMO_HISTORY - i) * 60_000L)
        main.postDelayed(demoTick, 500)
    }

    private val demoTick = object : Runnable {
        override fun run() {
            if (!demoOn) return
            feedDemo(System.currentTimeMillis())
            main.postDelayed(this, DEMO_TICK_MS)
        }
    }

    /** one report in the exact text format of the firmware, so the demo exercises the real parser */
    private fun feedDemo(timeMs: Long) {
        val min = DEMO_HISTORY + (timeMs - demoStart) / 60_000.0
        val (lat, lon) = demoPos(min)
        val (pLat, pLon) = demoPos(min - 0.25)
        val kmh = Geo.distM(pLat, pLon, lat, lon) / 15.0 * 3.6
        val resting = demoResting(min)
        val seq = ++demoSeq
        val status = if (seq == 1) "start" else if (resting) "stoi" else "idzie"
        val pct = (97 - min / 8).toInt()
        val text = String.format(
            Locale.ROOT, "%s: %s %d%% %s 8,5°C %dsat %s%s a%d nr%d https://maps.google.com/?q=%.5f,%.5f",
            DEMO_NAME, status, pct, String.format(Locale.ROOT, "%.2fV", 3.6 + pct * 0.006).replace('.', ','),
            9 + seq % 4, String.format(Locale.ROOT, "%.1fkm/h", if (resting) 0.0 else kmh).replace('.', ','),
            if (!resting && kmh >= 2) " k" + Geo.bearing(pLat, pLon, lat, lon).toInt() else "",
            if (resting) 1 else (kmh * 4).toInt().coerceAtMost(99), seq, lat, lon
        )
        onChannelText(text, timeMs / 1000, -4.0 - seq % 7)
    }

    private fun demoResting(min: Double) = min % 45 in 20.0..25.0

    /** a wandering loop in a forest, about 1 km across; the dog rests for 5 minutes now and then */
    private fun demoPos(minute: Double): Pair<Double, Double> {
        val phase = minute % 45
        val walked = minute - (minute / 45).toInt() * 5 - (if (phase > 25) 5.0 else if (phase > 20) phase - 20 else 0.0)
        val a = walked * 0.085
        val north = 420 * sin(a) + 130 * sin(3.1 * a) + 35 * sin(9.7 * a)
        val east = 560 * (1 - cos(a)) + 150 * sin(2.3 * a) + 30 * cos(8.3 * a)
        return Pair(DEMO_LAT + north / 111_320.0, DEMO_LON + east / (111_320.0 * cos(Math.toRadians(DEMO_LAT))))
    }

    companion object {
        private const val TAG = "TrackDog"
        const val ACTION_STOP = "pl.qbart.trackdog.STOP"
        const val DEMO_NAME = "Demo"
        private const val CH_STATUS = "status"
        private const val CH_ALARM = "alarm"
        private const val NOTIF_STATUS = 1
        private const val NOTIF_SOS = 2
        private const val NOTIF_LOW = 3
        private const val MIN_TIME = 1_700_000_000_000L   // 2023: older = the tracker has no time yet
        private const val DEMO_HISTORY = 60
        private const val DEMO_TICK_MS = 5000L
        const val DEMO_LAT = 52.0756    // forest car park near Otwock, PL
        const val DEMO_LON = 21.3013

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, TrackService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, TrackService::class.java))
        }
    }
}
