package pl.qbart.trackdog

import android.app.Activity
import android.app.AlertDialog
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.math.roundToInt

/**
 * Report intervals of the tracker (firmware meshcore-tracker, TrackerMode.cpp) = its custom vars, read and
 * written over Bluetooth while its configuration window is open (button held 2-6 s). The desktop version has
 * the same table (desktop/tdd/trackerset.py); both are checked against shared/vectors.json ("trackerSettings").
 */
object TrackerSettings {
    const val AIR_PER_REPORT_S = 2.4   // 2 copies of ~1.2 s on air

    data class Field(val key: String, val label: Int, val unit: String, val min: Int, val max: Int,
                     val default: Int, val trk8: Boolean = false)

    val FIELDS = listOf(
        Field("trk_fast", R.string.ts_fast, "s", 15, 3600, 20),
        Field("trk_move", R.string.ts_move, "s", 15, 3600, 30),
        Field("trk_still", R.string.ts_still, "s", 15, 3600, 300),
        Field("trk_nap", R.string.ts_nap, "min", 0, 1440, 60, trk8 = true),
        Field("trk_beat", R.string.ts_beat, "min", 15, 1440, 120, trk8 = true),
        Field("trk_idle", R.string.ts_idle, "min", 0, 1440, 15, trk8 = true),
        Field("trk_home_r", R.string.ts_home_r, "m", 30, 5000, 150, trk8 = true),
    )

    /** trk_home for a position (trk10): saved only in the tracker, never in the repository */
    fun homeValue(lat: Double, lon: Double): String = String.format(java.util.Locale.ROOT, "%.6f %.6f", lat, lon)

    fun clamp(key: String, value: Int): Int {
        val f = FIELDS.first { it.key == key }
        return value.coerceIn(f.min, f.max)
    }

    fun airtimePct(intervalS: Int): Int = (AIR_PER_REPORT_S / intervalS * 100).roundToInt()

    /** "k:v,k:v" as the companion sends custom vars */
    fun parseVars(text: String): Map<String, String> = text.split(',').mapNotNull { pair ->
        val i = pair.indexOf(':')
        if (i > 0) pair.substring(0, i) to pair.substring(i + 1) else null
    }.toMap()

    fun isTracker(vars: Map<String, String>) = "tracker" in vars && "trk_move" in vars
}

