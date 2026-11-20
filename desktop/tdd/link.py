"""Link to a MeshCore companion radio over Bluetooth LE, a USB cable or TCP (MeshLink.kt in the Android app).

The link only listens: it takes every waiting message out of the companion as soon as it arrives (so the
companion's small queue never fills up) and hands channel texts to the listener. It never transmits
anything over LoRa; like every MeshCore app it sets the radio's clock (the radio takes it only forward).

Runs its own asyncio loop in a thread; the listener is called from that thread.
"""
import asyncio
import logging
import sys
import threading
import time

log = logging.getLogger("trackdog.link")

RETRY_S = 4
HOUSEKEEPING_S = 30
APP_NAME = "TrackDog"

OFF, CONNECTING, PAIRING, CONNECTED, WAITING = "off", "connecting", "pairing", "connected", "waiting"
NOT_SEEN = "not_seen"   # detail: a BLE radio that does not advertise (off, or connected to another device)


class Listener:
    def on_link_state(self, state, detail=""): ...
    def on_base_name(self, name): ...
    def on_base_battery(self, millivolts): ...
    def on_base_position(self, lat, lon): ...
    def on_channel_text(self, text, sender_time, snr): ...


async def paired_radios():
    """[(name, address)] of MeshCore radios paired with this computer, also when they do not advertise now"""
    try:
        if sys.platform == "win32":
            from winrt.windows.devices.bluetooth import BluetoothLEDevice
            from winrt.windows.devices.enumeration import DeviceInformation
            sel = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
            out = []
            for info in await DeviceInformation.find_all_async(sel):
                dev = await BluetoothLEDevice.from_id_async(info.id)
                if dev is not None and (info.name or "").startswith("MeshCore"):
                    a = f"{dev.bluetooth_address:012X}"
                    out.append((info.name, ":".join(a[i:i + 2] for i in range(0, 12, 2))))
            return out
        from dbus_fast import BusType, Message
        from dbus_fast.aio import MessageBus
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        try:
            reply = await bus.call(Message(destination="org.bluez", path="/", member="GetManagedObjects",
                                           interface="org.freedesktop.DBus.ObjectManager"))
        finally:
            bus.disconnect()
        out = []
        for ifaces in reply.body[0].values():
            d = ifaces.get("org.bluez.Device1")
            if not d or not d.get("Paired") or not d["Paired"].value:
                continue
            name = d["Name"].value if "Name" in d else ""
            if name.startswith("MeshCore"):
                out.append((name, d["Address"].value))
        return out
    except Exception as e:  # noqa: BLE001  (no Bluetooth stack, no WinRT): only the scan then
        log.info("paired radios: %r", e)
        return []


async def ble_scan(timeout=8):
    """([(name, address, rssi)] of MeshCore companions advertising over BLE, strongest first,
    number of all BLE devices heard: 0 means a stuck adapter rather than a missing radio)"""
    from bleak import BleakScanner
    from bleak.exc import BleakDBusError
    nus = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    for attempt in range(4):
        try:
            found = await BleakScanner.discover(timeout=timeout, return_adv=True)
            break
        except BleakDBusError as e:   # BlueZ: another program is scanning right now
            if "InProgress" not in str(e) or attempt == 3:
                raise
            await asyncio.sleep(2)
    out = []
    for addr, (dev, adv) in found.items():
        name = adv.local_name or dev.name or ""
        if "meshcore" in name.lower() or nus in [u.lower() for u in adv.service_uuids]:
            out.append((name or addr, addr, adv.rssi))
    return sorted(out, key=lambda f: -f[2]), len(found)


def serial_ports():
    """[(device, description)] of serial ports, USB first; on Linux only USB ones (not the 32 legacy ttyS)"""
    from serial.tools import list_ports
    ports = sorted(list_ports.comports(), key=lambda p: (p.vid is None, p.device))
    if not sys.platform.startswith("win"):
        ports = [p for p in ports if p.vid is not None or "ttyACM" in p.device or "ttyUSB" in p.device]
    return [(p.device, p.description or "") for p in ports]


