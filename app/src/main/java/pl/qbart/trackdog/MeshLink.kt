package pl.qbart.trackdog

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.util.ArrayDeque
import java.util.UUID

/**
 * Bluetooth link to a MeshCore companion radio (the node carried by the walker).
 *
 * Speaks the companion protocol over the Nordic UART service: one BLE write / notification = one frame.
 * The link only listens: it takes every waiting message out of the companion as soon as it arrives
 * (so the companion's small queue never fills up) and hands channel texts to the listener.
 * It never transmits anything over LoRa.
 *
 * All callbacks of [Listener] come on the main thread.
 */
@SuppressLint("MissingPermission")   // the service starts the link only with BLUETOOTH_CONNECT granted
class MeshLink(ctx: Context, private val listener: Listener) {

    enum class State { OFF, CONNECTING, PAIRING, CONNECTED, WAITING }

    interface Listener {
        fun onLinkState(state: State)
        fun onBaseName(name: String)
        fun onBaseBattery(millivolts: Int)
        /** a text from any channel; [senderTime] in seconds, [snr] in dB */
        fun onChannelText(text: String, senderTime: Long, snr: Double?)
    }

    private val app = ctx.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val adapter = (app.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    private var mac: String? = null
    private var gatt: BluetoothGatt? = null
    private var rx: BluetoothGattCharacteristic? = null
    private var want = false
    private var ready = false                 // notifications on, handshake sent
    private var generation = 0                // invalidates callbacks and timers of older connections
    private val writes = ArrayDeque<ByteArray>()
    private var writing = false
    private var syncing = false
    private var syncStarted = 0L
    private var receiverOn = false

    var state = State.OFF
        private set

    fun start(address: String) {
        stop()
        mac = address
        want = true
        if (!receiverOn) {
            app.registerReceiver(bondReceiver, IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED))
            receiverOn = true
        }
        open(direct = true)
        main.postDelayed(housekeeping, HOUSEKEEPING_MS)
    }

    fun stop() {
        want = false
        generation++
        main.removeCallbacksAndMessages(null)
        if (receiverOn) {
            runCatching { app.unregisterReceiver(bondReceiver) }
            receiverOn = false
        }
        closeGatt()
        setState(State.OFF)
    }

    // ------------------------------------------------------------------ connection

    private fun open(direct: Boolean) {
        val address = mac ?: return
        if (!want) return
        closeGatt()
        if (adapter == null || !adapter.isEnabled) {
            setState(State.WAITING)
            retryLater(RETRY_MS)
            return
        }
        val gen = ++generation
        setState(State.CONNECTING)
        val device = adapter.getRemoteDevice(address)
        // direct = fast, but gives up after ~30 s; autoConnect waits as long as it takes (out of range, radio off)
        gatt = device.connectGatt(app, !direct, Callback(gen), BluetoothDevice.TRANSPORT_LE)
        if (direct) {
            main.postDelayed({ if (gen == generation && !ready && state == State.CONNECTING) open(direct = false) }, DIRECT_TIMEOUT_MS)
        }
    }

    private fun retryLater(ms: Long) {
        val gen = generation
        main.postDelayed({ if (want && gen == generation) open(direct = false) }, ms)
    }

    private fun closeGatt() {
        ready = false
        rx = null
        writes.clear()
        writing = false
        syncing = false
        gatt?.let { g ->
            runCatching { g.disconnect() }
            runCatching { g.close() }
        }
        gatt = null
    }

    private fun setState(s: State) {
        if (state == s) return
        state = s
        listener.onLinkState(s)
    }

