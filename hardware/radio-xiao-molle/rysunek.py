"""Zwymiarowany zarys obudowy (widok z przodu bez wieka + przekrój warstw). Wymiary z obudowa.scad.
Użycie: python rysunek.py [ścieżka do openscad]  ->  podglad/zarys.png"""
import json, os, re, subprocess, sys, tempfile
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch, Polygon

tu = os.path.dirname(os.path.abspath(__file__))
os_exe = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('OPENSCAD', 'openscad')
echo = os.path.join(tempfile.gettempdir(), 'obudowa-wymiary.echo')
subprocess.run([os_exe, '-D', 'czesc="nic"', '-o', echo, os.path.join(tu, 'obudowa.scad')], capture_output=True)
W = json.loads(re.search(r'WYMIARY=(\{.*\})', open(echo, encoding='utf-8').read()).group(1).replace('\\"', '"'))

fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 9.5), gridspec_kw={'width_ratios': [1.15, 1]})
SZ, CZ = '#5b6b73', '#c0392b'

def wym(ax, p1, p2, txt, off=0, pion=False):
    (x1, y1), (x2, y2) = p1, p2
    if pion:
        ax.annotate('', (x1 + off, y1), (x1 + off, y2), arrowprops=dict(arrowstyle='<->', color=CZ, lw=0.9))
        ax.text(x1 + off - 1, (y1 + y2)/2, txt, rotation=90, ha='right', va='center', color=CZ, fontsize=9)
    else:
        ax.annotate('', (x1, y1 + off), (x2, y1 + off), arrowprops=dict(arrowstyle='<->', color=CZ, lw=0.9))
        ax.text((x1 + x2)/2, y1 + off + 0.8, txt, ha='center', va='bottom', color=CZ, fontsize=9)

# --- widok z przodu (bez wieka) ---
zx, zy, s = W['zew_x'], W['zew_y'], W['scianka']
a1.add_patch(FancyBboxPatch((0, 0), zx, zy, boxstyle='round,pad=0,rounding_size=2', fc='#dfe6e9', ec=SZ, lw=1.5))
f = W['faza']; ix, iy = zx - 2*s, zy - 2*s
a1.add_patch(Polygon([(s+f, s), (s+ix-f, s), (s+ix, s+f), (s+ix, s+iy-f), (s+ix-f, s+iy), (s+f, s+iy), (s, s+iy-f), (s, s+f)],
                     fc='white', ec=SZ, lw=1))
# bloczki MOLLE z tyłu (przerywane)
for i in range(2):
    a1.add_patch(Rectangle((0, W['molle_y0'] + i*(W['pas_szer'] + W['bloczek'] + 1)), zx, W['bloczek'],
                           fc='none', ec='#7f8c8d', ls='--', lw=0.8))
a1.add_patch(Rectangle((zx/2 - W['listwa_sz']/2, W['molle_y0'] - 6), W['listwa_sz'], W['listwa_dl'] - 6,
                       fc='none', ec='black', ls=':', lw=1))
bx, by, bw, bh, bz = W['bat']
a1.add_patch(Rectangle((bx, by), bw, bh, fc='#4a69bd', alpha=0.85))
a1.text(bx + bw/2, by + bh/2, f'bateria\n{bw:g} × {bh:g} × {bz:g} mm\n(203450, 4000 mAh)', ha='center', va='center', color='white', fontsize=10)
a1.add_patch(Rectangle((s, W['zebro_y']), ix, W['zebro_gr'], fc='#95a5a6'))
a1.add_patch(Rectangle((s, W['zebro_y'] - 0.3), W['kabel'], W['zebro_gr'] + 0.6, fc='white'))
a1.text(s + W['kabel']/2, W['zebro_y'] + 3.2, 'przewody', ha='center', fontsize=7.5)
kx, ky, kw, kh, kz = W['kit']
a1.add_patch(Rectangle((kx, ky), kw, kh, fc='#27ae60'))
a1.text(kx + kw/2, ky + kh/2, 'XIAO nRF52840\n+ Wio-SX1262\n23 × 22 × 8', ha='center', va='center', color='white', fontsize=8.5)
uy, uz, uw, uh = W['usb']
a1.add_patch(Rectangle((zx - s, uy - uw/2), s, uw, fc='#2d3436'))
a1.annotate('USB-C\n(wnęka 13,5 × 8)', (zx, uy), (zx + 6, uy - 14), fontsize=9, arrowprops=dict(arrowstyle='->'))
sx, sz_, sd = W['sma']
a1.add_patch(Rectangle((sx - sd/2, zy - s), sd, s, fc='#f1c40f', ec='k', lw=0.5))
a1.annotate('SMA (antena)\nØ 6,6', (sx, zy), (sx - 4, zy + 8), fontsize=9, arrowprops=dict(arrowstyle='->'))
for x in (W['wkret_xy'], zx - W['wkret_xy']):
    for y in (W['wkret_xy'], zy - W['wkret_xy']):
        a1.add_patch(Circle((x, y), 0.8, fc='k'))
