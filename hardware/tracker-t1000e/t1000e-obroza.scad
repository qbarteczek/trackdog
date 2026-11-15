// Obudowa SenseCAP Card Tracker T1000-E na psa: kamizelka MOLLE albo obroża
// Części: podstawa (kieszeń + mocowanie z tyłu), ramka (front, 4 wkręty M2 x 8
// do plastiku) i - dla MOLLE - dwie listwy (patyczki) z zatrzaskiem.
//
// MOLLE (domyślnie): kamizelka ma na grzbiecie pionowe paski taśmy (wzdłuż
// kręgosłupa). Obudowa leży wzdłuż grzbietu, a z tyłu ma bloczki, które wchodzą
// w przerwy między paskami. Listwa idzie w poprzek psa: bloczek, pod paskiem
// kamizelki, bloczek, pod paskiem, bloczek - i zatrzaskuje się grotem za
// ostatnim bloczkiem. Zdjęcie: ściśnij oba ramiona grotu i wysuń listwę.
//
// Obroża: dwa tunele z tyłu, obroża przechodzi pod trackerem.
//
// Ładowanie: okno z tyłu odsłania magnetyczne styki; zdejmij obudowę i przyłóż kabel.
//
// Wymiary T1000-E wg producenta: 85 x 55 x 6.5 mm. Położenie przycisku, diody,
// brzęczyka i styków oszacowane ze zdjęć; paski kamizelki - wartości typowe.
// ZMIERZ i popraw sekcje oznaczone (!) przed drukiem.
//
// Render:  openscad -D 'czesc="podstawa"' -o podstawa.stl t1000e-obroza.scad
//          openscad -D 'czesc="ramka"'    -o ramka.stl    t1000e-obroza.scad
//          openscad -D 'czesc="listwy"'   -o listwy.stl   t1000e-obroza.scad

czesc      = "zlozenie";  // "podstawa", "ramka", "listwy", "zlozenie"
mocowanie  = "molle";     // "molle" albo "obroza"

// ---------- Kamizelka MOLLE (!) ----------
pas_szer      = 25;     // szerokość paska taśmy na kamizelce
pas_przerwa   = 10;     // przerwa między sąsiednimi paskami
pas_ile       = 2;      // pod iloma paskami przechodzi listwa (bloczków jest o 1 więcej)
petla_rozstaw = 38.1;   // rozstaw szwów na pasku = rozstaw dwóch listew (MOLLE: 1,5")
// listwa
listwa_szer   = 18;     // musi wejść między szwy paska (< petla_rozstaw - szew)
listwa_gr     = 2.4;
luz_listwy    = 0.8;    // luz tunelu na grubość (szerokość: połowa tego na stronę); FDM: zwis stropu tunelu
mostek_molle  = 2.0;    // grubość mostka pod listwą w bloczku (tyle pasek musi się unieść + listwa)
pas_grub      = 2.0;    // grubość taśmy paska kamizelki (!) - pasek leży NA listwie
luz_pasa      = 0.6;    // luz nad paskiem, pod płytą obudowy
grot_dl       = 14;     // długość zatrzasku (grotu)
grot_wystep   = 2.0;    // o ile zaczep grotu wystaje na bok poza tunel; płaskie oparcie o bloczek
                        // = grot_wystep - faza_tunelu - r_zaczepu (tu 0,8 mm), inaczej zaczep
                        // zsuwa się po fazie zamiast oprzeć się o bloczek
zaczep_prosty = 1.2;    // prosty odcinek zaczepu przed skosem grotu (narożnik 90° zamiast ostrego)
r_zaczepu     = 0.4;    // zaokrąglenie zaczepów; duże (jak reszta listwy) zjada płaską półkę
szczelina_grotu = 6.0;  // szczelina między ramionami grotu (ramiona 6 mm szerokie)
szczelina_przed = 40;   // długość sprężystych ramion przed zaczepem; krótsze = sztywniej i pęka
                        // (symulacja_zatrzasku.py: 40 mm daje 1,2% odkształcenia - PETG z zapasem)
