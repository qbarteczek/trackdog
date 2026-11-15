#!/usr/bin/env python3
"""Animacja MES grotu listwy: ściskanie ramion od 0 do pełnego ugięcia i z powrotem, stara (v1) i nowa (v2)
wersja obok siebie, PETG. Sprężystość liniowa - jedno rozwiązanie na wersję, klatki to jego przeskalowanie.

Uruchom:  ~/.local/opt/fem-venv/bin/python fem_animacja.py   (wynik: podglad/fem-grot-animacja.gif i .mp4)
"""
import os, shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.collections import PolyCollection
from fem_listwa import WARIANTY, MATERIALY, siatka, licz

TU = os.path.dirname(os.path.abspath(__file__))
E, nu, eps_raz, eps_wiele = MATERIALY['PETG']
SKALA_POKAZ = 2.0      # przemieszczenia na rysunku x2, żeby ugięcie było dobrze widać
N = 36                 # klatek na pół cyklu

dane = []
for nazwa, p in WARIANTY.items():
    mesh, y0, gw = siatka(p)
    u, ib, F, e1, e_nas = licz(p, E, nu, mesh, y0, gw)
    fac = mesh.facets_satisfying(lambda x: x[2] > p['t'] - 1e-6)
    f = mesh.facets[:, fac]
    yc = mesh.p[1, mesh.t].mean(axis=0)
    e_pokaz = np.where(yc < -3, e1, np.minimum(e1, e_nas))   # bez artefaktu w miejscu przyłożenia ugięcia
    dane.append(dict(nazwa=nazwa, p=p, X=mesh.p[0, f], Y=mesh.p[1, f], ux=u[ib.nodal_dofs[0]][f], uy=u[ib.nodal_dofs[1]][f],
                     e=e_pokaz[mesh.f2t[0, fac]] * 100, F=F, e_nas=e_nas))
    print(f"{nazwa}: nasada {e_nas*100:.2f}%, siła {F:.1f} N/ramię")

fig, axs = plt.subplots(1, 2, figsize=(11, 8))
fig.subplots_adjust(top=0.84, bottom=0.17, wspace=0.3)
vmax = 5.0
pcs, txt = [], []
for ax, d in zip(axs, dane):
    pc = PolyCollection(np.stack([d['X'].T, d['Y'].T], -1), array=d['e'] * 0, cmap='turbo', edgecolors='none')
    pc.set_clim(0, vmax); ax.add_collection(pc); pcs.append(pc)
    ax.set_xlim(-12, 12); ax.set_ylim(-54, 17); ax.set_aspect('equal')
    ax.set_title(d['nazwa'] + f"\nramiona {d['p']['Ls']} mm, szczelina {d['p']['s']} mm", fontsize=11)
    ax.set_xlabel('mm'); ax.tick_params(labelsize=8)
    for s in (-1, 1):   # ściany tunelu (do tej szerokości ściskane są zaczepy)
        ax.axvline(s * (d['p']['w'] + d['p']['luz']) / 2, color='0.6', lw=1, ls='--')
    txt.append(ax.text(0.5, -0.08, '', transform=ax.transAxes, ha='center', va='top', fontsize=10, linespacing=1.4))
cb = fig.colorbar(pcs[0], ax=axs, shrink=0.7, pad=0.08)
cb.ax.set_title('odkształcenie\n[%]', fontsize=9)
for v, k, c in [(eps_wiele * 100, 'dop. wielokr.', 'darkorange'), (eps_raz * 100, 'dop. jednoraz.', 'red')]:
    cb.ax.axhline(v, color=c, lw=2); cb.ax.text(1.25, v, k, transform=cb.ax.get_yaxis_transform(), va='center', fontsize=8, color=c)
fig.suptitle('Grot listwy MOLLE (PETG) – ściskanie ramion do szerokości tunelu\n'
             f'MES: Gmsh + scikit-fem, przemieszczenia na rysunku x{SKALA_POKAZ:g}, przerywane linie = ściany tunelu', fontsize=12)

def klatka(i):
    k = i / N if i <= N else (2 * N - i) / N
    for pc, d, tx in zip(pcs, dane, txt):
        X = d['X'] + SKALA_POKAZ * k * d['ux']; Y = d['Y'] + SKALA_POKAZ * k * d['uy']
        pc.set_verts(np.stack([X.T, Y.T], -1)); pc.set_array(k * d['e'])
        e = k * d['e_nas'] * 100
        stan = 'PĘKA' if e > eps_raz * 100 else ('zmęczenie' if e > eps_wiele * 100 else 'OK')
        tx.set_text(f"ugięcie zaczepu {k * d['p']['wystep']:.2f} mm\nnasada {e:.2f}%  ·  siła {k * d['F']:.1f} N/ramię\n{stan}")
        tx.set_color('red' if stan == 'PĘKA' else ('darkorange' if stan == 'zmęczenie' else 'darkgreen'))
    return pcs + txt

ani = animation.FuncAnimation(fig, klatka, frames=2 * N + 1, interval=60, blit=False)
out = os.path.join(TU, 'podglad', 'fem-grot-animacja')
ani.save(out + '.gif', writer=animation.PillowWriter(fps=15), dpi=80)
print('zapisano', out + '.gif')
if shutil.which('ffmpeg'):
    ani.save(out + '.mp4', writer=animation.FFMpegWriter(fps=24, bitrate=2500), dpi=110)
    print('zapisano', out + '.mp4')
