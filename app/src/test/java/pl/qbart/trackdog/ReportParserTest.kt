package pl.qbart.trackdog

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReportParserTest {
    private val t = 1_800_000_000_000L

    @Test
    fun oldFirmwareWithoutSpeed() {
        val r = ReportParser.parse(
            "TRK1: idzie 93% 4,18V 9,3°C 12sat nr81 https://maps.google.com/?q=52.22970,21.01220", t, -7.5
        )!!
        assertEquals("TRK1", r.tracker)
        assertEquals("idzie", r.status)
        assertEquals(93, r.battPct)
        assertEquals(4180, r.battMv)
        assertEquals(9.3, r.tempC!!, 1e-9)
        assertEquals(12, r.sats)
        assertEquals(81, r.seq)
        assertEquals(52.2297, r.lat!!, 1e-9)
        assertEquals(21.0122, r.lon!!, 1e-9)
        assertTrue(r.hasFix)
        assertNull(r.speedKmh)
        assertNull(r.course)
        assertNull(r.activity)
        assertEquals(-7.5, r.snr!!, 1e-9)
    }

    @Test
    fun speedCourseActivity() {
        val r = ReportParser.parse(
            "TRK1: idzie 80% 4,00V -2,5°C 9sat 12,4km/h k270 a37 nr7 https://maps.google.com/?q=52.10000,-0.50000", t
        )!!
        assertEquals(12.4, r.speedKmh!!, 1e-9)
        assertEquals(270, r.course)
        assertEquals(37, r.activity)
        assertEquals(-2.5, r.tempC!!, 1e-9)
        assertEquals(-0.5, r.lon!!, 1e-9)
        assertEquals(7, r.seq)
    }

    @Test
    fun noFixKeepsLastPositionAsStale() {
        val r = ReportParser.parse(
            "TRK1: brak GPS 55% 3,82V 21,0°C a0 nr12 ost. https://maps.google.com/?q=52.22970,21.01220", t
        )!!
        assertEquals("brak GPS", r.status)
        assertTrue(r.stale)
        assertTrue(r.hasPos)
        assertFalse(r.hasFix)
        assertNull(r.sats)
        assertEquals(0, r.activity)
    }

    @Test
    fun noPositionAtAll() {
        val r = ReportParser.parse("TRK1: start 100% 4,20V 20,0°C nr1", t)!!
        assertEquals("start", r.status)
        assertFalse(r.hasPos)
    }

    @Test
    fun sosAndLowBattery() {
        val r = ReportParser.parse(
            "Pies 🐕: SOS 9% 3,45V 5,0°C 7sat bateria! nr300 https://maps.google.com/?q=52.00000,21.00000", t
        )!!
        assertTrue(r.sos)
        assertTrue(r.lowBatt)
        assertEquals("Pies 🐕", r.tracker)
    }

    @Test
    fun chatIsNotAReport() {
        assertNull(ReportParser.parse("Ala: idziemy na spacer", t))
        assertNull(ReportParser.parse("Ala: stoi pod sklepem", t))
        assertNull(ReportParser.parse("no sender", t))
        assertNull(ReportParser.parse("Ala: OK", t))
    }

    @Test
    fun trailCountsDistanceSpeedAndLostReports() {
        fun rep(min: Int, lat: Double, seq: Int, status: String = "idzie") =
            Report(t + min * 60_000L, "TRK1", status, lat, 21.0, false, 90, 4100, 10.0, 10, null, null, null, seq, false)
        // 0.001 deg of latitude = 111.2 m
        val trail = Trail(listOf(rep(0, 52.000, 1), rep(1, 52.001, 2), rep(2, 52.002, 3), rep(5, 52.002, 6, "stoi")))
        assertEquals(222.4, trail.distanceM, 1.0)
        assertEquals(120_000L, trail.movingMs)
        assertEquals(6.67, trail.maxKmh, 0.1)
        assertEquals(2, trail.lost)
        assertEquals(4, trail.received)
        assertNotNull(trail.points[1].speedKmh)
    }

    @Test
    fun bearingAndDistance() {
        assertEquals(0.0, Geo.bearing(52.0, 21.0, 53.0, 21.0), 0.01)
        assertEquals(90.0, Geo.bearing(0.0, 21.0, 0.0, 22.0), 0.01)
        assertEquals(111_195.0, Geo.distM(52.0, 21.0, 53.0, 21.0), 50.0)
        assertEquals("NE", Geo.cardinal(47.0))
        assertEquals("N", Geo.cardinal(350.0))
    }
}