glowka_dl     = 6;      // główka listwy (oporek po drugiej stronie)

// ---------- Obroża ----------
obroza_szer  = 25;    // szerokość paska obroży [mm]
obroza_grub  = 3.5;   // grubość paska [mm]
luz_obrozy   = 1.0;   // luz tunelu (szer. i wys.)
tunel_dl     = 9;     // szerokość mostka wzdłuż obroży
mostek_gr    = 3.0;   // grubość mostka

// ---------- Tracker ----------
karta_dl   = 85;      // oś X (wzdłuż grzbietu / obroży); koniec z oczkiem smyczy przy X=0
karta_szer = 55;      // oś Y (w poprzek)
karta_grub = 6.5;
karta_r    = 4;       // promień narożnika karty
luz        = 0.3;     // luz kieszeni na stronę

// ---------- Obudowa ----------
scianka   = 3.0;      // ścianka boczna
dno       = 1.6;      // dno podstawy
ramka_gr  = 2.0;      // grubość ramki (frontu)
r_zew     = 1.5;      // promień narożnika zewnętrznego
docisk    = 0.2;      // ramka dociska kartę (kieszeń płytsza o tyle)
skrzydla_gr = 3.0;    // płyta tylna, gdy bloczki MOLLE wystają poza obrys

// zaokrąglenie WSZYSTKICH wypukłych krawędzi (obrys, otwory, wejścia tuneli,
// listwy) - żeby nic nie drapało psa ani nie przecierało kamizelki.
// Promień musi być mniejszy niż połowa najcieńszego elementu części.
// Kieszeń, otwory na wkręty i napis są wycinane PO zaokrągleniu (są zakryte
// albo za drobne), więc nie ograniczają promienia.
r_kraw       = 1.4;   // podstawa (mostki 3 mm)
r_kraw_ramki = 0.9;   // ramka (2 mm grubości)
r_kraw_listwy= 1.0;   // listwy (2,4 mm)
fn_kraw      = 24;    // gładkość zaokrągleń (więcej = wolniejszy render)

// wkręty M2 do plastiku
wkret_otw_pod = 1.6;  // otwór pilotowy w podstawie
wkret_otw_ram = 2.4;  // otwór przelotowy w ramce
wkret_xy      = 2.6;  // odległość osi wkrętu od krawędzi zewnętrznych

// napis wgłębiony na dłuższym boku (np. telefon); "" = bez napisu
napis       = "";
napis_wys   = 4.5;
napis_gleb  = 0.6;

// ---------- Elementy na froncie (współrzędne na karcie) ----------
// x = od końca z oczkiem smyczy wzdłuż 85 mm, y = w poprzek (55 mm), średnica otworu.
// Wg rysunku wymiarowego Seeed (karta katalogowa T1000-E) i zdjęć urządzenia (2026-10-28).
otwory_front = [
    [18.4, 27.5, 16],   // przycisk: nakładka Ø 13,6 mm + zapas, żeby ramka jej nie dociskała
    [36.9, 27.5,  9],   // świetlik diody i czujnika światła (Ø 6,1 mm)
    [52.6, 27.5, 10],   // brzęczyk: w obudowie karty jest otworek ok. 1 mm nad piezo Ø ok. 16 mm
];
// ---------- Okno z tyłu na styki ładowania ----------
// 4 piny pogo w pionowym rzędzie (kapsuła 17,3 x 5,2 mm z dwoma magnesami), 14 mm od długiego boku.
// Y: patrząc od frontu, oczko przy X = 0 - piny są przy Y = 55 - 14 (zdjęcie tyłu: oczko na dole, piny po prawej).
// X: rysunek Seeed daje środek 35,6 mm od oczka, zdjęcie ok. 43 mm - okno obejmuje oba.
okno_tyl_x  = 43.0;   // środek okna, od końca z oczkiem
okno_tyl_y  = 41.0;
okno_tyl_dl = 26;     // wzdłuż X: kapsuła 17,3 mm + rozrzut położenia + wtyczka
okno_tyl_sz = 10;     // wzdłuż Y: kapsuła 5,2 mm + wtyczka; mieści się w przerwie między bloczkami MOLLE
okno_tyl_r  = 3;

