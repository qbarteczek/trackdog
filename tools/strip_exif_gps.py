"""Remove the GPS position from the EXIF metadata of JPEG photos - without recompressing the image.

    python strip_exif_gps.py PHOTO.jpg [...]         # fixes the files in place
    python strip_exif_gps.py --check FOLDER          # only lists photos that carry a GPS position

Run it on photos of the dog, the harness or the enclosure before you publish them: a photo taken at home
carries the home position. It zeroes the GPS block of the EXIF segment (entries and their values); the rest of
the metadata (date, orientation, camera) stays.
"""
import os
import struct
import sys

SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def _exif_segments(data):
    """offsets of the TIFF headers of all Exif APP1 segments"""
    out = []
    if data[:2] != b'\xff\xd8':
        return out
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker in (0xD9, 0xDA):
            break
        length = struct.unpack('>H', data[pos + 2:pos + 4])[0]
        if marker == 0xE1 and data[pos + 4:pos + 10] == b'Exif\0\0':
            out.append((pos + 10, pos + 2 + length))
        pos += 2 + length
    return out


def strip_gps(data):
    """returns the JPEG without GPS data, or None when there is nothing to remove"""
    buf = bytearray(data)
    changed = False
    for tiff, end in _exif_segments(data):
        bo = '<' if buf[tiff:tiff + 2] == b'II' else '>'
        ifd0 = tiff + struct.unpack(bo + 'I', buf[tiff + 4:tiff + 8])[0]
        n = struct.unpack(bo + 'H', buf[ifd0:ifd0 + 2])[0]
        for i in range(n):
            e = ifd0 + 2 + 12 * i
            tag = struct.unpack(bo + 'H', buf[e:e + 2])[0]
            if tag != 0x8825:
                continue
            gps = tiff + struct.unpack(bo + 'I', buf[e + 8:e + 12])[0]
            m = struct.unpack(bo + 'H', buf[gps:gps + 2])[0]
            if m == 0 or gps + 2 + 12 * m > end:
                continue
            for j in range(m):
                g = gps + 2 + 12 * j
                typ, count = struct.unpack(bo + 'HI', buf[g + 2:g + 8])
                size = SIZES.get(typ, 1) * count
                if size > 4:   # value stored elsewhere in the segment
                    off = tiff + struct.unpack(bo + 'I', buf[g + 8:g + 12])[0]
                    if off + size <= end:
                        buf[off:off + size] = bytes(size)
            buf[gps:gps + 2 + 12 * m + 4] = bytes(2 + 12 * m + 4)   # an empty GPS block
            changed = True
    return bytes(buf) if changed else None


def has_gps(data):
    return strip_gps(data) is not None


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--check':
        for d, _, files in os.walk(args[1]):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg')):
                    p = os.path.join(d, f)
                    if has_gps(open(p, 'rb').read()):
                        print('GPS:', p)
    else:
        for p in args:
            new = strip_gps(open(p, 'rb').read())
            if new is not None:
                open(p, 'wb').write(new)
                print('GPS removed:', p)
