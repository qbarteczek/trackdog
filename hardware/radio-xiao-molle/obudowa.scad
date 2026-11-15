// Obudowa XIAO nRF52840 + Wio-SX1262 (zestaw Seeed) z baterią LiPo 203450 4000 mAh,
// gniazdem SMA na antenę (pigtail U.FL -> SMA bulkhead), otworem USB-C
// i mocowaniem zewnętrznym MOLLE/PALS (dwie sztywne listwy z zatrzaskiem).
//
// Układ (patrząc na front, obudowa zamocowana na kamizelce/plecaku):
//   X - w poziomie (wzdłuż rzędów taśmy PALS), Y - w pionie (do góry = +Y),
//   Z - od kamizelki (Z = 0) na zewnątrz.
//   Na dole bateria, na górze elektronika. USB-C w prawej ściance (+X),
//   gniazdo SMA w górnej ściance (+Y) - antena do góry.
//
// MOLLE/PALS: na kamizelce poziome rzędy taśmy 1" co 1" (przerwa 1"), szwy co 1,5".
// Z tyłu obudowy są poziome bloczki, które wchodzą w przerwy między rzędami.
// Listwa idzie pionowo: bloczek, pod rzędem taśmy, bloczek - i zatrzaskuje się
// grotem za ostatnim bloczkiem (ten sam grot co w meshcore-tracker/obudowa, v3).
// Zdjęcie: ściśnij oba ramiona grotu i wysuń listwę za główkę.
//
// Części: podstawa, wieko (4 wkręty M2 x 10 do plastiku), listwy (2 + zapas).
// Render (OpenSCAD 2025+, --backend=Manifold):
//   openscad -D 'czesc="podstawa"' -o stl/podstawa.stl obudowa.scad
//   openscad -D 'czesc="wieko"'    -o stl/wieko.stl    obudowa.scad
//   openscad -D 'czesc="listwy"'   -o stl/listwy.stl   obudowa.scad
//   openscad -D 'czesc="test_usb"' -o stl/test_usb.stl obudowa.scad   (szybka próba pasowania)
//
// ZMIERZ i popraw sekcje oznaczone (!) przed drukiem.

czesc = "zlozenie";   // "podstawa", "wieko", "listwy", "test_usb", "zlozenie", "rozstrzelony", "nic"

// ---------- Bateria (!) ----------
// "203450" w nazwie = 2,0 x 34 x 50 mm, ale to ok. 400 mAh. 4000 mAh przy podstawie
// 34 x 50 mm wymaga ok. 20 mm grubości - domyślnie miejsce na 20 mm. ZMIERZ swoją.
bat_x    = 34;     // szerokość
bat_y    = 50;     // długość (bez wyprowadzeń; płytka zabezpieczająca w tym wymiarze)
bat_z    = 20;     // grubość
bat_luz  = 1.0;    // luz na piankę / puchnięcie (na stronę w X; w Z nad baterią)
bat_y_zapas = 3.0; // na długości: przewody i płytka zabezpieczająca wychodzą z krótkiego boku (przy żebrze)

// ---------- Elektronika: zestaw XIAO nRF52840 + Wio-SX1262 (!) ----------
// Seeed: 8 x 22 x 23 mm (wys. x szer. x dł. z USB-C). XIAO na górze, Wio-SX1262 pod spodem.
kit_x    = 23;     // wzdłuż osi USB (gniazdo USB-C przy +X)
kit_y    = 22;
kit_z    = 8;
kit_luz  = 0.4;
usb_z    = 6.3;    // (!) środek gniazda USB-C nad spodem zestawu (XIAO na górze stosu)
usb_y    = 0;      // (!) przesunięcie środka gniazda względem środka zestawu w Y
usb_otw  = [10.6, 4.6];   // otwór w ściance (gniazdo 8,9 x 3,2; wtyk 8,3 x 2,5 + zapas)
usb_wnek = [13.5, 8.0];   // wnęka na wtyczkę od zewnątrz (obudowa wtyczki ok. 12 x 6,5)
usb_scianka = 0;          // tyle ścianki zostaje w miejscu wnęki; 0 = wnęka przez całą ściankę
                          // (przy 1 mm zwykła wtyczka nie dochodzi do gniazda o ok. 1,4 mm)