async def win_pair(addr, pin):
    """Pair with a PIN through WinRT (from MeshCore Desktop).

    bleak on Windows cannot supply a PIN, and a bond made without one is rejected by MeshCore with
    "GATT Insufficient Authentication". Any existing bond is removed first.
    """
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
    from winrt.windows.devices.enumeration import (DevicePairingKinds, DevicePairingProtectionLevel,
                                                   DevicePairingResultStatus)
    num = int(addr.replace(":", ""), 16)
    dev = await BluetoothLEDevice.from_bluetooth_address_async(num)
    if dev is None:
        return "NOT_FOUND"
    pairing = dev.device_information.pairing
    if pairing.is_paired:
        await pairing.unpair_async()
        await asyncio.sleep(3)
        dev = await BluetoothLEDevice.from_bluetooth_address_async(num)
        pairing = dev.device_information.pairing

    def on_request(sender, args):
        if args.pairing_kind == DevicePairingKinds.PROVIDE_PIN:
            args.accept_with_pin(pin)
        else:
            args.accept()

    custom = pairing.custom
    token = custom.add_pairing_requested(on_request)
    try:
        res = await custom.pair_with_protection_level_async(
            DevicePairingKinds.PROVIDE_PIN | DevicePairingKinds.CONFIRM_ONLY,
            DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION)
    finally:
        custom.remove_pairing_requested(token)
    return DevicePairingResultStatus(res.status).name


