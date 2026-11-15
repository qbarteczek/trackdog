// Test pasowania obudowy (symulacja geometryczna): przecięcia brył w kluczowych sytuacjach.
// Pusty wynik = brak kolizji. Uruchamia go test_pasowania.sh (OpenSCAD 2025+ z --backend=Manifold).
//   test = "listwa_zapieta"   listwa w położeniu końcowym vs podstawa       -> pusto
//   test = "listwa_w_tunelu"  zaczep grotu w ostatnim bloczku vs podstawa  -> wcisk = ugięcie ramion
//   test = "karta"            karta w kieszeni vs podstawa                  -> pusto
//   test = "piny"             kapsuła pinów ładowania (z zapasem) vs podstawa -> pusto
//   test = "okno_listwy"      rzut listew na okno ładowania                 -> pusto = listwy nie zasłaniają okna
// czesc = "nic" podaje test_pasowania.sh (-D), bo include nadpisałby przypisanie w tym pliku
include <t1000e-obroza.scad>

test = "listwa_zapieta";
przesun = 0;   // przesunięcie listwy wzdłuż osi (ujemne = jeszcze nie dosunięta)

module listwa_w_miejscu(x, dy = 0) {
    translate([x, molle_y0 - 0.2 + dy, mostek_molle + luz_listwy/2]) listwa();
}

// kapsuła 4 pinów + 2 magnesy (17,3 x 5,2 mm wg Seeed), wydłużona o rozrzut położenia z rysunku i zdjęcia
module piny() {
    translate([each nakarte(okno_tyl_x, okno_tyl_y), -5])
        hull() for (dx = [-(17.3 + 6)/2 + 2.6, (17.3 + 6)/2 - 2.6]) translate([dx, 0, 0]) cylinder(d = 5.2, h = 40);
}

if (test == "listwa_zapieta")
    intersection() { podstawa(); for (x = listwy_x) listwa_w_miejscu(x, przesun); }
else if (test == "listwa_w_tunelu")
    intersection() { podstawa(); listwa_w_miejscu(listwy_x[0], -(bloczek_sz/2 + 0.4)); }
else if (test == "karta")
    intersection() { podstawa(); karta(); }
else if (test == "piny")
    intersection() { podstawa(); piny(); }
else if (test == "okno_listwy")
    intersection() {
        translate([each nakarte(okno_tyl_x - okno_tyl_dl/2, okno_tyl_y - okno_tyl_sz/2), -10])
            linear_extrude(60) zaokr_prost(okno_tyl_dl, okno_tyl_sz, okno_tyl_r);
        for (x = listwy_x) listwa_w_miejscu(x);
    }
