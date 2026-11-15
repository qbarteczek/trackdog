#!/usr/bin/env python3
"""Analiza listwy jak wydruku FDM: ścieżki z G-code (PrusaSlicer) -> materiał kierunkowy w MES -> Tsai-Hill.

1. G-code: odcinki ekstruzji w każdej warstwie z typem (;TYPE:) i kierunkiem; podgląd jak w slicerze,
   przekrój ramienia (ile ścieżek, szczeliny).
2. MES (Gmsh + scikit-fem, jak fem_listwa.py): każdy element dostaje kierunek i typ najbliższej ścieżki
   w swojej warstwie. Materiał ortotropowy: 1 = wzdłuż ścieżki, 2 = w poprzek (zgrzew między ścieżkami
   w warstwie), 3 = między warstwami. Rzadkie wypełnienie i szczeliny mają obniżoną sztywność.
3. Wytężenie Tsai-Hill (3D) w osiach ścieżki; współczynnik bezpieczeństwa SF = 1/sqrt(FI).
   Wielokrotne zapinanie (setki cykli): wymagane SF >= 2 (zmęczenie FDM ~50% wytrzymałości).

Uruchom: ~/.local/opt/fem-venv/bin/python fdm_analiza.py A.gcode B.gcode
Parametry materiałów: typowe wartości z badań wydruków FDM (nie pomiar konkretnego filamentu).
"""
import os, re, sys
import numpy as np
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from skfem import Basis, ElementTetP2, ElementTetP0, ElementVector, BilinearForm, asm, condense, solve, solver_iter_pcg, build_pc_diag
from skfem.helpers import sym_grad, ddot
from fem_listwa import WARIANTY, siatka

TU = os.path.dirname(os.path.abspath(__file__))
P = WARIANTY['v2 (nowa)']
DL = 79 + 0.4            # molle_sz + 0.4: położenie zaczepu w układzie listwy (główka przy y<0)
WARSTWA, SZER = 0.2, 0.45

# E1 wzdłuż, E2 w poprzek (zgrzew w warstwie), E3 między warstwami [MPa]; wytrzymałości X, Y, Z, S [MPa]
MAT = {
    'PETG': dict(E=(1900, 1500, 1400), G=(650, 550, 520), nu=(0.38, 0.38, 0.40), X=45, Y=30, Z=22, S=25),
    'PLA':  dict(E=(3200, 2700, 2500), G=(1100, 950, 900), nu=(0.35, 0.35, 0.37), X=55, Y=35, Z=25, S=28),
}
TYPY = {'External perimeter': 'obrys zewn.', 'Perimeter': 'obrys', 'Solid infill': 'wypełn. pełne',
        'Top solid infill': 'wypełn. pełne', 'Bridge infill': 'mostek', 'Internal infill': 'wypełn. rzadkie',
        'Gap fill': 'wypełn. szczelin'}
KOLOR = {'obrys zewn.': '#e8590c', 'obrys': '#f59f00', 'wypełn. pełne': '#ae3ec9', 'mostek': '#1c7ed6',
         'wypełn. rzadkie': '#2f9e44', 'wypełn. szczelin': '#e03131'}


def czytaj_gcode(f):
    seg = []   # (warstwa, x0, y0, x1, y1, typ)
    x = y = 0.0; z = 0.0; typ = None; wz = -1; zs = []
    for ln in open(f):
        if ln.startswith(';Z:'):
            z = float(ln[3:]); zs.append(z); wz = len(zs) - 1
        elif ln.startswith(';TYPE:'):
            typ = TYPY.get(ln[6:].strip())
        elif ln.startswith('G1') or ln.startswith('G0'):
            m = dict(re.findall(r'([XYE])(-?[\d.]+)', ln))
            nx, ny = float(m.get('X', x)), float(m.get('Y', y))
            if 'E' in m and float(m['E']) > 0 and typ and wz >= 0 and (nx, ny) != (x, y):
                seg.append((wz, x, y, nx, ny, typ))
            x, y = nx, ny
    return seg, zs


def do_ukladu_listwy(seg):
    """G-code (stół) -> układ listwy z OpenSCAD: dopasowanie obwiedni obrysu zewnętrznego."""
    a = np.array([(s[1], s[2]) for s in seg if s[5] == 'obrys zewn.'] + [(s[3], s[4]) for s in seg if s[5] == 'obrys zewn.'])
    w = P['w']; x0m, x1m, y0m, y1m = -(w + 6) / 2, (w + 6) / 2, -6, DL + P['grot']
    sx, sy = (x0m + x1m) / 2 - (a[:, 0].min() + a[:, 0].max()) / 2, (y0m + y1m) / 2 - (a[:, 1].min() + a[:, 1].max()) / 2
    # FEM: zaczep przy y = 0  ->  y_fem = y_listwy - DL
    return [(l, x0 + sx, y0 + sy - DL, x1 + sx, y1 + sy - DL, t) for l, x0, y0, x1, y1, t in seg]