$fn = 48;

// ---------- wymiary pochodne ----------
kie_dl  = karta_dl + 2*luz;
kie_sz  = karta_szer + 2*luz;
kie_gl  = karta_grub - docisk;
zew_dl  = kie_dl + 2*scianka;
zew_sz  = kie_sz + 2*scianka;
pod_wys = dno + kie_gl;

// obroża
tunel_wys = obroza_grub + luz_obrozy;
tunel_sz  = obroza_szer + luz_obrozy;

// MOLLE
bloczek_sz  = pas_przerwa - 1;                    // bloczek mieści się w przerwie
molle_sz    = pas_ile*(pas_szer + pas_przerwa) + bloczek_sz;  // od bloczka do bloczka
plyta_sz    = max(zew_sz, molle_sz);
plyta_y0    = (zew_sz - plyta_sz)/2;              // płyta tylna (może być szersza od korpusu)
molle_y0    = (zew_sz - molle_sz)/2;              // zewnętrzna ściana pierwszego bloczka
tunel_m_wys = listwa_gr + luz_listwy;
tunel_m_sz  = listwa_szer + luz_listwy;
listwy_x    = [zew_dl/2 - petla_rozstaw/2, zew_dl/2 + petla_rozstaw/2];

// MOLLE: od kamizelki: mostek | listwa | pasek kamizelki (leży na listwie) | płyta obudowy
tyl_wys = mocowanie == "molle" ? mostek_molle + tunel_m_wys + pas_grub + luz_pasa : tunel_wys + mostek_gr;

assert(mocowanie != "obroza" || tunel_sz < zew_sz - 6, "obroża za szeroka na tę obudowę");
assert(mocowanie != "molle" || bloczek_sz >= 4, "przerwa między paskami za mała na bloczki");
assert(mocowanie != "molle" || petla_rozstaw/2 + tunel_m_sz/2 < zew_dl/2 - 2,
       "listwy nie mieszczą się na długości obudowy");

// Zaokrągla wszystkie wypukłe krawędzie bryły promieniem r (morfologiczne
// otwarcie: zjedzenie o r, potem pogrubienie o r). Wklęsłe naroża zostają.
module zaokraglij(r) {
    duzo = [-200, -200, -100];
    minkowski() {
        difference() {
            translate(duzo) cube(-2*duzo);
            minkowski() {
                difference() {
                    translate(duzo - [1, 1, 1]) cube(-2*duzo + [2, 2, 2]);
                    children();
                }
                sphere(r = r, $fn = fn_kraw);
            }
        }
        sphere(r = r, $fn = fn_kraw);
    }
}

module zaokr_prost(dl, sz, r) {
    r2 = min(r, dl/2 - 0.01, sz/2 - 0.01);
    translate([r2, r2]) offset(r = r2) square([dl - 2*r2, sz - 2*r2]);
}

module wkrety(d, h) {
    for (x = [wkret_xy, zew_dl - wkret_xy], y = [wkret_xy, zew_sz - wkret_xy])
        translate([x, y, 0]) cylinder(d = d, h = h);
}

// współrzędne karty -> współrzędne obudowy
function nakarte(x, y) = [scianka + luz + x, scianka + luz + y];

module tyl_obroza() {
    intersection() {
        linear_extrude(tyl_wys + 0.01) zaokr_prost(zew_dl, zew_sz, r_zew);
        for (x0 = [0, zew_dl - tunel_dl])
            translate([x0, 0, 0]) difference() {
                cube([tunel_dl, zew_sz, tyl_wys + 0.01]);
                translate([-1, (zew_sz - tunel_sz)/2, mostek_gr])
                    cube([tunel_dl + 2, tunel_sz, tunel_wys + 0.01]);
            }
    }
}

