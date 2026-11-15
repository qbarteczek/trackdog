// Schemat montażu obudowy T1000-E na kamizelce MOLLE - renderowane obrazy ze strzałkami.
// Korzysta z bryły z t1000e-obroza.scad (te same wymiary).
//   openscad -D 'scena="zakladanie"'  --camera=... -o podglad/schemat-zakladanie.png schemat-montazu.scad
//   openscad -D 'scena="zdejmowanie"' --camera=... -o podglad/schemat-zdejmowanie.png schemat-montazu.scad
include <t1000e-obroza.scad>
czesc = "nic";          // nie rysuj części z pliku głównego
scena = "zakladanie";   // "zakladanie" albo "zdejmowanie"
KAT = 0;                // obrót napisów do kamery (kąt Z kamery)

wysun_obudowe = 55;     // o ile obudowa jest uniesiona w widoku rozstrzelonym
wysun_listwy  = 125;     // o ile listwy są wysunięte w bok
kol_strz = [0.86, 0.16, 0.12];
kol_kam  = [0.62, 0.55, 0.40];
kol_pas  = [0.42, 0.34, 0.20];

// strzałka od punktu a do punktu b
module strzalka(a, b, d = 4) {
    v = b - a; L = norm(v); g = min(12, L*0.45);
    color(kol_strz) translate(a)
        rotate([0, acos(v[2]/L), atan2(v[1], v[0])]) {
            cylinder(d = d, h = L - g, $fn = 24);
            translate([0, 0, L - g]) cylinder(d1 = d*2.8, d2 = 0, h = g, $fn = 24);
        }
}
// numer kroku / opis, stojący pionowo, obrócony do kamery
module napis3d(t, p, kat = 0, wys = 7, lustro = false) {
    color([0.1, 0.1, 0.1]) translate(p) rotate([90, 0, kat]) mirror([0, lustro ? 1 : 0, 0])
        linear_extrude(1.2) text(t, size = wys, font = "Liberation Sans:style=Bold", halign = "center");
}

module kamizelka(pasy_na_listwach = true) {
    color(kol_kam) translate([-40, molle_y0 - 30, -2]) cube([zew_dl + 80, molle_sz + 60, 2]);
    for (i = [0 : pas_ile - 1]) {
        y = molle_y0 + bloczek_sz + 0.5 + i*(pas_szer + pas_przerwa);
        z = pasy_na_listwach ? mostek_molle + tunel_m_wys : 0;
        color(kol_pas) translate([-40, y, z]) cube([zew_dl + 80, pas_szer - 1, pas_grub]);
        // szwy co petla_rozstaw (między listwami i na zewnątrz)
        for (k = [-2 : 2])
            color([0.25, 0.2, 0.1]) translate([zew_dl/2 + k*petla_rozstaw - 0.6, y - 0.2, z + pas_grub - 0.3])
                cube([1.2, pas_szer - 0.6, 0.5]);
    }
}

module obudowa_zlozona() {
    podstawa();
    karta();
    color("orange") translate([0, 0, tyl_wys + pod_wys + 0.01]) ramka();
}

if (scena == "zakladanie") {
    kamizelka(pasy_na_listwach = false);
    // 1. obudowa nad kamizelką - bloczki wchodzą w przerwy między paskami
    translate([0, 0, wysun_obudowe]) obudowa_zlozona();
    for (x = [-14, zew_dl + 14])
        strzalka([x, zew_sz/2, wysun_obudowe + 4], [x, zew_sz/2, 4]);
    napis3d("1", [zew_dl + 14, zew_sz/2 - 14, wysun_obudowe/2], kat = KAT, wys = 16);
    // 2. listwy wysunięte w bok; strzałka od czubka grotu do wejścia tunelu w pierwszym bloczku
    czubek = molle_y0 - wysun_listwy + molle_sz + 0.4 + grot_dl;
    for (x = listwy_x) {
        color([0.12, 0.12, 0.12]) translate([x, molle_y0 - wysun_listwy, mostek_molle + luz_listwy/2]) listwa();
        strzalka([x, czubek + 3, mostek_molle + 2], [x, molle_y0 - 2, mostek_molle + 2]);
    }
    napis3d("2", [listwy_x[0] - 22, czubek + 4, 4], kat = KAT, wys = 16);
} else {
    // po złożeniu, widok od spodu (od strony psa) bez materiału kamizelki
    obudowa_zlozona();
    kamizelka_bez_materialu = true;
    for (i = [0 : pas_ile - 1])
        color(kol_pas) translate([-40, molle_y0 + bloczek_sz + 0.5 + i*(pas_szer + pas_przerwa), mostek_molle + tunel_m_wys])
            cube([zew_dl + 80, pas_szer - 1, pas_grub]);
    for (x = listwy_x)
        color([0.12, 0.12, 0.12]) translate([x, molle_y0 - 0.2, mostek_molle + luz_listwy/2]) listwa();
    // ściśnij ramiona grotu
    gy = molle_y0 + molle_sz + 9;
    for (x = listwy_x, s = [-1, 1])
        strzalka([x + s*30, gy, mostek_molle + 1.5], [x + s*12, gy, mostek_molle + 1.5], d = 3.5);
    napis3d("3", [listwy_x[1] + 40, gy + 4, -4], kat = KAT, wys = 16, lustro = true);
    // wyciągnij za główkę
    for (x = listwy_x)
        strzalka([x, molle_y0 - 10, -6], [x, molle_y0 - 40, -6]);
    napis3d("4", [listwy_x[0] - 26, molle_y0 - 30, -8], kat = KAT, wys = 16, lustro = true);
}