def przekroj_ramienia(seg, y_c=-20.0):
    """Ścieżki przecinające prostą y = y_c (środek ramion): pozycje x w każdej warstwie."""
    wyn = {}
    for l, x0, y0, x1, y1, t in seg:
        if (y0 - y_c) * (y1 - y_c) < 0:
            xc = x0 + (y_c - y0) / (y1 - y0) * (x1 - x0)
            wyn.setdefault(l, []).append((xc, t))
    return {l: sorted(v) for l, v in wyn.items()}


def pole_kierunkow(seg, nwarstw):
    """Dla każdej warstwy: drzewo punktów próbkowanych co 0,1 mm wzdłuż ścieżek, z kątem i typem."""
    pola = []
    for l in range(nwarstw):
        pts, ang, typ = [], [], []
        for s in seg:
            if s[0] != l: continue
            _, x0, y0, x1, y1, t = s
            L = np.hypot(x1 - x0, y1 - y0); n = max(2, int(L / 0.1))
            u = np.linspace(0, 1, n)
            pts.append(np.c_[x0 + u * (x1 - x0), y0 + u * (y1 - y0)])
            ang += [np.arctan2(y1 - y0, x1 - x0)] * n; typ += [t] * n
        pola.append((cKDTree(np.vstack(pts)), np.array(ang), np.array(typ)))
    return pola


def sztywnosc(m):
    E1, E2, E3 = m['E']; G12, G13, G23 = m['G']; n12, n13, n23 = m['nu']
    Sm = np.zeros((6, 6))
    Sm[0, 0], Sm[1, 1], Sm[2, 2] = 1 / E1, 1 / E2, 1 / E3
    Sm[0, 1] = Sm[1, 0] = -n12 / E1; Sm[0, 2] = Sm[2, 0] = -n13 / E1; Sm[1, 2] = Sm[2, 1] = -n23 / E2
    Sm[3, 3], Sm[4, 4], Sm[5, 5] = 1 / G23, 1 / G13, 1 / G12
    return np.linalg.inv(Sm)      # Voigt: 11, 22, 33, 23, 13, 12 (odkształcenia postaciowe inżynierskie)


def lokalne(e, c, s):
    """Odkształcenia globalne (tensor) -> lokalne w osiach ścieżki (obrót wokół z o kąt ścieżki)."""
    exx, eyy, ezz, exy, exz, eyz = e[0, 0], e[1, 1], e[2, 2], e[0, 1], e[0, 2], e[1, 2]
    return (c * c * exx + s * s * eyy + 2 * c * s * exy, s * s * exx + c * c * eyy - 2 * c * s * exy, ezz,
            -s * exz + c * eyz, c * exz + s * eyz, -c * s * exx + c * s * eyy + (c * c - s * s) * exy)


def naprezenia_lokalne(e, c, s, k, C):
    e11, e22, e33, e23, e13, e12 = lokalne(e, c, s)
    v = [e11, e22, e33, 2 * e23, 2 * e13, 2 * e12]
    return [k * sum(C[i, j] * v[j] for j in range(6)) for i in range(6)]   # s11, s22, s33, s23, s13, s12


def globalne(sl, c, s):
    s11, s22, s33, s23, s13, s12 = sl
    sxx = c * c * s11 + s * s * s22 - 2 * c * s * s12
    syy = s * s * s11 + c * c * s22 + 2 * c * s * s12
    sxy = c * s * s11 - c * s * s22 + (c * c - s * s) * s12
    sxz = c * s13 - s * s23; syz = s * s13 + c * s23
    return np.array([[sxx, sxy, sxz], [sxy, syy, syz], [sxz, syz, s33]])


