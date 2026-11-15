"""Shared connection helper for the TrackDog radio tools (MeshCore companions over BLE or USB).

Needs the `meshcore` Python library (pip install meshcore bleak). On Windows, pairing with a PIN works only
through WinRT; if the MeshCore Desktop app (https://github.com/qbarteczek/meshcore-desktop) is next to
this repository or $MESHCORE_DESKTOP points to it, its `ble_pair` is used. Otherwise pair the radio once in
the system Bluetooth settings (PIN shown on the radio, default 123456).
"""
import os
import sys

from meshcore import MeshCore, EventType  # noqa: F401  (re-exported for the tools)

HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.environ.get("MESHCORE_DESKTOP"),
             os.path.join(HERE, "..", "..", "..", "meshcore-desktop"),
             os.path.join(HERE, "..", "..", "meshcore-desktop")):
    if cand and os.path.isdir(os.path.join(cand, "mcd")):
        sys.path.insert(0, cand)
        break
try:
    from mcd.core import ble_pair, ble_scan  # noqa: E402
except ImportError:
    ble_pair = None

    async def ble_scan(timeout=12):
        """[(name, address, rssi)] of BLE devices whose name starts with MeshCore-"""
        from bleak import BleakScanner
        found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for addr, (dev, adv) in found.items():
            name = adv.local_name or dev.name or ""
            if name.startswith("MeshCore-"):
                out.append((name, addr, adv.rssi))
        return sorted(out, key=lambda f: -f[2])


def is_serial(addr):
    return addr.startswith(("/dev/", "COM"))


async def connect(addr, pin="123456", tries=3):
    """MeshCore connection to a BLE address, or to a serial port (COM5, /dev/ttyACM0)."""
    if is_serial(addr):
        return await MeshCore.create_serial(addr, 115200, default_timeout=10)
    last = None
    for _ in range(tries):
        try:
            return await MeshCore.create_ble(addr)
        except Exception as e:  # noqa: BLE001  (e.g. a stale bond after a firmware update)
            last = e
            if ble_pair is None:
                break
            print("  connection failed:", e, "- pairing with PIN:", await ble_pair(addr, pin), flush=True)
    raise SystemExit(f"cannot connect to {addr}: {last}"
                     + ("" if ble_pair else " (pair it in the system Bluetooth settings first)"))


def ok(ev, what):
    bad = ev is None or ev.type == EventType.ERROR
    print(f"  {'ERROR' if bad else 'ok   '} {what}" + (f": {ev.payload}" if bad and ev else ""), flush=True)
    return not bad