/** The screen: connect to the chosen tracker, show its intervals, write the changed ones. */
class TrackerSettingsDialog(
    private val act: Activity, mac: String, name: String,
    private val myPosition: () -> Pair<Double, Double>?,   // phone GPS, for "home = my position"
) : MeshLink.Listener {
    private val main = Handler(Looper.getMainLooper())
    private val link = MeshLink(act, this)
    private val status = TextView(act)
    private val air = TextView(act)
    private val edits = LinkedHashMap<String, EditText>()
    private val homeState = TextView(act)
    private val homeSet = android.widget.Button(act)
    private val homeClear = android.widget.Button(act)
    private var vars: Map<String, String> = emptyMap()
    private var pending = 0          // answers still awaited while saving
    private var failed = false
    private var saving = false
    private val dialog: AlertDialog

    init {
        val pad = (16 * act.resources.displayMetrics.density).toInt()
        val box = LinearLayout(act).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad + pad / 2, pad / 2, pad + pad / 2, 0)
        }
        status.setText(R.string.ts_connecting)
        box.addView(status)
        for (f in TrackerSettings.FIELDS) {
            val row = LinearLayout(act).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
            row.addView(TextView(act).apply { setText(f.label) }, LinearLayout.LayoutParams(0, -2, 1f))
            val e = EditText(act).apply {
                inputType = InputType.TYPE_CLASS_NUMBER
                setText(f.default.toString())
                minEms = 3
                gravity = Gravity.END
                isEnabled = false
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun afterTextChanged(s: Editable?) = showAir()
                })
            }
            edits[f.key] = e
            row.addView(e)
            row.addView(TextView(act).apply {
                text = act.getString(when (f.unit) { "s" -> R.string.ts_unit_s; "m" -> R.string.ts_unit_m; else -> R.string.ts_unit_min })
                setPadding(pad / 2, 0, 0, 0)
            })
            box.addView(row)
        }
        val muted = act.getColor(R.color.muted)
        box.addView(TextView(act).apply { setText(R.string.ts_nap_hint); setTextColor(muted) })
        // home (trk10): the "still" alarm and naps depend on it; saved only in the tracker
        homeState.setTextColor(muted)
        homeState.setPadding(0, pad / 2, 0, 0)
        box.addView(homeState)
        val homeRow = LinearLayout(act).apply { orientation = LinearLayout.HORIZONTAL }
        homeSet.setText(R.string.ts_home_set)
        homeClear.setText(R.string.ts_home_clear)
        for (b in listOf(homeSet, homeClear)) { b.isEnabled = false; homeRow.addView(b) }
        homeSet.setOnClickListener {
            val p = myPosition()
            if (p == null) status.setText(R.string.ts_home_nopos) else saveHome(TrackerSettings.homeValue(p.first, p.second))
        }
        homeClear.setOnClickListener { saveHome("-") }
        box.addView(homeRow)
        air.setTextColor(muted)
        air.setPadding(0, pad / 2, 0, 0)
        box.addView(air)
        showAir()
        dialog = AlertDialog.Builder(act).setTitle(act.getString(R.string.ts_title) + " – " + name)
            .setView(ScrollView(act).apply { addView(box) })
            .setPositiveButton(R.string.ts_save, null)
            .setNegativeButton(R.string.no, null)
            .setOnDismissListener { link.stop(); main.removeCallbacksAndMessages(null) }
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).apply { isEnabled = false; setOnClickListener { save() } }
        }
        dialog.show()
        link.start(mac)
        // the window of the tracker may be closed, or the tracker out of range
        main.postDelayed({ if (vars.isEmpty()) status.setText(R.string.ts_failed) }, 45_000)
    }

    private fun value(key: String): Int? = edits[key]?.text?.toString()?.toIntOrNull()?.let { TrackerSettings.clamp(key, it) }

    private fun showAir() {
        val fast = value("trk_fast") ?: return
        val move = value("trk_move") ?: return
        air.text = act.getString(R.string.ts_air, TrackerSettings.airtimePct(fast), TrackerSettings.airtimePct(move))
    }

    private fun saveHome(value: String) {
        saving = true
        failed = false
        pending = 1
        status.setText(R.string.ts_saving)
        link.setCustomVar("trk_home", value)
    }

    private fun save() {
        val changes = TrackerSettings.FIELDS.filter { edits[it.key]!!.isEnabled }.mapNotNull { f ->
            val v = value(f.key) ?: return@mapNotNull null
            if (v.toString() != vars[f.key]) f.key to v.toString() else null
        }
        if (changes.isEmpty()) {
            dialog.dismiss()
            return
        }
        saving = true
        failed = false
        pending = changes.size
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled = false
        status.setText(R.string.ts_saving)
        for ((k, v) in changes) link.setCustomVar(k, v)
    }

    // ------------------------------------------------------------------ MeshLink.Listener

    override fun onLinkState(state: MeshLink.State) {
        when (state) {
            MeshLink.State.CONNECTED -> link.requestCustomVars()
            MeshLink.State.PAIRING -> status.setText(R.string.link_pairing)
            MeshLink.State.CONNECTING -> if (vars.isEmpty()) status.setText(R.string.ts_connecting)
            else -> {}
        }
    }

    override fun onCustomVars(vars: Map<String, String>) {
        if (!TrackerSettings.isTracker(vars)) {
            status.setText(R.string.ts_not_tracker)
            return
        }
        this.vars = vars
        var old = false
        for (f in TrackerSettings.FIELDS) {
            val e = edits[f.key]!!
            val v = vars[f.key]?.toIntOrNull()
            if (v != null) e.setText(TrackerSettings.clamp(f.key, v).toString()) else old = true
            e.isEnabled = v != null
        }
        val hasHome = "trk_home" in vars
        homeSet.isEnabled = hasHome
        homeClear.isEnabled = hasHome
        homeState.text = if (!hasHome) "" else act.getString(if (vars["trk_home"] == "1") R.string.ts_home_on else R.string.ts_home_off)
        val done = if (saving) act.getString(R.string.ts_saved) else ""
        status.text = (done + if (old) " " + act.getString(R.string.ts_old_fw) else "").trim()
        saving = false
        dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.isEnabled = true
    }

    override fun onCommandResult(ok: Boolean) {
        if (!saving || pending == 0) return   // e.g. the clock set while connecting
        if (!ok) failed = true
        if (--pending > 0) return
        if (failed) {
            saving = false
            status.setText(R.string.ts_save_failed)
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled = true
        } else {
            link.requestCustomVars()   // read back what the tracker took
        }
    }

    override fun onBaseName(name: String) {}
    override fun onBaseBattery(millivolts: Int) {}
    override fun onChannelText(text: String, senderTime: Long, snr: Double?) {}
}