class Link:
    """device = {"kind": "ble"|"serial"|"tcp", "address": ..., "pin": "123456"}"""

    def __init__(self, listener):
        self.listener = listener
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="link", daemon=True)
        self.thread.start()
        self.task = None
        self.state = OFF

    def start(self, device):
        self.stop()
        self.task = asyncio.run_coroutine_threadsafe(self._run(dict(device)), self.loop)

    def stop(self):
        t, self.task = self.task, None
        if t is not None:
            t.cancel()
            try:
                t.result(timeout=8)
            except BaseException:  # noqa: BLE001  (cancelled, or failed already)
                pass
        self._set(OFF)

    def submit(self, coro):
        """starts a coroutine on the link's loop; returns a concurrent future"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def run(self, coro, timeout=30):
        """runs a coroutine (a scan) on the link's loop and waits for it"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def _set(self, state, detail=""):
        if state != self.state or detail != getattr(self, "detail", ""):
            self.state, self.detail = state, detail
            self.listener.on_link_state(state, detail)

    # ------------------------------------------------------------------ connection

    async def _open(self, dev):
        return await open_radio(dev, lambda: self._set(PAIRING))

    async def _run(self, dev):
        retry = False
        while True:
            mc = None
            try:
                # while the radio stays away the state stays "waiting" (with the reason), not "connecting"
                if not retry:
                    self._set(CONNECTING)
                mc = await self._open(dev)
                if mc is None:
                    raise ConnectionError("no answer from the radio")
                retry = False
                await self._session(mc)
                self._set(WAITING)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001  (out of range, radio off, cable out: try again)
                log.info("link: %r", e)
                retry = True
                self._set(WAITING, NOT_SEEN if dev["kind"] == "ble" and "Failed to connect" in str(e)
                          else str(e) or type(e).__name__)
            finally:
                if mc is not None:
                    try:
                        await asyncio.wait_for(mc.disconnect(), 5)
                    except BaseException:  # noqa: BLE001
                        pass
            await asyncio.sleep(RETRY_S)

    async def _session(self, mc):
        from meshcore import EventType
        lost = asyncio.Event()
        wake = asyncio.Event()

        def on_channel(ev):
            p = ev.payload or {}
            text = p.get("text")
            if text:
                self.listener.on_channel_text(text, int(p.get("sender_timestamp") or 0), p.get("SNR"))

        subs = [mc.subscribe(EventType.CHANNEL_MSG_RECV, on_channel),
                mc.subscribe(EventType.MESSAGES_WAITING, lambda ev: wake.set()),
                mc.subscribe(EventType.DISCONNECTED, lambda ev: lost.set())]
        try:
            info = mc.self_info or {}
            self._set(CONNECTED)
            if info.get("name"):
                self.listener.on_base_name(info["name"])
            lat, lon = info.get("adv_lat"), info.get("adv_lon")
            if lat and lon:
                self.listener.on_base_position(lat, lon)
            await mc.commands.set_time(int(time.time()))
            await self._battery(mc)
            ticks = 0
            failures = 0
            while not lost.is_set():
                ok = await self._drain(mc)
                failures = 0 if ok else failures + 1
                if failures >= 3:
                    raise ConnectionError("the radio does not answer")
                wake.clear()
                waits = [asyncio.create_task(wake.wait()), asyncio.create_task(lost.wait())]
                try:
                    done, _ = await asyncio.wait(waits, timeout=HOUSEKEEPING_S, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for w in waits:
                        w.cancel()
                if not done:   # a lost push or reply must not stop the flow: ask again now and then
                    ticks += 1
                    if ticks % 20 == 0:
                        await self._battery(mc)
        finally:
            for s in subs:
                try:
                    mc.unsubscribe(s)
                except Exception:  # noqa: BLE001
                    pass

    async def _battery(self, mc):
        from meshcore import EventType
        ev = await mc.commands.get_bat()
        if ev is not None and ev.type == EventType.BATTERY:
            mv = (ev.payload or {}).get("level")
            if mv:
                self.listener.on_base_battery(int(mv))

    async def _drain(self, mc):
        """takes every waiting message out of the companion's queue; False = no answer"""
        from meshcore import EventType
        for _ in range(300):
            ev = await mc.commands.get_msg(timeout=8)
            if ev is None:
                return False
            if ev.type == EventType.ERROR:   # a timeout comes as an error with a reason
                return (ev.payload or {}).get("reason") not in ("timeout", "no_event_received")
            if ev.type == EventType.NO_MORE_MSGS:
                return True
        return True


async def open_radio(dev, on_pairing=None):
    """MeshCore connection to dev = {"kind": "ble"|"serial"|"tcp", "address": ..., "pin": "123456"}"""
    from meshcore import MeshCore
    kind, addr = dev["kind"], dev["address"]
    if kind == "serial":
        return await MeshCore.create_serial(addr, 115200, default_timeout=10)
    if kind == "tcp":
        host, _, port = addr.rpartition(":")
        return await MeshCore.create_tcp(host or addr, int(port or 5000), default_timeout=10)
    try:
        mc = await MeshCore.create_ble(addr, default_timeout=10)
        if mc is not None:
            return mc
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001  (not paired, or a stale bond after a firmware update)
        log.info("BLE connect failed: %r", e)
    # not there at all (off, or busy with the phone): pairing would not help
    from bleak import BleakScanner
    if await BleakScanner.find_device_by_address(addr, timeout=6) is None:
        raise ConnectionError("Failed to connect to device")
    # the companion wants a bond made with its PIN
    if on_pairing:
        on_pairing()
    pin = dev.get("pin") or "123456"
    if sys.platform == "win32":
        log.info("pairing through WinRT: %s", await win_pair(addr, pin))
        return await MeshCore.create_ble(addr, default_timeout=10)
    # BlueZ asks the desktop's Bluetooth agent for the PIN (or the radio was paired with bluetoothctl)
    return await MeshCore.create_ble(addr, pin=pin, default_timeout=10)


async def tracker_settings(dev, changes=None):
    """Writes the changed custom vars of a tracker in its configuration window (button 2-6 s), then reads
    them all back: {name: value}. Raises when the tracker cannot be reached or refuses a value."""
    from meshcore import EventType
    mc = await open_radio(dev)
    if mc is None:
        raise ConnectionError("no answer from the tracker")
    try:
        for key, value in (changes or {}).items():
            ev = await mc.commands.set_custom_var(key, str(value))
            if ev is None or ev.type != EventType.OK:
                raise RuntimeError(f"{key}: {(ev.payload if ev is not None else None) or 'no answer'}")
        ev = await mc.commands.get_custom_vars()
        if ev is None or ev.type != EventType.CUSTOM_VARS:
            raise RuntimeError("no answer")
        return dict(ev.payload or {})
    finally:
        try:
            await asyncio.wait_for(mc.disconnect(), 5)
        except BaseException:  # noqa: BLE001
            pass