// ---------- Antena: gniazdo SMA bulkhead (pigtail U.FL -> SMA) ----------
sma_d    = 6.6;    // gwint 1/4"-36 (6,35 mm) + luz
sma_flat = 0;      // > 0: spłaszczenie otworu (np. 5,9) dla gniazd z płaskim gwintem (przeciw obracaniu)
sma_x    = 9.0;    // od lewej ścianki wnętrza; nakrętka (9,2 mm) mieści się między fazą narożnika a zestawem
sma_zc   = 11.0;   // wysokość osi nad dnem wnętrza
sma_podkl = 11;    // średnica płaskiego pola pod podkładkę/oring na zewnątrz

// ---------- MOLLE / PALS (!) ----------
pas_szer      = 25.4;  // szerokość taśmy rzędu (1")
pas_przerwa   = 25.4;  // przerwa między rzędami (1")
pas_ile       = 1;     // pod iloma rzędami idzie listwa (bloczków o 1 więcej)
petla_rozstaw = 38.1;  // rozstaw szwów (bar tack) = rozstaw listew przy 2 listwach (1,5")
listwy_ile   = 1;      // 1 = jedna listwa pośrodku (decyzja 2026-11-15), 2 = dwie co 38,1 mm
pas_grub      = 2.0;   // (!) grubość taśmy (zwykle 1,5-2 mm)
luz_pasa      = 0.6;
// listwa - geometria grotu jak w meshcore-tracker/obudowa v3 (MES: PETG SF 2,5)
listwa_szer   = 18;
listwa_gr     = 3.2;   // 2,4 mm pęka przy szarpnięciu 60 N (MES 2026-11-15: SF 0,97), 3,2 mm - zob. testy-wytrzymalosci
luz_listwy    = 0.8;
mostek_molle  = 2.0;
grot_dl       = 14;
grot_wystep   = 2.0;
zaczep_prosty = 1.2;
r_zaczepu     = 0.4;
szczelina_grotu = 6.0;
szczelina_przed = 40;
glowka_dl     = 6;
skrzydla_gr   = 3.0;   // płyta tylna (przy 2 listwach szersza niż korpus)

// ---------- Obudowa ----------
scianka   = 3.0;
dno       = 2.0;
wieko_gr  = 2.2;
wargi_gl  = 2.5;    // kołnierz wieka wchodzący we wnętrze (centruje i osłania szczelinę)
wargi_sz  = 1.2;
wargi_luz = 0.25;
faza_nar  = 4.0;    // fazy w wewnętrznych narożnikach (materiał pod wkręty)
r_zew     = 2.0;
r_kraw    = 1.4;    // zaokrąglenie wypukłych krawędzi podstawy
r_kraw_w  = 0.9;    // wieko
r_kraw_listwy = 1.0;
fn_kraw   = 20;
zebro_wys = 6;      // żebro między baterią a elektroniką
zebro_gr  = 1.6;
kabel_szer = 7;     // przejście na przewody baterii w żebrze (po lewej, przy wolnym miejscu)
wkret_otw_pod = 1.6;  // M2 do plastiku
wkret_otw_w   = 2.4;
wkret_leb_d   = 4.2;  // wpuszczenie łba w wieko
wkret_leb_gl  = 1.0;
wkret_xy      = 2.6;  // oś wkrętu od zewnętrznych krawędzi
docisk_luz    = 1.0;  // szczelina nad zestawem na podkładkę z pianki

$fn = 48;

