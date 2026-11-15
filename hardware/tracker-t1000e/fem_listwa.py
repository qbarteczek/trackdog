#!/usr/bin/env python3
"""Symulacja MES (metoda elementów skończonych) grotu listwy MOLLE: Gmsh (siatka) + scikit-fem (solwer).

Model 3D sprężysto-liniowy, elementy czworościenne 2. rzędu. Korpus listwy utwierdzony 12 mm przed
końcem szczeliny; zaczepy obu ramion przesunięte do środka o tyle, ile trzeba, żeby grot wszedł
w tunel (ugięcie = grot_wystep). Wynik: maksymalne odkształcenie główne (nasada ramienia, karb na
końcu szczeliny), siła ściśnięcia jednego ramienia, rysunek mapy odkształceń na kształcie ugiętym.

Środowisko: ~/.local/opt/fem-venv (pip: gmsh scikit-fem meshio matplotlib scipy).
Uruchom:   ~/.local/opt/fem-venv/bin/python fem_listwa.py
Uproszczenia: materiał izotropowy (druk płaski - ramiona zginają się wzdłuż ścieżek), bez zaokrągleń
krawędzi listwy (r 1 mm, nieco sztywniej), kontakt z tunelem bez tarcia.
"""
import os, sys
import numpy as np
import gmsh
import meshio
import gc
from skfem import MeshTet, ElementTetP2, ElementVector, Basis, asm, condense, solve, solver_iter_pcg, build_pc_diag
from skfem.models.elasticity import linear_elasticity, lame_parameters
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

TU = os.path.dirname(os.path.abspath(__file__))
MATERIALY = {'PLA': (3200, 0.36, 0.020, 0.012), 'PETG': (1900, 0.38, 0.035, 0.025)}  # E, nu, eps jednoraz., wielokrotne

WARIANTY = {
    'v1 (stara)': dict(w=18, t=2.4, luz=0.6, wystep=1.0, s=2.6, Ls=12, grot=14),
    'v2 (nowa)':  dict(w=18, t=2.4, luz=0.8, wystep=1.4, s=6.0, Ls=40, grot=14),
}


