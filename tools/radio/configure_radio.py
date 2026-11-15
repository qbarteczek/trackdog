r"""Set up the TrackDog private channel on a MeshCore radio, and optionally the tracker mode.

    python configure_radio.py ADDRESS --channel-file my-channel.secret [options]
    python configure_radio.py ADDRESS --new-channel my-channel.secret [options]
    python configure_radio.py ADDRESS --show

ADDRESS is a BLE address (AA:BB:CC:DD:EE:FF), a serial port (COM5, /dev/ttyACM0) or "scan".

The tracker and every radio that should hear it (pocket companion, home node) need the same channel name and
secret. --new-channel makes a random 16-byte secret and saves it as hex; keep that file private (outside any
public repository) and use --channel-file with it for the other radios. The channel goes to the slot that
already has this name, otherwise to the first free one.

Options:
    --channel-name NAME     channel name (default Pies, like trk_ch on the tracker)
    --name NAME             device name shown in MeshCore (e.g. TRK1 for the tracker)
    --radio F,BW,SF,CR      radio settings of your mesh, e.g. 869.618,62.5,8,8 (EU narrow); default: unchanged
    --power DBM             transmit power
    --tracker               tracker firmware (meshcore-tracker): tracker=1, trk_ch, interval settings
    --path HEX              trk_path: route of the first copy through repeaters, 1 byte each (e.g. a1); - = zero-hop only
    --move S / --still S / --fast S   intervals when moving / standing / above 7 km/h (defaults 60 / 300 / 30)
    --pin PIN               BLE PIN for pairing (default 123456)
    --show                  only list channels and custom variables
"""
import argparse
import asyncio
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshcore_link import EventType, ble_scan, connect, ok  # noqa: E402


def read_secret(path):
    s = open(path, encoding="ascii").read().strip()
    b = bytes.fromhex(s)
    if len(b) != 16:
        raise SystemExit(f"{path}: the channel secret must be 16 bytes (32 hex digits)")
    return b


async def pick_address(addr, name):
    if addr != "scan":
        return addr
    print("Scanning BLE (12 s)...")
    found = await ble_scan()
    for n, a, r in found:
        print(f"  {n:28} {a}  {r} dBm")
    # a fresh radio is called MeshCore-<BLE address without colons>
    cand = [f for f in found if f[0] == "MeshCore-" + f[1].replace(":", "")
            or (name and f[0] == "MeshCore-" + name)]
    if len(cand) != 1:
        raise SystemExit("cannot tell which radio to use - give its address")
    return cand[0][1]


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--channel-file")
    g.add_argument("--new-channel", metavar="FILE")
    ap.add_argument("--channel-name", default="Pies")
    ap.add_argument("--name")
    ap.add_argument("--radio")
    ap.add_argument("--power", type=int)
    ap.add_argument("--tracker", action="store_true")
    ap.add_argument("--path")
    ap.add_argument("--move", default="60")
    ap.add_argument("--still", default="300")
    ap.add_argument("--fast", default="30")
    ap.add_argument("--pin", default="123456")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    secret = None
    if a.new_channel:
        if os.path.exists(a.new_channel):
            raise SystemExit(f"{a.new_channel} exists - use --channel-file to reuse it")
        secret = secrets.token_bytes(16)
        with open(a.new_channel, "w", encoding="ascii") as f:
            f.write(secret.hex() + "\n")
        print(f"new channel secret saved to {a.new_channel} (keep it private)")
    elif a.channel_file:
        secret = read_secret(a.channel_file)
    elif not a.show:
        raise SystemExit("give --channel-file, --new-channel or --show")

    mc = await connect(await pick_address(a.address, a.name), a.pin)
    si = mc.self_info
    print(f"radio: {si.get('name')}  {si.get('radio_freq')} MHz {si.get('radio_bw')} kHz "
          f"SF{si.get('radio_sf')} CR{si.get('radio_cr')}")
    c = mc.commands
    free, mine = None, None
    for i in range(8):
        ev = await c.get_channel(i)
        if not ev or ev.type == EventType.ERROR:
            break
        nm = ev.payload.get("channel_name", "")
        print(f"  channel {i}: {nm!r}")
        if nm == a.channel_name:
            mine = i
        elif not nm and free is None:
            free = i

    if not a.show:
        if a.name:
            ok(await c.set_name(a.name), f"name {a.name}")
        if a.radio:
            f, bw, sf, cr = (float(x) for x in a.radio.split(","))
            ok(await c.set_radio(f, bw, int(sf), int(cr)), f"radio {a.radio}")
        if a.power is not None:
            ok(await c.set_tx_power(a.power), f"power {a.power} dBm")
        idx = mine if mine is not None else free
        if idx is None:
            raise SystemExit("no free channel slot")
        ok(await c.set_channel(idx, a.channel_name, secret), f"channel {idx} {a.channel_name}")
        if a.tracker:
            ok(await c.set_custom_var("gps", "1"), "GPS on")
            vars_ = {"trk_ch": a.channel_name, "trk_move": a.move, "trk_still": a.still, "trk_fast": a.fast}
            if a.path:
                vars_["trk_path"] = a.path
            for k, v in vars_.items():
                ok(await c.set_custom_var(k, v), f"{k}={v}")
            # last: the tracker falls asleep a minute after BLE disconnects
            ok(await c.set_custom_var("tracker", "1"), "tracker=1 (sleeps a minute after disconnect)")
    ev = await c.get_custom_vars()
    print("  custom variables:", ev.payload if ev else None)
    await mc.disconnect()


asyncio.run(main())
