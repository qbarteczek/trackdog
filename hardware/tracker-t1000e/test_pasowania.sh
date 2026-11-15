#!/bin/bash
# Symulacja geometryczna pasowania obudowy: przecięcia brył (OpenSCAD 2025+ z silnikiem Manifold).
# Użycie: bash test_pasowania.sh   (wyniki STL kolizji w katalogu tymczasowym)
cd "$(dirname "$0")"
T=$(mktemp -d)
for t in listwa_zapieta listwa_w_tunelu karta piny okno_listwy; do
    out=$(openscad --backend=Manifold --export-format=binstl -D 'czesc="nic"' -D "test=\"$t\"" -o "$T/$t.stl" test_pasowania.scad 2>&1)
    if echo "$out" | grep -qi 'empty'; then echo "$t: brak kolizji"; continue; fi
    python3 -I - "$T/$t.stl" "$t" <<'PY'
import sys, struct
d = open(sys.argv[1], 'rb').read()
n = struct.unpack('<I', d[80:84])[0]
v = [struct.unpack('<3f', d[84 + i*50 + 12 + 12*k:84 + i*50 + 24 + 12*k]) for i in range(n) for k in range(3)]
T = [v[i:i+3] for i in range(0, len(v), 3)]
vol = abs(sum((a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6 for a, b, c in T))
r = lambda i: (min(p[i] for p in v), max(p[i] for p in v))
(x0, x1), (y0, y1), (z0, z1) = r(0), r(1), r(2)
print(f"{sys.argv[2]}: KOLIZJA {vol:.2f} mm³  x {x0:.2f}..{x1:.2f}  y {y0:.2f}..{y1:.2f}  z {z0:.2f}..{z1:.2f}")
PY
done
