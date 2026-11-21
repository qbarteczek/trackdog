package pl.qbart.trackdog

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.io.File

/** The trail: every report ever received, on the phone only. */
class Store(ctx: Context) : SQLiteOpenHelper(ctx.applicationContext, "trackdog.db", null, 2) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(SCHEMA)
        db.execSQL("CREATE INDEX reports_t ON reports(t)")
    }

    /** version 2 (firmware trk10): HDOP, posture, minutes without motion */
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) for ((name, kind) in NEW_COLS) db.execSQL("ALTER TABLE reports ADD COLUMN $name $kind")
    }

    /** false = this report is already stored (the companion delivered it twice) */
    fun insert(r: Report): Boolean =
        writableDatabase.insertWithOnConflict("reports", null, values(r), SQLiteDatabase.CONFLICT_IGNORE) != -1L

    private fun values(r: Report) = ContentValues().apply {
        put("t", r.time); put("tracker", r.tracker); put("status", r.status)
        put("lat", r.lat); put("lon", r.lon); put("stale", if (r.stale) 1 else 0)
        put("pct", r.battPct); put("mv", r.battMv); put("temp", r.tempC); put("sats", r.sats)
        put("speed", r.speedKmh); put("course", r.course); put("act", r.activity); put("seq", r.seq)
        put("low", if (r.lowBatt) 1 else 0); put("snr", r.snr)
        put("hdop", r.hdop); put("pos", r.posture); put("idle", r.idleMin)
    }

    fun last(tracker: String?): Report? = query(
        if (tracker == null) null else "tracker = ?", if (tracker == null) null else arrayOf(tracker), "t DESC", "1"
    ).firstOrNull()

    /** the last report that carries a fresh fix */
    fun lastFix(tracker: String?): Report? = query(
        "stale = 0 AND lat IS NOT NULL" + if (tracker == null) "" else " AND tracker = ?",
        if (tracker == null) null else arrayOf(tracker), "t DESC", "1"
    ).firstOrNull()

    /** the last report that has [column] (pct, temp, sats): firmware trk9 sends them in every 10th report */
    fun lastWith(tracker: String?, column: String): Report? {
        require(column in setOf("pct", "temp", "sats"))
        return query(
            "$column IS NOT NULL" + if (tracker == null) "" else " AND tracker = ?",
            if (tracker == null) null else arrayOf(tracker), "t DESC", "1"
        ).firstOrNull()
    }

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

    /**
     * A standalone copy of the table in [file], for the computer (TrackDog desktop) or another phone.
     * The same table as the desktop's store.py, so either side merges the other's file as it is.
     */
    fun exportTo(file: File) {
        file.delete()
        val out = SQLiteDatabase.openOrCreateDatabase(file, null)
        try {
            out.execSQL(SCHEMA)
            out.beginTransaction()
            try {
                for (r in query(null, null, "t ASC", null)) out.insertWithOnConflict("reports", null, values(r), SQLiteDatabase.CONFLICT_IGNORE)
                out.setTransactionSuccessful()
            } finally {
                out.endTransaction()
            }
        } finally {
            out.close()
        }
    }

    /** merges a TrackDog database from [file]; (new reports, reports in the file) */
    fun mergeFrom(file: File): Pair<Int, Int> {
        val src = SQLiteDatabase.openDatabase(file.path, null, SQLiteDatabase.OPEN_READONLY)
        val rows = try {
            val out = ArrayList<Report>()
            src.query("reports", null, null, null, null, null, "t ASC").use { c -> while (c.moveToNext()) out.add(read(c)) }
            out
        } finally {
            src.close()
        }
        val db = writableDatabase
        var added = 0
        db.beginTransaction()
        try {
            for (r in rows) if (db.insertWithOnConflict("reports", null, values(r), SQLiteDatabase.CONFLICT_IGNORE) != -1L) added++
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return Pair(added, rows.size)
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

    companion object {
        /** the same table in the desktop version (desktop/tdd/store.py) */
        const val SCHEMA = """CREATE TABLE reports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                t INTEGER NOT NULL, tracker TEXT NOT NULL, status TEXT NOT NULL,
                lat REAL, lon REAL, stale INTEGER NOT NULL,
                pct INTEGER, mv INTEGER, temp REAL, sats INTEGER,
                speed REAL, course INTEGER, act INTEGER, seq INTEGER,
                low INTEGER NOT NULL, snr REAL,
                hdop REAL, pos TEXT, idle INTEGER,
                UNIQUE(tracker, t))"""
        val NEW_COLS = listOf("hdop" to "REAL", "pos" to "TEXT", "idle" to "INTEGER")
    }

    private fun read(c: Cursor): Report {
        fun i(n: String) = c.getColumnIndexOrThrow(n)
        fun int(n: String) = if (c.isNull(i(n))) null else c.getInt(i(n))
        fun dbl(n: String) = if (c.isNull(i(n))) null else c.getDouble(i(n))
        fun opt(n: String) = c.getColumnIndex(n).takeIf { it >= 0 && !c.isNull(it) }   // older files lack trk10 columns
        return Report(
            time = c.getLong(i("t")), tracker = c.getString(i("tracker")), status = c.getString(i("status")),
            lat = dbl("lat"), lon = dbl("lon"), stale = c.getInt(i("stale")) != 0,
            battPct = int("pct"), battMv = int("mv"), tempC = dbl("temp"), sats = int("sats"),
            speedKmh = dbl("speed"), course = int("course"), activity = int("act"), seq = int("seq"),
            lowBatt = c.getInt(i("low")) != 0, snr = dbl("snr"), id = c.getLong(i("id")),
            hdop = opt("hdop")?.let { c.getDouble(it) }, posture = opt("pos")?.let { c.getString(it) },
            idleMin = opt("idle")?.let { c.getInt(it) },
        )
    }
}
