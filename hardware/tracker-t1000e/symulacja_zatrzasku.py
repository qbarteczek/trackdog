#!/usr/bin/env python3
"""Symulacja zatrzasku listwy MOLLE (grot z dwoma ramionami) dla PLA i PETG.

Model: każde ramię grotu to wspornik o długości L (od końca szczeliny do zaczepu), przekroju
h (szerokość ramienia w płaszczyźnie listwy) x t (grubość listwy), zginany w płaszczyźnie listwy.
Sztywność: zginanie + ścinanie (Timoshenko). Odkształcenie u nasady z karbem (koniec szczeliny,
promień s/2). Siły: wkładanie (klin grotu + tarcie), ściśnięcie palcami (wyjmowanie),
wyrwanie przy ciągnięciu (płaskie oparcie zaczepu o bloczek albo klin na fazie tunelu).

Parametry odpowiadają zmiennym w t1000e-obroza.scad. Uruchom: python3 symulacja_zatrzasku.py
"""
import math

# materiał FDM drukowany płasko (włókna wzdłuż ramienia): moduł E [MPa], dopuszczalne odkształcenie
# jednorazowe (montaż) i wielokrotne (zdejmowanie do ładowania co 1-2 dni, setki cykli), tarcie
MATERIALY = {
    'PLA':  dict(E=3200, eps_raz=0.020, eps_wiele=0.012, mu=0.35, tg=57),
    'PETG': dict(E=1900, eps_raz=0.035, eps_wiele=0.025, mu=0.30, tg=78),
}


def zatrzask(listwa_szer, listwa_gr, luz_listwy, grot_wystep, szczelina, przed_zaczepem,
             grot_dl, faza_tunelu, r_kraw_listwy=1.0, r_zaczepu=None):
    w, t = listwa_szer, listwa_gr
    h = (w - szczelina) / 2 - 0.3 * r_kraw_listwy      # zaokrąglenie krawędzi zjada trochę przekroju
    L = przed_zaczepem
    d = grot_wystep                                     # ugięcie potrzebne, żeby zaczep wszedł w tunel
    tunel = w + luz_listwy
    gw = tunel + 2 * grot_wystep
    tg_klin = (gw / 2 - (w / 2 - 1.5)) / grot_dl        # pochylenie grotu (wprowadzenie)
    # zaczep poza fazą = płaskie oparcie o bloczek; zaokrąglenie narożnika zaczepu też je zjada
    # (v1/v2: ostry narożnik ok. 77° pod r 1,5 w płaszczyźnie - zjadał całą półkę, pomiar STL: 0 mm)
    r_z = r_zaczepu if r_zaczepu is not None else 1.9
    oparcie = grot_wystep - faza_tunelu - r_z
    kt = 1 + 0.5 * math.sqrt(h / (szczelina / 2))       # karb na końcu szczeliny (przybliżenie)
    return dict(h=h, L=L, d=d, t=t, gw=gw, tg_klin=tg_klin, oparcie=oparcie, kt=kt,
                kolizja=d > szczelina / 2 - 0.2)


def policz(g, m):
    E, G = m['E'], m['E'] / 2.7
    I = g['t'] * g['h'] ** 3 / 12
    podatnosc = g['L'] ** 3 / (3 * E * I) + 1.2 * g['L'] / (G * g['t'] * g['h'])
    k = 1 / podatnosc                                   # N/mm na ramię
    F = k * g['d']                                      # siła ugięcia jednego ramienia
    eps = F * g['L'] * (g['h'] / 2) / (E * I) * g['kt']
    mu, a = m['mu'], g['tg_klin']
    wkladanie = 2 * F * (a + mu) / (1 - mu * a)
    if g['oparcie'] > 0.3:
        wyrwanie = None                                 # płaskie oparcie - trzyma do zniszczenia
    else:                                               # zaczep zsuwa się po fazie 45°
        wyrwanie = 2 * F * (1 + mu) / (1 - mu)
    return dict(k=k, F=F, eps=eps, wkladanie=wkladanie, wyrwanie=wyrwanie)


def ocena(r, g, m):
    uw = []
    if g['kolizja']:
        uw.append('ramiona stykają się przed pełnym ugięciem')
    if r['eps'] > m['eps_raz']:
        uw.append('PĘKNIE przy pierwszym wkładaniu')
    elif r['eps'] > m['eps_wiele']:
        uw.append('zmęczenie: pęknie po kilkudziesięciu cyklach')
    if r['F'] > 25:
        uw.append('za sztywny do ściśnięcia palcami')
    if r['F'] < 3:
        uw.append('za miękki')
    if r['wyrwanie'] is not None and r['wyrwanie'] < 30:
        uw.append('słabo trzyma (zsuwa się po fazie)')
    return uw or ['OK']


WARIANTY = {
    'obecny (v1)': dict(listwa_szer=18, listwa_gr=2.4, luz_listwy=0.6, grot_wystep=1.0, szczelina=2.6,
                        przed_zaczepem=12, grot_dl=14, faza_tunelu=0.8),
    'poprawiony (v2)': dict(listwa_szer=18, listwa_gr=2.4, luz_listwy=0.8, grot_wystep=1.4, szczelina=6.0,
                            przed_zaczepem=40, grot_dl=14, faza_tunelu=0.8),
    'v3 (zaczepy r 0,4)': dict(listwa_szer=18, listwa_gr=2.4, luz_listwy=0.8, grot_wystep=2.0, szczelina=6.0,
                               przed_zaczepem=40, grot_dl=14, faza_tunelu=0.8, r_zaczepu=0.4),
}

if __name__ == '__main__':
    for nazwa, p in WARIANTY.items():
        g = zatrzask(**p)
        print(f"\n== {nazwa}: ramię {g['h']:.1f} x {g['t']} mm, długość do zaczepu {g['L']} mm, "
              f"ugięcie {g['d']} mm, oparcie zaczepu {g['oparcie']:+.1f} mm, karb Kt {g['kt']:.2f}")
        for mn, m in MATERIALY.items():
            r = policz(g, m)
            wy = 'trzyma (płaskie oparcie)' if r['wyrwanie'] is None else f"{r['wyrwanie']:.0f} N"
            print(f"   {mn:4}  odkształcenie {r['eps']*100:4.1f}% (dop. {m['eps_wiele']*100:.1f}/{m['eps_raz']*100:.1f}%)"
                  f"  ściśnięcie {r['F']:5.1f} N/ramię  wkładanie {r['wkladanie']:5.0f} N  wyrwanie {wy}"
                  f"  -> {'; '.join(ocena(r, g, m))}")
    print("\nTemperatura mięknienia: PLA ok. 57 °C (czarna kamizelka w słońcu / w aucie - ryzyko),"
          " PETG ok. 78 °C.")
