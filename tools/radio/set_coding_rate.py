r"""Change the LoRa coding rate (CR) of MeshCore companions over BLE; the rest of the radio settings stays.

    python set_coding_rate.py [CR] [NAME ...]

Without names it only scans. NAME is the start of the BLE name after "MeshCore-" (e.g. TRK1).
All radios of one mesh must use the same frequency, bandwidth, SF and CR.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshcore_link import ble_scan, connect  # noqa: E402


async def main():
    cr = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    names = sys.argv[2:]
    found = await ble_scan()
    for n, a, r in found:
        print(f"  {n:28} {a}  {r} dBm")
    for want in names:
        cand = [f for f in found if f[0].startswith("MeshCore-" + want)]
        if not cand:
            print(f"{want}: not visible over BLE")
            continue
        addr = cand[0][1]
        print(f"{want}: connecting to {addr}")
        try:
            mc = await connect(addr)
            si = mc.self_info
            f, bw, sf, old = si["radio_freq"], si["radio_bw"], si["radio_sf"], si["radio_cr"]
            ev = await mc.commands.set_radio(f, bw, sf, cr)
            si = (await mc.commands.send_appstart()).payload
            print(f"  {si.get('name')}: {f} MHz {bw} kHz SF{sf} CR {old} -> {si.get('radio_cr')} ({ev.type.name})")
            await mc.disconnect()
        except (Exception, SystemExit) as e:  # noqa: BLE001
            print(f"  error: {e}")


asyncio.run(main())