module tyl_molle() {
    // płyta tylna (skrzydła), jeśli bloczki wychodzą poza korpus
    if (plyta_sz > zew_sz)
        translate([0, plyta_y0, tyl_wys])
            linear_extrude(skrzydla_gr) zaokr_prost(zew_dl, plyta_sz, r_zew);
    // bloczki w przerwach między paskami, z tunelami na listwy (w poprzek, wzdłuż Y)
    // tunele są wycinane dopiero po zaokrągleniu (tunele_molle), inaczej zaokrąglanie
    // zjada mostki cieńsze niż 2*r_kraw i tunel zamienia się w otwarte wycięcie
    for (i = [0 : pas_ile])
        translate([0.5, molle_y0 + i*(pas_szer + pas_przerwa), 0])
            cube([zew_dl - 1, bloczek_sz, tyl_wys + 0.01]);
}

// tunele na listwy przez wszystkie bloczki, z fazą 0,8 mm na wejściach
faza_tunelu = 0.8;
module tunele_molle() {
    for (x = listwy_x) {
        translate([x - tunel_m_sz/2, molle_y0 - 1, mostek_molle])
            cube([tunel_m_sz, molle_sz + 2, tunel_m_wys]);
        for (i = [0 : pas_ile], sciana = [0, bloczek_sz], kier = [sciana == 0 ? 1 : -1])
            translate([x, molle_y0 + i*(pas_szer + pas_przerwa) + sciana, mostek_molle + tunel_m_wys/2])
                hull() {
                    translate([0, -kier*0.5, 0])
                        cube([tunel_m_sz + 2*faza_tunelu, 1, tunel_m_wys + 2*faza_tunelu], center = true);
                    translate([0, kier*faza_tunelu, 0])
                        cube([tunel_m_sz, 0.01, tunel_m_wys], center = true);
                }
    }
}

module podstawa() {
    difference() {
        zaokraglij(r_kraw) podstawa_bryla();
        podstawa_wyciecia();
    }
}
module ramka() {
    difference() {
        zaokraglij(r_kraw_ramki) ramka_bryla();
        translate([0, 0, -1]) wkrety(wkret_otw_ram, ramka_gr + 2);
    }
}
module listwa() {
    zaokraglij(r_kraw_listwy) linear_extrude(listwa_gr) listwa_2d();
    // zaczepy osobno, z małym zaokrągleniem - półka oporowa zostaje płaska
    zaokraglij(r_zaczepu) linear_extrude(listwa_gr) zaczepy_2d();
}

// pełna bryła z tunelami i oknem - ta jest zaokrąglana
module podstawa_bryla() {
    difference() {
        union() {
            translate([0, 0, tyl_wys])
                linear_extrude(pod_wys) zaokr_prost(zew_dl, zew_sz, r_zew);
            if (mocowanie == "molle") tyl_molle(); else tyl_obroza();
        }
        // okno z tyłu na styki ładowania (przez wszystko)
        translate([each nakarte(okno_tyl_x - okno_tyl_dl/2, okno_tyl_y - okno_tyl_sz/2), -1])
            linear_extrude(tyl_wys + pod_wys + 2) zaokr_prost(okno_tyl_dl, okno_tyl_sz, okno_tyl_r);
    }
}

// wycinane po zaokrągleniu: kieszeń (zakryta ramką), tunele MOLLE, wkręty, napis
module podstawa_wyciecia() {
    union() {
        // kieszeń
        translate([scianka, scianka, tyl_wys + dno])
            linear_extrude(kie_gl + 1) zaokr_prost(kie_dl, kie_sz, karta_r + luz);
        if (mocowanie == "molle") tunele_molle();
        // otwory pilotowe wkrętów
        translate([0, 0, tyl_wys + 1]) wkrety(wkret_otw_pod, pod_wys);
        // napis na dłuższym boku (Y = 0)
        if (napis != "")
            translate([zew_dl/2, napis_gleb - 0.01, tyl_wys + pod_wys/2])
                rotate([90, 0, 0]) linear_extrude(napis_gleb + 1)
                    text(napis, size = napis_wys, font = "Liberation Sans:style=Bold",
                         halign = "center", valign = "center");
    }
}

