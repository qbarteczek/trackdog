# Objętość (mm³) binarnego STL; brak pliku = 0 (puste przecięcie)
import struct, sys, os
p = sys.argv[1]
if not os.path.exists(p) or os.path.getsize(p) < 84: print(0.0); sys.exit()
d = open(p, 'rb').read(); n = struct.unpack('<I', d[80:84])[0]; v = 0.0
for k in range(n):
    a = struct.unpack('<9f', d[84 + k*50 + 12:84 + k*50 + 48])
    x1,y1,z1,x2,y2,z2,x3,y3,z3 = a
    v += (x1*(y2*z3 - y3*z2) - x2*(y1*z3 - y3*z1) + x3*(y1*z2 - y2*z1)) / 6
print(abs(v))