    private inner class Callback(val gen: Int) : BluetoothGattCallback() {
        private fun mine() = gen == generation

        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            main.post {
                if (!mine()) return@post
                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    // frames are up to 176 bytes and are not split: ask for a big MTU first
                    if (!g.requestMtu(MTU)) g.discoverServices()
                    main.postDelayed({ if (mine() && rx == null) g.discoverServices() }, 2000)
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    Log.i(TAG, "disconnected, status $status")
                    closeGatt()
                    if (want) {
                        setState(State.WAITING)
                        retryLater(RETRY_MS)
                    }
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            main.post { if (mine() && rx == null) g.discoverServices() }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            main.post {
                if (!mine() || rx != null) return@post
                val svc = g.getService(UART)
                val rxc = svc?.getCharacteristic(UART_RX)
                val txc = svc?.getCharacteristic(UART_TX)
                if (rxc == null || txc == null) {
                    Log.w(TAG, "not a MeshCore companion (no UART service)")
                    closeGatt()
                    setState(State.WAITING)
                    retryLater(RETRY_MS * 3)
                    return@post
                }
                rx = rxc
                // the companion asks for its PIN (shown as a system dialog) before it lets anyone read
                if (g.device.bondState == BluetoothDevice.BOND_BONDED) enableNotifications(g)
                else {
                    setState(State.PAIRING)
                    if (g.device.bondState == BluetoothDevice.BOND_NONE) g.device.createBond()
                }
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            main.post {
                if (!mine()) return@post
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    handshake()
                } else if (g.device.bondState != BluetoothDevice.BOND_BONDED) {
                    setState(State.PAIRING)   // the system is pairing; bondReceiver continues
                } else {
                    Log.w(TAG, "notifications refused, status $status")
                    closeGatt()
                    setState(State.WAITING)
                    retryLater(RETRY_MS)
                }
            }
        }

        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) {
            main.post {
                if (!mine()) return@post
                writing = false
                pump()
            }
        }

