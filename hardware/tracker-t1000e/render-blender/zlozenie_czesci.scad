// eksport części obudowy w położeniu złożenia (do renderu w Blenderze); czesc="nic" z linii poleceń
include <t1000e-obroza.scad>
eks = "podstawa";
if (eks == "podstawa") podstawa();
if (eks == "ramka") translate([0, 0, tyl_wys + pod_wys + 0.01]) ramka();
if (eks == "karta") karta();
if (eks == "listwy") for (x = listwy_x) translate([x, molle_y0 - 0.2, mostek_molle + luz_listwy/2]) listwa();
if (eks == "paski") for (i = [0 : pas_ile - 1])
    translate([-25, molle_y0 + bloczek_sz + 0.5 + i*(pas_szer + pas_przerwa), mostek_molle + tunel_m_wys]) cube([zew_dl + 50, pas_szer - 1, pas_grub]);
