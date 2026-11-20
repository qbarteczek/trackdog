"""GPX: the trail for map apps (the same file as Maps.gpx in the Android app) and back."""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .report import MAX_GAP_MS, ST_MOVING, ST_STILL, Report


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gpx(name, points):
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           '<gpx version="1.1" creator="TrackDog" xmlns="http://www.topografix.com/GPX/1/1">\n',
           f"<trk><name>{_xml(name)}</name>\n<trkseg>\n"]
    prev = None
    for p in points:
        r = p.r
        # a long silence starts a new segment, so the map does not draw a straight line across it
        if prev is not None and r.time - prev.time > MAX_GAP_MS:
            out.append("</trkseg>\n<trkseg>\n")
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r.time / 1000))
        out.append(f'<trkpt lat="{r.lat:.6f}" lon="{r.lon:.6f}"><time>{iso}</time>')
        if p.speed_kmh is not None:
            out.append(f"<extensions><speed>{p.speed_kmh / 3.6:.2f}</speed></extensions>")
        out.append("</trkpt>\n")
        prev = r
    out.append("</trkseg></trk>\n</gpx>\n")
    return "".join(out)


def tracker_from_name(name):
    """'trackdog-TRK1-2026-11-12' (the name TrackDog gives its files) -> 'TRK1'"""
    m = re.match(r"^trackdog-(.+)-\d{4}-\d{2}-\d{2}$", name or "")
    return m.group(1) if m else None


def read_gpx(path, tracker=None):
    """(tracker name found in the file or None, [Report]) from the track points of a GPX file.

    A GPX file carries only position, time and maybe speed: battery, satellites and report numbers are
    lost, so the database exported from the phone is the better way to move trails between devices.
    """
    root = ET.parse(path).getroot()
    ns = {"g": root.tag[1:root.tag.index("}")]} if root.tag.startswith("{") else {"g": ""}
    q = (lambda tag: f"g:{tag}") if ns["g"] else (lambda tag: tag)
    found = None
    name = root.find(f"{q('trk')}/{q('name')}", ns)
    if name is not None:
        found = tracker_from_name((name.text or "").strip())
    who = tracker or found or "GPX"
    out = []
    for pt in root.iter(f"{{{ns['g']}}}trkpt" if ns["g"] else "trkpt"):
        t = pt.find(q("time"), ns)
        if t is None or not t.text:
            continue
        ts = datetime.fromisoformat(t.text.strip().replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        speed = None
        for el in pt.iter():
            if el.tag.split("}")[-1] == "speed" and el.text:
                speed = float(el.text) * 3.6
        out.append(Report(time=int(ts.timestamp() * 1000), tracker=who,
                          status=ST_MOVING if speed is None or speed >= 1 else ST_STILL,
                          lat=float(pt.get("lat")), lon=float(pt.get("lon")), speed_kmh=speed))
    return found, out