// ---------- wymiary pochodne ----------
mar_dol  = 4.5;                         // pod baterią: faza narożnika + kołnierz wieka nie mogą dotknąć rogu baterii
mar_gora = faza_nar + 0.2;              // nad elektroniką (faza narożnika przy USB)
in_x  = max(bat_x + 2*bat_luz + 2, kit_x + 2*kit_luz + 14);
bat_zona = bat_y + bat_y_zapas;
kit_zona = kit_y + 2*kit_luz;
in_y  = mar_dol + bat_zona + zebro_gr + kit_zona + mar_gora;
in_z  = max(bat_z + bat_luz, kit_z + 4);   // od dna do spodu wieka
zew_x = in_x + 2*scianka;
zew_y = in_y + 2*scianka;

// MOLLE (bloczki w poziomych pasach, listwy pionowo wzdłuż Y)
bloczek_sz  = pas_przerwa - 1;
molle_sz    = pas_ile*(pas_szer + pas_przerwa) + bloczek_sz;
tunel_m_wys = listwa_gr + luz_listwy;
tunel_m_sz  = listwa_szer + luz_listwy;
tyl_wys     = mostek_molle + tunel_m_wys + pas_grub + luz_pasa;
plyta_x     = listwy_ile == 1 ? zew_x : max(zew_x, petla_rozstaw + tunel_m_sz + 2*3.5);
plyta_x0    = (zew_x - plyta_x)/2;
molle_y0    = (zew_y - molle_sz)/2;
listwy_x    = listwy_ile == 1 ? [zew_x/2] : [zew_x/2 - petla_rozstaw/2, zew_x/2 + petla_rozstaw/2];

z_dna  = tyl_wys + dno;                 // poziom dna wnętrza
pod_wys = tyl_wys + dno + in_z;         // wysokość podstawy (bez wieka)

// położenia we wnętrzu (współrzędne obudowy)
bat_pos = [scianka + (in_x - bat_x)/2, scianka + mar_dol, z_dna];
zebro_y = scianka + mar_dol + bat_zona;
kit_pos = [scianka + in_x - kit_luz - kit_x, zebro_y + zebro_gr + kit_luz, z_dna];
usb_c   = [zew_x, kit_pos[1] + kit_y/2 + usb_y, z_dna + usb_z];
sma_c   = [scianka + sma_x, zew_y, z_dna + sma_zc];

assert(molle_sz <= zew_y - 2, "obudowa za niska na bloczki MOLLE - zwiększ in_y albo pas_ile = 0");
assert(bloczek_sz >= 4, "przerwa między rzędami za mała na bloczki");
assert(sma_c[2] + 5 < z_dna + in_z, "gniazdo SMA zahacza o wieko");
assert(usb_c[2] + usb_wnek[1]/2 < pod_wys - 0.5, "wnęka USB zahacza o wieko");
assert(sma_x + 5 < in_x - kit_luz - kit_x, "nakrętka SMA wchodzi na zestaw - zmniejsz sma_x");

// ---------- pomocnicze ----------
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
// obrys wnętrza z fazami w narożnikach (pod wkręty)
module wnetrze_2d(off = 0) {
    f = faza_nar;
    offset(delta = off)
        polygon([[f, 0], [in_x - f, 0], [in_x, f], [in_x, in_y - f],
                 [in_x - f, in_y], [f, in_y], [0, in_y - f], [0, f]]);
}
module wkrety(d, h) {
    for (x = [wkret_xy, zew_x - wkret_xy], y = [wkret_xy, zew_y - wkret_xy])
        translate([x, y, 0]) cylinder(d = d, h = h);
}

// ---------- podstawa ----------
module tyl_molle() {
    translate([plyta_x0, 0, tyl_wys])
        linear_extrude(skrzydla_gr) translate([0, 0]) zaokr_prost(plyta_x, zew_y, r_zew);
    for (i = [0 : pas_ile])
        translate([plyta_x0, molle_y0 + i*(pas_szer + pas_przerwa), 0])
            cube([plyta_x, bloczek_sz, tyl_wys + 0.01]);
}
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