wym(a1, (0, 0), (zx, 0), f'{zx:g}', off=-7)
wym(a1, (0, 0), (0, zy), f'{zy:g}', off=-4, pion=True)
a1.text(zx/2, -14, 'listwa (kropki) i bloczki MOLLE z tyłu (kreski)\nwkręty M2 × 10 w narożach', ha='center', fontsize=8.5, color='#555')
a1.set_xlim(-14, zx + 22); a1.set_ylim(-20, zy + 16); a1.set_aspect('equal'); a1.axis('off')
a1.set_title('Widok z przodu, bez wieka', fontsize=12)

# --- przekrój warstw (w poprzek, przez bloczek) ---
t, m, tw, tsz = W['tyl_wys'], W['mostek'], W['tunel_wys'], W['tunel_sz']
d, iz, wg = W['dno'], W['in_z'], W['wieko_gr']
x0 = 0
a2.add_patch(Rectangle((x0, 0), zx, t, fc='#dfe6e9', ec=SZ))                    # bloczek
a2.add_patch(Rectangle((zx/2 - tsz/2, m), tsz, tw, fc='white', ec=SZ))           # tunel
a2.add_patch(Rectangle((zx/2 - W['listwa_sz']/2, m + 0.4), W['listwa_sz'], W['listwa_gr'], fc='black'))
a2.add_patch(Rectangle((x0, t), zx, d, fc='#dfe6e9', ec=SZ))                     # dno
a2.add_patch(Rectangle((x0, t + d), s, iz, fc='#dfe6e9', ec=SZ)); a2.add_patch(Rectangle((zx - s, t + d), s, iz, fc='#dfe6e9', ec=SZ))
a2.add_patch(Rectangle((bx, t + d), bw, bz, fc='#4a69bd', alpha=0.85))
a2.add_patch(Rectangle((x0, t + d + iz), zx, wg, fc='#f39c12', ec='#b9770e'))     # wieko
a2.add_patch(Rectangle((-8, -2), zx + 16, 2, fc='#556b2f', alpha=0.6))          # kamizelka
a2.text(zx + 9, -1, 'kamizelka / plecak', va='center', fontsize=9)
a2.text(zx/2, t + d + bz/2, 'bateria', ha='center', va='center', color='white')
a2.text(zx/2, t + d + iz + wg/2, 'wieko 2,2', ha='center', va='center', fontsize=8.5)
a2.text(zx/2, m + tw/2 + 0.2, 'listwa', ha='center', va='center', color='white', fontsize=8)
wym(a2, (0, 0), (0, t), f'tył MOLLE {t:g}', off=-3, pion=True)
wym(a2, (0, t), (0, t + d + iz + wg), f'korpus + wieko {d + iz + wg:g}', off=-3, pion=True)
wym(a2, (zx, 0), (zx, t + d + iz + wg), f'razem {t + d + iz + wg:g} mm', off=12, pion=True)
wym(a2, (0, 0), (zx, 0), f'{zx:g}', off=-6)
a2.text(zx/2, -12, f'bloczek: mostek {m:g} mm | tunel {tsz:g} × {tw:g} na listwę {W["listwa_sz"]:g} × {W["listwa_gr"]:g}\n'
        f'nad tunelem miejsce na taśmę PALS ({W["pas_grub"]:g} mm) między bloczkami', ha='center', fontsize=8.5, color='#555')
a2.set_xlim(-26, zx + 30); a2.set_ylim(-18, t + d + iz + wg + 8); a2.set_aspect('equal'); a2.axis('off')
a2.set_title('Przekrój w poprzek (przez bloczek)', fontsize=12)

fig.suptitle('Obudowa radia XIAO nRF52840 + Wio-SX1262 z baterią 4000 mAh, mocowanie MOLLE (1 listwa)', fontsize=13)
plt.tight_layout()
plt.savefig(os.path.join(tu, 'podglad', 'zarys.png'), dpi=110)
print('podglad/zarys.png')
