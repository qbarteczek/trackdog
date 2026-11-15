r"""Print channel messages received by a MeshCore companion - e.g. tracker reports - on a PC.

    python listen_channel.py ADDRESS [--minutes 5] [--pin 123456]

ADDRESS is a BLE address or a serial port. Note: like the phone app, this takes the messages out of the
radio's queue, so TrackDog on the phone will not get them. Disconnect the phone first (one BLE link at a time).
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshcore_link import EventType, connect  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address")
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--pin", default="123456")
    a = ap.parse_args()
    mc = await connect(a.address, a.pin)
    print("radio:", mc.self_info.get("name"), flush=True)

    def show(ev):
        p = ev.payload
        print(f"{datetime.datetime.now():%H:%M:%S} channel {p.get('channel_idx')} SNR {p.get('SNR')}: {p.get('text')}",
              flush=True)

    mc.subscribe(EventType.CHANNEL_MSG_RECV, show)
    await mc.start_auto_message_fetching()
    await asyncio.sleep(a.minutes * 60)
    await mc.disconnect()


asyncio.run(main())
