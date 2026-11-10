package pl.qbart.trackdog

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** The trail: every report ever received, on the phone only. */
class Store(ctx: Context) : SQLiteOpenHelper(ctx.applicationContext, "trackdog.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE reports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                t INTEGER NOT NULL, tracker TEXT NOT NULL, status TEXT NOT NULL,
                lat REAL, lon REAL, stale INTEGER NOT NULL,
                pct INTEGER, mv INTEGER, temp REAL, sats INTEGER,
                speed REAL, course INTEGER, act INTEGER, seq INTEGER,
                low INTEGER NOT NULL, snr REAL,
                UNIQUE(tracker, t))"""
        )
        db.execSQL("CREATE INDEX reports_t ON reports(t)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    /** false = this report is already stored (the companion delivered it twice) */
    fun insert(r: Report): Boolean {
        val v = ContentValues().apply {
            put("t", r.time); put("tracker", r.tracker); put("status", r.status)
            put("lat", r.lat); put("lon", r.lon); put("stale", if (r.stale) 1 else 0)
            put("pct", r.battPct); put("mv", r.battMv); put("temp", r.tempC); put("sats", r.sats)
            put("speed", r.speedKmh); put("course", r.course); put("act", r.activity); put("seq", r.seq)
            put("low", if (r.lowBatt) 1 else 0); put("snr", r.snr)
        }
        return writableDatabase.insertWithOnConflict("reports", null, v, SQLiteDatabase.CONFLICT_IGNORE) != -1L
    }

    fun last(tracker: String?): Report? = query(
        if (tracker == null) null else "tracker = ?", if (tracker == null) null else arrayOf(tracker), "t DESC", "1"
    ).firstOrNull()

    /** the last report that carries a fresh fix */
    fun lastFix(tracker: String?): Report? = query(
        "stale = 0 AND lat IS NOT NULL" + if (tracker == null) "" else " AND tracker = ?",
        if (tracker == null) null else arrayOf(tracker), "t DESC", "1"
    ).firstOrNull()

    fun between(tracker: String?, fromMs: Long, toMs: Long): List<Report> = query(
        "t >= ? AND t < ?" + if (tracker == null) "" else " AND tracker = ?",
        if (tracker == null) arrayOf(fromMs.toString(), toMs.toString())
        else arrayOf(fromMs.toString(), toMs.toString(), tracker),
        "t ASC", null
    )

    fun trackers(): List<String> {
        val out = ArrayList<String>()
        readableDatabase.rawQuery("SELECT tracker FROM reports GROUP BY tracker ORDER BY MAX(t) DESC", null).use { c ->
            while (c.moveToNext()) out.add(c.getString(0))
        }
        return out
    }

    /** local days that have reports, oldest first, as "yyyy-MM-dd" */
    fun days(tracker: String?): List<String> {
        val out = ArrayList<String>()
        val where = if (tracker == null) "" else " WHERE tracker = ?"
        readableDatabase.rawQuery(
            "SELECT DISTINCT date(t / 1000, 'unixepoch', 'localtime') FROM reports$where ORDER BY 1",
            if (tracker == null) null else arrayOf(tracker)
        ).use { c -> while (c.moveToNext()) out.add(c.getString(0)) }
        return out
    }

    fun count(): Long = readableDatabase.compileStatement("SELECT COUNT(*) FROM reports").simpleQueryForLong()

    fun clear() {
        writableDatabase.delete("reports", null, null)
    }

    fun deleteTracker(tracker: String) {
        writableDatabase.delete("reports", "tracker = ?", arrayOf(tracker))
    }

    private fun query(where: String?, args: Array<String>?, order: String, limit: String?): List<Report> {
        val out = ArrayList<Report>()
        readableDatabase.query("reports", null, where, args, null, null, order, limit).use { c ->
            while (c.moveToNext()) out.add(read(c))
        }
        return out
    }

    private fun read(c: Cursor): Report {
        fun i(n: String) = c.getColumnIndexOrThrow(n)
        fun int(n: String) = if (c.isNull(i(n))) null else c.getInt(i(n))
        fun dbl(n: String) = if (c.isNull(i(n))) null else c.getDouble(i(n))
        return Report(
            time = c.getLong(i("t")), tracker = c.getString(i("tracker")), status = c.getString(i("status")),
            lat = dbl("lat"), lon = dbl("lon"), stale = c.getInt(i("stale")) != 0,
            battPct = int("pct"), battMv = int("mv"), tempC = dbl("temp"), sats = int("sats"),
            speedKmh = dbl("speed"), course = int("course"), activity = int("act"), seq = int("seq"),
            lowBatt = c.getInt(i("low")) != 0, snr = dbl("snr"), id = c.getLong(i("id")),
        )
    }
}
