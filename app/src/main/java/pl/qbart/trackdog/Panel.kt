package pl.qbart.trackdog

/**
 * Main screen rules (desktop/tdd/panel.py), checked against shared/vectors.json ("panel").
 *
 * Battery, temperature and satellites come from the last report that has them: firmware trk9 sends them in
 * every 10th report only. The data is live when the radio is connected and the last report is fresh; SNR
 * belongs to live reception, so it is not shown for old data.
 */
object Panel {
    const val FRESH_MS = 10 * 60_000L

    /** [battAge] etc.: ms, null = the value is from the last report itself */
    data class Model(
        val live: Boolean, val snr: Double?,
        val batt: Report?, val battAge: Long?,
        val temp: Report?, val tempAge: Long?,
        val sats: Report?, val satsAge: Long?,
    )

    private fun age(r: Report?, last: Report, now: Long): Long? = if (r == null || r.time == last.time) null else now - r.time

    fun build(last: Report?, batt: Report?, temp: Report?, sats: Report?, linkUp: Boolean, now: Long): Model {
        if (last == null) return Model(false, null, null, null, null, null, null, null)
        val live = linkUp && now - last.time < FRESH_MS
        return Model(live, if (live) last.snr else null, batt, age(batt, last, now), temp, age(temp, last, now),
            sats, age(sats, last, now))
    }
}
