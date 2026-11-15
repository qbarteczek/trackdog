// Test pasowania na sucho: każda para musi dać PUSTE przecięcie.
// bash test_pasowania.sh
include <obudowa.scad>
test = 0;
module W() { translate([0, 0, pod_wys + 0.01]) wieko(); }
if (test == 1) intersection() { podstawa(); bateria(); }
if (test == 2) intersection() { podstawa(); zestaw(); }
if (test == 3) intersection() { podstawa(); sma(); }
if (test == 4) intersection() { podstawa(); wtyczka_usb(); }
if (test == 5) intersection() { podstawa(); W(); }
if (test == 6) intersection() { W(); bateria(); }
if (test == 7) intersection() { W(); zestaw(); }
if (test == 8) intersection() { W(); sma(); }
if (test == 9) intersection() { podstawa(); listwy_na_miejscu(); }
if (test == 10) intersection() { podstawa(); paski(); }
if (test == 11) intersection() { listwy_na_miejscu(); paski(); }
if (test == 12) intersection() { zestaw(); sma(); }
if (test == 13) intersection() { bateria(); zestaw(); }
// 20: docisk wieka musi być 0,5-1,5 mm nad zestawem (wtedy przecięcie z podniesionym zestawem niepuste)
if (test == 20) intersection() { W(); translate([0, 0, docisk_luz + 0.2]) zestaw(); }