module podstawa_bryla() {
    difference() {
        union() {
            translate([0, 0, tyl_wys]) linear_extrude(dno + in_z) zaokr_prost(zew_x, zew_y, r_zew);
            tyl_molle();
        }
        // wnęka na wtyczkę USB i płaskie pole pod podkładkę SMA (przed zaokrągleniem - gładkie brzegi)
        translate([zew_x - (scianka - usb_scianka), usb_c[1] - usb_wnek[0]/2, usb_c[2] - usb_wnek[1]/2])
            rotate([90, 0, 90]) linear_extrude(scianka) zaokr_prost(usb_wnek[0], usb_wnek[1], 1.2);
    }
}

module podstawa_wyciecia() {
    // wnętrze
    translate([scianka, scianka, z_dna]) linear_extrude(in_z + 1) wnetrze_2d();
    tunele_molle();
    translate([0, 0, z_dna + 2]) wkrety(wkret_otw_pod, in_z + 1);
    // otwór USB-C
    translate([zew_x - scianka - 1, usb_c[1] - usb_otw[0]/2, usb_c[2] - usb_otw[1]/2])
        rotate([90, 0, 90]) linear_extrude(scianka + 2) zaokr_prost(usb_otw[0], usb_otw[1], 1.4);
    // otwór SMA (pionowy przy druku na stojąco)
    translate([sma_c[0], zew_y - scianka - 1, sma_c[2]]) rotate([-90, 0, 0])
        linear_extrude(scianka + 2) intersection() {
            circle(d = sma_d);
            if (sma_flat > 0) translate([-sma_d, -sma_flat/2]) square([2*sma_d, sma_flat]);
            else circle(d = sma_d);
        }
}

module podstawa_dodatki() {
    // żebro między baterią a elektroniką, z przejściem na przewody po lewej
    difference() {
        translate([scianka, zebro_y, z_dna - 0.01]) cube([in_x, zebro_gr, zebro_wys]);
        translate([scianka - 1, zebro_y - 1, z_dna + 1.5]) cube([kabel_szer + 1, zebro_gr + 2, zebro_wys]);
    }
    // narożne kołki ustalające zestaw (bez pełnych ścianek - wolny dostęp do U.FL)
    k = 1.2; h = 3;
    kx0 = kit_pos[0] - kit_luz; ky1 = kit_pos[1] + kit_y + kit_luz;
    for (p = [[kx0 - k, kit_pos[1] - kit_luz], [kx0 - k, ky1 - 4]]) translate([p[0], p[1], z_dna - 0.01]) cube([k, 4, h]);
    translate([kx0, ky1, z_dna - 0.01]) cube([4, k, h]);
    translate([kit_pos[0] + kit_x - 4, ky1, z_dna - 0.01]) cube([4 + kit_luz, k, h]);
}

module podstawa() {
    difference() {
        zaokraglij(r_kraw) podstawa_bryla();
        podstawa_wyciecia();
    }
    podstawa_dodatki();
}

// ---------- wieko ----------
module wieko() {
    // wieko w układzie obudowy: spód wieka na Z = 0 (potem przesunięte na pod_wys)
    difference() {
        union() {
            zaokraglij(r_kraw_w) linear_extrude(wieko_gr) zaokr_prost(zew_x, zew_y, r_zew);
            // kołnierz wchodzący we wnętrze
            translate([scianka, scianka, -wargi_gl]) linear_extrude(wargi_gl + 0.01)
                difference() {
                    wnetrze_2d(-wargi_luz);
                    wnetrze_2d(-wargi_luz - wargi_sz);
                }
            // docisk zestawu (podkładka z pianki docisk_luz)
            dz = in_z - kit_z - docisk_luz;
            translate([kit_pos[0] + kit_x/2, kit_pos[1] + kit_y/2, -dz]) cylinder(d = 6, h = dz + 0.01);
        }
        translate([0, 0, -1]) wkrety(wkret_otw_w, wieko_gr + 2);
        translate([0, 0, wieko_gr - wkret_leb_gl]) wkrety(wkret_leb_d, 2);
    }
}