def siatka(p, h=1.2, h_karb=0.35):
    w, t, s, Ls, g = p['w'], p['t'], p['s'], p['Ls'], p['grot']
    gw = (w + p['luz']) / 2 + p['wystep']          # pół-szerokość grotu na zaczepach
    y0 = -(Ls + 12)                                # utwierdzenie (dalej korpus nie pracuje)
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    occ = gmsh.model.occ
    body = occ.addRectangle(-w / 2, y0, 0, w, -y0)
    pts = [occ.addPoint(x, y, 0) for x, y in [(-gw, 0), (gw, 0), (w / 2 - 1.5, g), (-(w / 2 - 1.5), g)]]
    ln = [occ.addLine(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    grot = occ.addPlaneSurface([occ.addCurveLoop(ln)])
    ksz, _ = occ.fuse([(2, body)], [(2, grot)])
    szcz = occ.addRectangle(-s / 2, -Ls, 0, s, Ls + g + 1)
    kolo = occ.addDisk(0, -Ls, 0, s / 2, s / 2)
    ksz, _ = occ.cut(ksz, [(2, szcz), (2, kolo)])
    occ.extrude(ksz, 0, 0, t)
    occ.synchronize()
    # zagęszczenie przy końcu szczeliny (karb) i przy zaczepach
    f = gmsh.model.mesh.field
    d = f.add('Distance'); f.setNumbers(d, 'PointsList', [occ.addPoint(0, -Ls - s / 2, t / 2)]); occ.synchronize()
    th = f.add('Threshold'); f.setNumber(th, 'InField', d)
    for k, v in dict(SizeMin=h_karb, SizeMax=h, DistMin=1.0, DistMax=8).items(): f.setNumber(th, k, v)
    f.setAsBackgroundMesh(th)
    gmsh.option.setNumber('Mesh.MeshSizeMax', h)
    gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 0)
    gmsh.model.mesh.generate(3)
    gmsh.write('/tmp/listwa_fem.msh'); gmsh.finalize()
    m = meshio.read('/tmp/listwa_fem.msh')
    tet = m.cells_dict['tetra']
    used = np.unique(tet); remap = -np.ones(len(m.points), int); remap[used] = np.arange(len(used))
    return MeshTet(m.points[used].T, remap[tet].T), y0, gw


def licz(p, E, nu, mesh, y0, gw):
    e = ElementVector(ElementTetP2())
    ib = Basis(mesh, e, intorder=3)
    lam, mu = lame_parameters(E, nu)
    K = asm(linear_elasticity(lam, mu), ib)
    utw = ib.get_dofs(lambda x: x[1] < y0 + 1e-6).all()
    # zaczep: zewnętrzna krawędź grotu tuż za ramieniem (y w [0, 1.5]) - tam opiera się o ścianę tunelu
    zprawej = ib.get_dofs(lambda x: (x[1] > -1e-6) & (x[1] < 1.5) & (x[0] > gw - 0.35))
    zlewej = ib.get_dofs(lambda x: (x[1] > -1e-6) & (x[1] < 1.5) & (x[0] < -gw + 0.35))
    u = ib.zeros()
    dp, dl = zprawej.nodal['u^1'], zlewej.nodal['u^1']
    u[dp] = -p['wystep']; u[dl] = p['wystep']
    D = np.unique(np.concatenate([utw, dp, dl]))
    A, b, x, I = condense(K, x=u, D=D)
    u[I] = solve(A, b, solver=solver_iter_pcg(M=build_pc_diag(A), rtol=1e-9, maxiter=20000))   # mało pamięci (3,7 GB RAM)
    sila = abs((K @ u)[dp].sum())                     # reakcja = siła ściśnięcia jednego ramienia [N]
    # odkształcenie główne max w punktach całkowania
    g = ib.interpolate(u).grad                       # (3,3,nel,nqp)
    eps = 0.5 * (g + g.transpose(1, 0, 2, 3))
    ev = np.linalg.eigvalsh(np.moveaxis(eps, (0, 1), (-2, -1)))   # (nel,nqp,3)
    e1 = np.abs(ev).max(axis=-1).max(axis=-1)        # na element
    # maksimum poza miejscem przyłożenia ugięcia (zadane przemieszczenie węzłów daje sztuczny szczyt w narożach
    # zaczepów) - realne miejsce pękania to nasada ramion / koniec szczeliny
    yc = mesh.p[1, mesh.t].mean(axis=0)
    e_nasada = e1[yc < -3].max()
    del eps, ev, g; gc.collect()
    return u, ib, sila, e1, e_nasada


def rysuj(ax, mesh, ib, u, e1, p, tytul, skala=1.0, vmax=None, zoom=None):
    t = p['t']
    fac = mesh.facets_satisfying(lambda x: x[2] > t - 1e-6)
    el = mesh.f2t[0, fac]
    xs = mesh.p[:, mesh.facets[:, fac]]               # (3, 3, nf)
    # przemieszczenia węzłów P1 (pierwsze stopnie swobody ElementVector P2 to wierzchołki)
    uv = u[ib.nodal_dofs].reshape(3, -1) if ib.nodal_dofs.shape[0] == 3 else None
    ux = u[ib.nodal_dofs[0]]; uy = u[ib.nodal_dofs[1]]
    X = xs[0] + skala * ux[mesh.facets[:, fac]]; Y = xs[1] + skala * uy[mesh.facets[:, fac]]
    poly = np.stack([X.T, Y.T], axis=-1)
    pc = PolyCollection(poly, array=e1[el] * 100, cmap='turbo', edgecolors='none')
    pc.set_clim(0, vmax)
    ax.add_collection(pc)
    ax.set_aspect('equal')
    if zoom: ax.set_xlim(zoom[0]); ax.set_ylim(zoom[1])
    else: ax.autoscale_view()
    ax.set_title(tytul, fontsize=10); ax.set_xlabel('mm'); ax.tick_params(labelsize=8)
    return pc


if __name__ == '__main__':
    wyniki = {}
    fig, axs = plt.subplots(1, 4, figsize=(17, 8.5), gridspec_kw=dict(width_ratios=[1, 1.25, 1, 1.25]))
    for k, (nazwa, p) in enumerate(WARIANTY.items()):
        mesh, y0, gw = siatka(p)
        print(f"\n== {nazwa}: siatka {mesh.p.shape[1]} węzłów, {mesh.t.shape[1]} elementów")
        for mn, (E, nu, eraz, ewiele) in MATERIALY.items():
            u, ib, F, e1, emax = licz(p, E, nu, mesh, y0, gw)
            ezacz = e1.max()
            werd = 'PĘKNIE przy wkładaniu' if emax > eraz else ('zmęczenie po wielu cyklach' if emax > ewiele else 'OK')
            print(f"   {mn:4}: nasada {emax*100:5.2f}% (szczyt przy zaczepie {ezacz*100:.1f}% - artefakt obciążenia)  (dop. {ewiele*100:.1f}/{eraz*100:.1f}%)  "
                  f"siła ściśnięcia {F:6.1f} N/ramię  -> {werd}")
            wyniki[(nazwa, mn)] = (emax, F, werd)
            if mn == 'PETG':
                vmax = 14 if 'v1' in nazwa else 3.5
                pc = rysuj(axs[2 * k], mesh, ib, u, e1, p, f"{nazwa}: odkształcenie [%]\n(ugięcie zaczepów {p['wystep']} mm, x1)", vmax=vmax)
                Ls, s = p['Ls'], p['s']
                rysuj(axs[2 * k + 1], mesh, ib, u, e1, p, f"{nazwa}: nasada szczeliny (zbliżenie)\nnasada max {emax*100:.1f}%  PETG {F:.0f} N / PLA "
                      f"{wyniki.get((nazwa, 'PLA'), (0, 0))[1]:.0f} N na ramię", vmax=vmax,
                      zoom=((-p['w'] / 2 - 1, p['w'] / 2 + 1), (-Ls - s / 2 - 6, -Ls + 8)))
                fig.colorbar(pc, ax=axs[2 * k:2 * k + 2], shrink=0.6, label='odkształcenie główne max [%]')
    fig.suptitle('Grot listwy MOLLE – MES (Gmsh + scikit-fem), ramiona ściśnięte do szerokości tunelu', fontsize=13)
    out = os.path.join(TU, 'podglad', 'fem-grot.png')
    fig.savefig(out, dpi=110, bbox_inches='tight')
    print('\nrysunek:', out)