def mes(mesh, y0, gw, pola, zs, mat, gestosc_rzadkiego):
    C = sztywnosc(mat)
    ib = Basis(mesh, ElementVector(ElementTetP2()), intorder=3)
    b0 = ib.with_element(ElementTetP0())
    cen = mesh.p[:, mesh.t].mean(axis=1)
    warstwa = np.clip((cen[2] / WARSTWA).astype(int), 0, len(zs) - 1)
    th = np.zeros(mesh.t.shape[1]); kk = np.ones_like(th); typ = np.empty(th.shape, object); szczel = np.zeros(th.shape, bool)
    for l in np.unique(warstwa):
        idx = np.where(warstwa == l)[0]
        tree, ang, tp = pola[l]
        d, j = tree.query(cen[:2, idx].T)
        th[idx] = ang[j]; typ[idx] = tp[j]
        kk[idx] = np.where(d > SZER * 0.75, 0.05, 1.0)                        # szczelina bez ścieżki
        szczel[idx] = d > SZER * 0.75
        kk[idx] *= np.where(tp[j] == 'wypełn. rzadkie', gestosc_rzadkiego, 1.0)
    c_, s_, k_ = np.cos(th), np.sin(th), kk

    @BilinearForm
    def forma(u, v, w):
        return ddot(globalne(naprezenia_lokalne(sym_grad(u), w['c'], w['s'], w['k'], C), w['c'], w['s']), sym_grad(v))

    pola_w = dict(c=b0.interpolate(c_), s=b0.interpolate(s_), k=b0.interpolate(k_))
    K = asm(forma, ib, **pola_w)
    utw = ib.get_dofs(lambda x: x[1] < y0 + 1e-6).all()
    zp = ib.get_dofs(lambda x: (x[1] > -1e-6) & (x[1] < 1.5) & (x[0] > gw - 0.35)).nodal['u^1']
    zl = ib.get_dofs(lambda x: (x[1] > -1e-6) & (x[1] < 1.5) & (x[0] < -gw + 0.35)).nodal['u^1']
    u = ib.zeros(); u[zp] = -P['wystep']; u[zl] = P['wystep']
    A, b, x, I = condense(K, x=u, D=np.unique(np.concatenate([utw, zp, zl])))
    u[I] = solve(A, b, solver=solver_iter_pcg(M=build_pc_diag(A), rtol=1e-9, maxiter=30000))
    F = abs((K @ u)[zp].sum())
    # wytężenie Tsai-Hill w punktach całkowania, w osiach ścieżki
    g = ib.interpolate(u).grad
    e = 0.5 * (g + g.transpose(1, 0, 2, 3))
    cq, sq, kq = (np.asarray(pola_w[n]) for n in 'csk')
    s11, s22, s33, s23, s13, s12 = naprezenia_lokalne(e, cq, sq, kq, C)
    sc = np.where(kq < 0.999, np.maximum(kq, 0.05), 1.0)                      # rzadkie wypełnienie: słabsze
    # szczelina (brak ścieżki w G-code, np. zaokrąglona krawędź, której siatka MES nie ma) to powietrze:
    # obniża sztywność, ale nie jest oceniana - inaczej daje sztuczny szczyt wytężenia
    X, Y, Z, S = (mat[n] * sc for n in 'XYZS')
    FI = ((s11 / X) ** 2 - s11 * s22 / X ** 2 + (s22 / Y) ** 2 + (s33 / Z) ** 2
          + (s12 / S) ** 2 + (s13 / S) ** 2 + (s23 / S) ** 2).max(axis=1)
    FI[szczel] = 0
    # który kierunek dominuje (udział w FI): wzdłuż / zgrzew w warstwie / między warstwami / ścinanie
    skl = np.stack([(s11 / X) ** 2, (s22 / Y) ** 2, (s33 / Z) ** 2, (s12 / S) ** 2 + (s13 / S) ** 2 + (s23 / S) ** 2]).max(axis=2)
    return dict(FI=FI, skl=skl, F=F, typ=typ, kk=kk, th=th, cen=cen, mesh=mesh, szczel=szczel)


def rysuj_sciezki(ax, seg, l, tytul, zoom):
    for t, kol in KOLOR.items():
        ls = [((x0, y0), (x1, y1)) for w, x0, y0, x1, y1, tt in seg if w == l and tt == t]
        if ls: ax.add_collection(LineCollection(ls, colors=kol, linewidths=2.2, label=t))
    ax.set_xlim(*zoom[0]); ax.set_ylim(*zoom[1]); ax.set_aspect('equal'); ax.set_title(tytul, fontsize=10)
    ax.tick_params(labelsize=7)