// ---------- listwa (jak meshcore-tracker/obudowa v3) ----------
listwa_dl = molle_sz + 0.4;
module listwa_2d() { offset(r = 1.5) offset(delta = -1.5) listwa_2d_ostra(); }
module listwa_2d_ostra() {
    w = listwa_szer; dl = listwa_dl;
    translate([-(w + 6)/2, -glowka_dl]) square([w + 6, glowka_dl]);
    difference() {
        union() {
            translate([-w/2, -0.01]) square([w, dl + 0.02]);
            translate([0, dl]) polygon([[-w/2, 0], [w/2, 0], [w/2 - 1.5, grot_dl], [-(w/2 - 1.5), grot_dl]]);
        }
        translate([-szczelina_grotu/2, dl - szczelina_przed]) square([szczelina_grotu, grot_dl + szczelina_przed + 1]);
        translate([0, dl - szczelina_przed]) circle(d = szczelina_grotu);
    }
}
module zaczepy_2d() {
    w = listwa_szer; gw = tunel_m_sz + 2*grot_wystep;
    for (k = [-1, 1]) scale([k, 1]) translate([0, listwa_dl])
        polygon([[w/2 - 1.5, 0], [gw/2, 0], [gw/2, zaczep_prosty], [w/2 - 1.5, grot_dl]]);
}
module listwa() {
    zaokraglij(r_kraw_listwy) linear_extrude(listwa_gr) listwa_2d();
    zaokraglij(r_zaczepu) linear_extrude(listwa_gr) zaczepy_2d();
}

// ---------- modele zawartości (do podglądu i testów) ----------
module bateria() { color("royalblue", 0.85) translate(bat_pos) cube([bat_x, bat_y, bat_z]); }
module zestaw() {
    translate(kit_pos) {
        color("darkgreen") cube([kit_x - 1.5, kit_y, 1.2]);                    // Wio-SX1262
        color("seagreen") translate([0, 2, kit_z - 4.8]) cube([kit_x - 1.5, 17.8, 1.2]); // XIAO
        color("silver") translate([kit_x - 7.3, kit_y/2 + usb_y - 4.47, usb_z - 1.63]) cube([7.3, 8.94, 3.26]); // USB-C
        color("silver") translate([5, 5, kit_z - 2]) cube([10, 10, 2]);         // moduł nRF (wierzch = 8 mm)
    }
}
module sma() {
    color("gold") translate(sma_c) rotate([-90, 0, 0]) {
        translate([0, 0, -9]) cylinder(d = 6.35, h = 9 + scianka + 6);
        translate([0, 0, -scianka - 2.5]) cylinder(d = 9.2, h = 2.5, $fn = 6); // nakrętka wewnątrz
        translate([0, 0, 0]) cylinder(d = 9.2, h = 2, $fn = 6);                // kołnierz na zewnątrz
    }
}
// wtyczka USB-C wsunięta do końca (czoło obudowy wtyczki przy czole gniazda)
module wtyczka_usb() {
    czolo = kit_pos[0] + kit_x;
    color("dimgray") translate([czolo, usb_c[1], usb_c[2]]) rotate([0, 90, 0]) {
        translate([-1.2, -4.12, -6.65]) cube([2.4, 8.25, 6.65]);
        translate([-3.25, -6, 0]) cube([6.5, 12, 25]);
    }
}
module paski() {
    for (i = [0 : pas_ile - 1])
        color("tan", 0.75)
            translate([plyta_x0 - 25, molle_y0 + bloczek_sz + 0.5 + i*(pas_szer + pas_przerwa), mostek_molle + tunel_m_wys])
                cube([plyta_x + 50, pas_szer - 1, pas_grub]);
}
module listwy_na_miejscu() {
    for (x = listwy_x) color("black") translate([x, molle_y0 - 0.2, mostek_molle + luz_listwy/2]) listwa();
}

