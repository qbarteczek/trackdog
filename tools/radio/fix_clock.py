"""Check (and on request fix) the clock of a MeshCore companion over BLE or USB.

    python fix_clock.py ADDRESS [--fix] [--pin 123456]
    python fix_clock.py /dev/ttyACM0 [--fix]        # over USB, e.g. a home node in a server

Without --fix it only reports: device time vs computer time, number of contacts with lastmod in the future.
With --fix: backs up the contacts to a JSON file in the current folder, rewrites contacts whose lastmod is in
the future with lastmod = now - 60, reboots (to save the contacts) and sets the time. Why: at boot a companion
sets its clock to max(contact lastmod) + 1 and refuses to go back in time, so a clock that was once too fast
survives every reboot. Wrong clocks make tracker reports show up with wrong times.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshcore_link import EventType, connect  # noqa: E402

TOL = 120   # s - a bigger difference is a clock error


async def write_lastmod(mc, c, lastmod):
    """CMD_ADD_UPDATE_CONTACT like the meshcore library, but with the optional lastmod at the end of the frame
    (the library does not send it, and without it the firmware stores its own - wrong - time)."""
    plen = c["out_path_len"]
    plen = 255 if plen == -1 else plen | (c.get("out_path_hash_mode", 0) << 6)
    path = c["out_path"] + "0" * (128 - len(c["out_path"]))
    nm = c["adv_name"].encode()[:32]
    data = (b"\x09" + bytes.fromhex(c["public_key"]) + c["type"].to_bytes(1, "little") + c["flags"].to_bytes(1, "little")
            + int(plen).to_bytes(1, "little") + bytes.fromhex(path) + nm + b"\0" * (32 - len(nm))
            + c["last_advert"].to_bytes(4, "little")
            + int(c["adv_lat"] * 1e6).to_bytes(4, "little", signed=True) + int(c["adv_lon"] * 1e6).to_bytes(4, "little", signed=True)
            + int(lastmod).to_bytes(4, "little"))
    return await mc.commands.send(data, [EventType.OK, EventType.ERROR])


async def status(mc):
    ev = await mc.commands.get_time()
    dev = ev.payload.get("time") if ev and ev.type != EventType.ERROR else None
    await mc.commands.get_contacts()
    now = int(time.time())
    future = [c for c in mc.contacts.values() if c.get("lastmod", 0) > now + TOL]
    return dev, now, future


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fix = "--fix" in sys.argv
    pin = sys.argv[sys.argv.index("--pin") + 1] if "--pin" in sys.argv else "123456"
    if not args:
        sys.exit(__doc__)
    addr = args[0]
    mc = await connect(addr, pin)
    name = mc.self_info.get("name")
    dev, now, future = await status(mc)
    off = (dev - now) if dev else None
    print(f"{name}: clock {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dev)) if dev else '?'}"
          f" (difference {off:+d} s), contacts {len(mc.contacts)}, with lastmod in the future: {len(future)}")
    if not fix or (off is not None and abs(off) <= TOL and not future):
        if fix:
            print("  clock is fine - nothing to do")
        await mc.disconnect()
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(os.getcwd(), f"contacts-{name.encode('ascii', 'ignore').decode() or 'mc'}-{stamp}.json")
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(list(mc.contacts.values()), f, ensure_ascii=False, indent=1)
    print("  contacts backup:", bak)
    for rnd in range(3):
        bad = [c for c in mc.contacts.values() if c.get("lastmod", 0) > int(time.time()) + TOL]
        if not bad:
            break
        for c in bad:
            ev = await write_lastmod(mc, c, int(time.time()) - 60)
            if ev is None or ev.type == EventType.ERROR:
                print("  ERROR writing contact", c.get("adv_name"), ev.payload if ev else "")
        await mc.commands.get_contacts()
        print(f"  round {rnd + 1}: fixed {len(bad)} contacts")
    ev = await mc.commands.set_time(int(time.time()))
    print("  set time:", ev.type.name if ev else "no answer")
    print("  reboot (saves the contacts)...")
    try:
        await mc.commands.reboot()
    except Exception:  # noqa: BLE001
        pass
    await mc.disconnect()
    await asyncio.sleep(15)
    mc = await connect(addr, pin)
    ev = await mc.commands.set_time(int(time.time()))
    dev, now, future = await status(mc)
    print(f"  after reboot: difference {(dev - now) if dev else '?'} s, contacts in the future: {len(future)},"
          f" set time: {ev.type.name if ev else '?'}")
    await mc.disconnect()


asyncio.run(main())