module ramka_bryla() {
    difference() {
        linear_extrude(ramka_gr) zaokr_prost(zew_dl, zew_sz, r_zew);
        for (o = otwory_front)
            translate([each nakarte(o[0], o[1]), -1]) cylinder(d = o[2], h = ramka_gr + 2);
    }
}

// Listwa w 2D, oś wzdłuż Y: główka przy Y < 0, zaczepy grotu za Y = molle_sz.
module listwa_2d() {
    // naroża w płaszczyźnie listwy zaokrąglone mocniej (r = 1,5 mm)
    offset(r = 1.5) offset(delta = -1.5) listwa_2d_ostra();
}
listwa_dl = molle_sz + 0.4;                     // od główki do zaczepów
module listwa_2d_ostra() {
    w   = listwa_szer;
    dl  = listwa_dl;
    // główka
    translate([-(w + 6)/2, -glowka_dl]) square([w + 6, glowka_dl]);
    difference() {
        union() {
            translate([-w/2, -0.01]) square([w, dl + 0.02]);
            // czubek grotu zwęża się (zaczepy dokłada zaczepy_2d)
            translate([0, dl])
                polygon([[-w/2, 0], [w/2, 0], [w/2 - 1.5, grot_dl], [-(w/2 - 1.5), grot_dl]]);
        }
        // szczelina dzieląca grot na dwa sprężyste ramiona
        translate([-szczelina_grotu/2, dl - szczelina_przed]) square([szczelina_grotu, grot_dl + szczelina_przed + 1]);
        translate([0, dl - szczelina_przed]) circle(d = szczelina_grotu);
    }
}
// Zaczepy grotu (oba boki): płaska półka oporowa, prosty odcinek i skos wprowadzający
// do czubka. Zachodzą 1,5 mm na ramię, żeby zrosły się z nim po zaokrągleniu.
module zaczepy_2d() {
    w  = listwa_szer;
    gw = tunel_m_sz + 2*grot_wystep;
    for (k = [-1, 1]) scale([k, 1])
        translate([0, listwa_dl])
            polygon([[w/2 - 1.5, 0], [gw/2, 0], [gw/2, zaczep_prosty], [w/2 - 1.5, grot_dl]]);
}


module karta() {
    color("dimgray", 0.8)
        translate([scianka + luz, scianka + luz, tyl_wys + dno])
            linear_extrude(karta_grub) zaokr_prost(karta_dl, karta_szer, karta_r);
}

if (czesc == "podstawa") {
    // druk FDM: na stojąco, na krótszym końcu - bez podpór
    podstawa();
} else if (czesc == "ramka") {
    // druk płasko, frontem do stołu
    translate([0, 0, ramka_gr]) mirror([0, 0, 1]) ramka();
} else if (czesc == "nic") {
    // nic - plik dołączany przez include (np. schemat-montazu.scad)
} else if (czesc == "listwy") {
    // druk płasko; drukuj zapas, to część eksploatacyjna
    for (i = [0 : 2]) translate([i*(listwa_szer + 10), 0, 0]) listwa();
} else {
    podstawa();
    karta();
    color("orange") translate([0, 0, tyl_wys + pod_wys + 0.01]) ramka();
    if (mocowanie == "molle") {
        // paski kamizelki i listwy
        for (i = [0 : pas_ile - 1])
            color("tan", 0.7)
                translate([-25, molle_y0 + bloczek_sz + 0.5 + i*(pas_szer + pas_przerwa),
                           mostek_molle + tunel_m_wys])   // pasek leży NA listwie
                    cube([zew_dl + 50, pas_szer - 1, pas_grub]);
        for (x = listwy_x)
            color("black") translate([x, molle_y0 - 0.2, mostek_molle + luz_listwy/2]) listwa();
    } else {
        color("saddlebrown", 0.6)
            translate([-30, (zew_sz - obroza_szer)/2, mostek_gr + luz_obrozy/2])
                cube([zew_dl + 60, obroza_szer, obroza_grub]);
    }
}