        @Deprecated("Deprecated in API 33, still the one called on older systems")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION")
            val bytes = c.value?.clone() ?: return
            main.post { if (mine()) onFrame(bytes) }
        }

        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic, value: ByteArray) {
            val bytes = value.clone()
            main.post { if (mine()) onFrame(bytes) }
        }
    }

    private val bondReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, intent: Intent) {
            val device: BluetoothDevice? = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
            val g = gatt ?: return
            if (device?.address != g.device.address || rx == null || ready) return
            when (intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.BOND_NONE)) {
                BluetoothDevice.BOND_BONDED -> main.postDelayed({ if (gatt === g && !ready) enableNotifications(g) }, 600)
                BluetoothDevice.BOND_NONE -> {   // wrong PIN or cancelled
                    closeGatt()
                    setState(State.WAITING)
                    retryLater(RETRY_MS * 3)
                }
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun enableNotifications(g: BluetoothGatt) {
        val tx = g.getService(UART)?.getCharacteristic(UART_TX) ?: return
        setState(State.CONNECTING)
        g.setCharacteristicNotification(tx, true)
        val d = tx.getDescriptor(CCCD) ?: return
        d.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        g.writeDescriptor(d)
    }

    // ------------------------------------------------------------------ protocol

    private fun handshake() {
        ready = true
        setState(State.CONNECTED)
        send(byteArrayOf(CMD_DEVICE_QUERY, APP_VER))
        send(byteArrayOf(CMD_APP_START, APP_VER, 32, 32, 32, 32, 32, 32) + "TrackDog".toByteArray())
        // the companion may have no clock of its own; it takes the time only if it is not behind
        val now = System.currentTimeMillis() / 1000
        send(byteArrayOf(CMD_SET_DEVICE_TIME) + u32(now))
        send(byteArrayOf(CMD_GET_BATT))
        sync()
    }

    private fun sync() {
        if (!ready || syncing) return
        syncing = true
        syncStarted = System.currentTimeMillis()
        send(byteArrayOf(CMD_SYNC_NEXT))
    }

    private fun onFrame(b: ByteArray) {
        if (b.isEmpty()) return
        when (b[0].toInt() and 0xFF) {
            RESP_SELF_INFO -> if (b.size > 58) listener.onBaseName(cstr(b, 58))
            RESP_BATT -> if (b.size >= 3) listener.onBaseBattery(u16(b, 1))
            RESP_CHANNEL_MSG_V3 -> {
                if (b.size > 11) listener.onChannelText(String(b, 11, b.size - 11), u32(b, 7), b[1] / 4.0)
                next()
            }
            RESP_CHANNEL_MSG -> {
                if (b.size > 8) listener.onChannelText(String(b, 8, b.size - 8), u32(b, 4), null)
                next()
            }
            // private messages and channel data are not ours, but they must leave the queue too
            RESP_CONTACT_MSG, RESP_CONTACT_MSG_V3, RESP_CHANNEL_DATA -> next()
            RESP_NO_MORE -> syncing = false
            PUSH_MSG_WAITING -> sync()
        }
    }

    private fun next() {
        syncStarted = System.currentTimeMillis()
        send(byteArrayOf(CMD_SYNC_NEXT))
    }

    private fun send(frame: ByteArray) {
        writes.add(frame)
        pump()
    }

    @Suppress("DEPRECATION")
    private fun pump() {
        if (writing) return
        val g = gatt ?: return
        val c = rx ?: return
        val frame = writes.poll() ?: return
        c.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        c.value = frame
        writing = g.writeCharacteristic(c)
        if (!writing) {   // stack busy: try again shortly
            writes.addFirst(frame)
            val gen = generation
            main.postDelayed({ if (gen == generation) pump() }, 150)
        }
    }

    /** a lost push or reply must not stop the flow: ask again now and then */
    private val housekeeping = object : Runnable {
        private var ticks = 0
        override fun run() {
            if (!want) return
            if (ready) {
                if (syncing && System.currentTimeMillis() - syncStarted > 8000) syncing = false
                sync()
                if (++ticks % 20 == 0) send(byteArrayOf(CMD_GET_BATT))
            }
            main.postDelayed(this, HOUSEKEEPING_MS)
        }
    }

    companion object {
        private const val TAG = "TrackDog"
        val UART: UUID = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
        private val UART_RX: UUID = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e")   // phone -> companion
        private val UART_TX: UUID = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e")   // companion -> phone
        private val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        private const val MTU = 247
        private const val DIRECT_TIMEOUT_MS = 20_000L
        private const val RETRY_MS = 4_000L
        private const val HOUSEKEEPING_MS = 30_000L

        // companion protocol (MeshCore examples/companion_radio/MyMesh.cpp)
        private const val APP_VER: Byte = 3
        private const val CMD_APP_START: Byte = 1
        private const val CMD_SET_DEVICE_TIME: Byte = 6
        private const val CMD_SYNC_NEXT: Byte = 10
        private const val CMD_GET_BATT: Byte = 20
        private const val CMD_DEVICE_QUERY: Byte = 22
        private const val RESP_SELF_INFO = 5
        private const val RESP_CONTACT_MSG = 7
        private const val RESP_CHANNEL_MSG = 8
        private const val RESP_NO_MORE = 10
        private const val RESP_BATT = 12
        private const val RESP_CONTACT_MSG_V3 = 16
        private const val RESP_CHANNEL_MSG_V3 = 17
        private const val RESP_CHANNEL_DATA = 27
        private const val PUSH_MSG_WAITING = 0x83

        private fun u16(b: ByteArray, i: Int) = (b[i].toInt() and 0xFF) or ((b[i + 1].toInt() and 0xFF) shl 8)
        private fun u32(b: ByteArray, i: Int): Long =
            (b[i].toLong() and 0xFF) or ((b[i + 1].toLong() and 0xFF) shl 8) or
                ((b[i + 2].toLong() and 0xFF) shl 16) or ((b[i + 3].toLong() and 0xFF) shl 24)
        private fun u32(v: Long) = byteArrayOf(v.toByte(), (v shr 8).toByte(), (v shr 16).toByte(), (v shr 24).toByte())
        private fun cstr(b: ByteArray, from: Int): String {
            var end = from
            while (end < b.size && b[end] != 0.toByte()) end++
            return String(b, from, end - from)
        }
    }
}