// ---------- wybór części ----------
if (czesc == "podstawa") {
    // druk FDM na stojąco, dolnym końcem (Y = 0) do stołu: tunele i otwór SMA pionowo, bez podpór
    rotate([90, 0, 0]) podstawa();
} else if (czesc == "wieko") {
    // druk płasko, frontem do stołu
    translate([0, 0, wieko_gr]) mirror([0, 0, 1]) wieko();
} else if (czesc == "listwy") {
    for (i = [0 : listwy_ile]) translate([i*(listwa_szer + 12), 0, 0]) listwa();   // + 1 zapasowa
} else if (czesc == "listwa1") {
    listwa();   // jedna listwa w układzie do MES (oś = Y, główka przy y < 0)
} else if (czesc == "przekroj") {
    // przekrój przez środek listwy (płaszczyzna YZ) - widać tunele, taśmę, baterię i zestaw
    difference() {
        union() { podstawa(); bateria(); zestaw(); sma(); paski(); listwy_na_miejscu();
                  color("orange") translate([0, 0, pod_wys + 0.01]) wieko(); }
        translate([zew_x/2, -50, -50]) cube([200, 300, 200]);
    }
} else if (czesc == "test_usb") {
    // wycinek prawej ścianki z USB, dnem i kołkami - do sprawdzenia, czy wtyczka wchodzi
    intersection() {
        podstawa();
        translate([kit_pos[0] - 4, kit_pos[1] - 3, tyl_wys + skrzydla_gr - 0.5])
            cube([zew_x - kit_pos[0] + 5, kit_y + 6, dno + in_z]);
    }
} else if (czesc == "nic") {
} else if (czesc == "rozstrzelony") {
    podstawa(); bateria(); zestaw(); sma();
    color("orange") translate([0, 0, pod_wys + 30]) wieko();
    translate([0, 0, -25]) { paski(); listwy_na_miejscu(); }
} else {
    podstawa(); bateria(); zestaw(); sma(); paski(); listwy_na_miejscu();
    color("orange", 0.9) translate([0, 0, pod_wys + 0.01]) wieko();
}

// wymiary dla rysunek.py
echo(str("WYMIARY={\"zew_x\":", zew_x, ",\"zew_y\":", zew_y, ",\"scianka\":", scianka, ",\"dno\":", dno,
    ",\"in_z\":", in_z, ",\"wieko_gr\":", wieko_gr, ",\"tyl_wys\":", tyl_wys, ",\"mostek\":", mostek_molle,
    ",\"tunel_wys\":", tunel_m_wys, ",\"tunel_sz\":", tunel_m_sz, ",\"pas_grub\":", pas_grub,
    ",\"pas_szer\":", pas_szer, ",\"bloczek\":", bloczek_sz, ",\"molle_y0\":", molle_y0,
    ",\"bat\":[", bat_pos[0], ",", bat_pos[1], ",", bat_x, ",", bat_y, ",", bat_z, "]",
    ",\"kit\":[", kit_pos[0], ",", kit_pos[1], ",", kit_x, ",", kit_y, ",", kit_z, "]",
    ",\"zebro_y\":", zebro_y, ",\"zebro_gr\":", zebro_gr, ",\"zebro_wys\":", zebro_wys, ",\"kabel\":", kabel_szer,
    ",\"usb\":[", usb_c[1], ",", usb_c[2] - z_dna, ",", usb_wnek[0], ",", usb_wnek[1], "]",
    ",\"sma\":[", sma_c[0], ",", sma_c[2] - z_dna, ",", sma_d, "]",
    ",\"listwa_sz\":", listwa_szer, ",\"listwa_gr\":", listwa_gr, ",\"listwa_dl\":", listwa_dl + glowka_dl + grot_dl,
    ",\"wkret_xy\":", wkret_xy, ",\"faza\":", faza_nar, "}"));
echo(str("OBUDOWA: korpus ", zew_x, " x ", zew_y, " mm, płyta MOLLE ", plyta_x,
         " mm, grubość ", pod_wys + wieko_gr, " mm; wnętrze ", in_x, " x ", in_y, " x ", in_z,
         "; listwa ", listwa_dl + glowka_dl + grot_dl, " mm"));
