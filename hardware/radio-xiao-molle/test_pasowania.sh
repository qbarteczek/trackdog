#!/bin/bash
# Symulacja geometryczna pasowania (OpenSCAD 2025 z Manifold).
cd "$(dirname "$0")"
# OpenSCAD 2025+ (Manifold): zmienna OPENSCAD albo openscad w PATH
OS=${OPENSCAD:-openscad}
nazwy=([1]="bateria w podstawie" "zestaw w podstawie" "gniazdo SMA w otworze" "wtyczka USB-C wsunięta do końca"
       "wieko na podstawie" "wieko / bateria" "wieko / zestaw" "wieko / SMA" "listwy zatrzaśnięte w tunelach"
       "taśma PALS pod płytą" "listwy / taśma" "zestaw / SMA" "bateria / zestaw")
zle=0
t=$(mktemp -d)
for i in $(seq 1 13) 20; do
  "$OS" --backend=Manifold --export-format=binstl -D czesc=\"nic\" -D test=$i -o "$t/t$i.stl" test_pasowania.scad >/dev/null 2>&1
  v=$(${PYTHON:-python} objetosc.py "$t/t$i.stl")
  # styk powierzchni (objętość ~0) to nie kolizja
  if ${PYTHON:-python} -c "import sys; sys.exit(0 if $v < 0.01 else 1)"; then pusty=1; else pusty=0; fi
  if [ $i -eq 20 ]; then
    [ $pusty -eq 0 ] && echo "OK    docisk wieka nad zestawem w zakresie" || { echo "BŁĄD  docisk wieka za wysoko"; zle=1; }
  else
    [ $pusty -eq 1 ] && echo "OK    ${nazwy[$i]}" || { echo "BŁĄD  ${nazwy[$i]} - kolizja $v mm3"; zle=1; }
  fi
done
rm -rf "$t"
exit $zle