if __name__ == '__main__':
    pliki = sys.argv[1:] or [os.path.join(TU, 'listwa_A.gcode'), os.path.join(TU, 'listwa_B.gcode')]
    profile = {'A': 0.15, 'B': 1.0}       # gęstość wypełnienia rzadkiego
    mesh, y0, gw = siatka(P)
    zoom = ((-11, 11), (-50, 2))
    fig1, ax1 = plt.subplots(1, 4, figsize=(16, 9))
    wyniki = {}
    for k, f in enumerate(pliki):
        prof = 'A' if '_A' in f else 'B'
        seg, zs = czytaj_gcode(f)
        seg = do_ukladu_listwy(seg)
        print(f"\n== profil {prof} ({os.path.basename(f)}): {len(zs)} warstw, {len(seg)} odcinków ekstruzji")
        prz = przekroj_ramienia(seg)
        for l in (0, len(zs) // 2):
            xs = prz.get(l, [])
            prawe = [(round(x, 2), t) for x, t in xs if x > 0]
            print(f"   warstwa {l+1:2}: przekrój prawego ramienia (y=-20): {len(prawe)} ścieżek: " +
                  ', '.join(f'{x:+.2f} {t}' for x, t in prawe))
        for j, l in enumerate((0, len(zs) // 2)):
            rysuj_sciezki(ax1[2 * k + j], seg, l, f'profil {prof}, warstwa {l+1} z {len(zs)}', zoom)
        pola = pole_kierunkow(seg, len(zs))
        for mn, m in MAT.items():
            r = mes(mesh, y0, gw, pola, zs, m, profile[prof])
            nas = r['cen'][1] < -3
            i = np.argmax(np.where(nas, r['FI'], 0))
            SF = 1 / np.sqrt(r['FI'][i])
            dom = ['wzdłuż ścieżki', 'zgrzew między ścieżkami', 'między warstwami', 'ścinanie'][int(np.argmax(r['skl'][:, i]))]
            wyniki[(prof, mn)] = (SF, r)
            werd = 'PĘKNIE' if SF < 1 else ('ryzyko zmęczenia' if SF < 2 else 'OK')
            print(f"   {mn:4}: SF {SF:4.1f} w miejscu: x {r['cen'][0, i]:+.1f}, y {r['cen'][1, i]:+.1f}, z {r['cen'][2, i]:.1f} mm "
                  f"({r['typ'][i]}), decyduje: {dom}; siła ściśnięcia {r['F']:.1f} N/ramię -> {werd}")
    h, l = ax1[0].get_legend_handles_labels()
    fig1.legend(h, l, loc='lower center', ncol=6, fontsize=10)
    fig1.suptitle('Ścieżki z G-code (PrusaSlicer, PETG, dysza 0,4, warstwa 0,2): ramiona grotu listwy\n'
                  'A: 3 obrysy, wypełnienie 15% gyroid   B: 4 obrysy, wypełnienie 100% wzdłuż listwy', fontsize=12)
    fig1.savefig(os.path.join(TU, 'podglad', 'fdm-sciezki.png'), dpi=100, bbox_inches='tight')

    # mapa wytężenia (PETG) w warstwie środkowej, A i B
    fig2, ax2 = plt.subplots(1, 2, figsize=(11, 8.5))
    for a, prof in zip(ax2, ('A', 'B')):
        SF, r = wyniki[(prof, 'PETG')]
        m = r['mesh']
        fac = m.facets_satisfying(lambda x: x[2] > P['t'] - 1e-6)
        el = m.f2t[0, fac]; xs = m.p[:, m.facets[:, fac]]
        val = np.sqrt(r['FI'][el]) * 100                      # wytężenie w % wytrzymałości
        val = np.where((r['cen'][1, el] < -3) & ~r['szczel'][el], val, np.nan)
        pc = PolyCollection(np.stack([xs[0].T, xs[1].T], -1), array=val, cmap='turbo', edgecolors='none')
        pc.set_clim(0, 60); a.add_collection(pc)
        a.set_xlim(-11, 11); a.set_ylim(-50, 2); a.set_aspect('equal')
        a.set_title(f'profil {prof}, PETG: SF = {SF:.1f}\n(wytężenie Tsai-Hill, warstwa górna)', fontsize=11)
    fig2.colorbar(pc, ax=ax2, shrink=0.7, label='wytężenie [% wytrzymałości FDM]')
    fig2.suptitle('MES z materiałem kierunkowym według ścieżek G-code (ramiona ściśnięte do szerokości tunelu)', fontsize=12)
    fig2.savefig(os.path.join(TU, 'podglad', 'fdm-mes.png'), dpi=100, bbox_inches='tight')
    print('\nrysunki: podglad/fdm-sciezki.png, podglad/fdm-mes.png')
