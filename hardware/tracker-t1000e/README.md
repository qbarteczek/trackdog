# Obudowa T1000-E na kamizelkę MOLLE (lub obrożę)

Obudowa na SenseCAP Card Tracker T1000-E (85 × 55 × 6,5 mm) do taktycznej kamizelki psa
z paskami MOLLE na grzbiecie (szelki z AliExpress, rozmiar L). Grzbiet to najlepsze miejsce
dla GPS. Plik źródłowy: [t1000e-obroza.scad](t1000e-obroza.scad), gotowe pliki: [stl/](stl/).

- **podstawa**: kieszeń na tracker, a z tyłu 3 bloczki, które wchodzą w przerwy między
  paskami kamizelki, z tunelami na listwy. Ma też okno na magnetyczne styki ładowania.
- **ramka**: front z otworami na przycisk, diodę/czujnik światła i brzęczyk, przykręcany 4 wkrętami
  M2 × 8 do plastiku
- **listwy** (2 sztuki + 1 zapasowa): idą w poprzek psa przez bloczek, pod paskiem kamizelki,
  przez bloczek, pod paskiem i przez bloczek. Na końcu zatrzaskują się rozdwojonym grotem
  (ramiona 40 mm, zaczep wystaje 2 mm poza tunel i opiera się płasko o bloczek ok. 1 mm poza fazą tunelu).
  Żeby zdjąć, ściśnij grot palcami (ok. 6,5 N na ramię w PETG) i wysuń listwę za główkę.

Wszystkie wypukłe krawędzie są zaokrąglone, żeby nic nie drapało psa i nie przecierało kamizelki:
podstawa r 1,4 mm (tunele na listwy są wycinane po zaokrągleniu, więc mostki pod listwami, 2 mm, zostają pełne), ramka r 0,9 mm, listwy r 1,0 mm,
a naroża listew w płaszczyźnie 1,5 mm. Wyjątek: zaczepy grotu mają tylko r 0,4 mm, bo większe zaokrąglenie
zjada płaską półkę zaczepu i listwa zsuwa się po fazie tunelu (tak było do 2026-11-06). Robi to moduł `zaokraglij()`. Kieszeń i otwory na wkręty są
wycinane po zaokrągleniu, bo po złożeniu są zakryte. Zbliżenia: [podglad/krawedzie.png](podglad/krawedzie.png).

Wymiary: 91,6 mm wzdłuż grzbietu × 79 mm w poprzek (korpus 61,6 mm, płyta z bloczkami 79 mm),
grubość ok. 17,5 mm (nad listwą jest miejsce na pasek kamizelki).

Schemat montażu krok po kroku: [montaz-molle.html](montaz-molle.html).

Ładowanie: wysuń listwy, zdejmij obudowę z kamizelki i przyłóż kabel magnetyczny do okna z tyłu.
Nie trzeba jej rozkręcać. Przy wsuniętych listwach się nie da: na kamizelce okno zakrywa pasek,
a listwy zachodzą po ok. 4 mm na końce okna (wolne zostaje 17 mm, wtyczka jest większa).

Wariant na obrożę: `-D 'mocowanie="obroza"'` (plik [stl/podstawa-obroza.stl](stl/podstawa-obroza.stl), obroża do 25 × 3,5 mm).

## Do zmierzenia przed drukiem

Na kamizelce (suwmiarką):

| Parametr | Co zmierzyć | Domyślnie |
|---|---|---|
| `pas_szer` | szerokość paska taśmy na grzbiecie | 25 |
| `pas_przerwa` | przerwa między sąsiednimi paskami | 10 |
| `petla_rozstaw` | odstęp między szwami (przeszyciami) na pasku, czyli długość pętli | 38,1 |
| `pas_ile` | pod iloma paskami ma iść listwa (bloczków jest o 1 więcej) | 2 |

Na trackerze: otwory i okno ładowania są według rysunku wymiarowego z karty katalogowej Seeed
i zdjęć urządzenia (2026-10-28): przycisk 18,4 mm od oczka (nakładka Ø 13,6 mm, otwór Ø 16),
świetlik 36,9 mm, brzęczyk 52,6 mm; 4 piny ładowania w kapsule 17,3 × 5,2 mm, 14 mm od długiego boku.
Położenie pinów wzdłuż karty różni się między rysunkiem (35,6 mm od oczka) a zdjęciem (ok. 43 mm),
więc okno ma 26 mm długości i obejmuje oba. Najpierw wydrukuj samą ramkę i podstawę na próbę.

## Druk

| Część | Ułożenie FDM | Materiał |
|---|---|---|
| podstawa | na stojąco, na krótszym końcu (bez podpór), z brimem | PETG lub ASA |
| ramka | płasko, frontem do stołu | PETG / ASA |
| listwy | płasko | **PETG** albo nylon (PA). Nie PLA (1,8% odkształcenia przy dopuszczalnych 1,2% - pęka po wielu zdjęciach) |

Żywica (Photon): użyj żywicy wytrzymałej (tough/ABS-like), a listwy i tak wydrukuj na FDM.

## Symulacja i testy

- `python3 symulacja_zatrzasku.py` – wytrzymałość grotu listwy dla PLA i PETG: odkształcenie u nasady
  ramienia (z karbem), siła ściśnięcia palcami, wkładania i czy zaczep trzyma. Pierwsza wersja
  (ramiona 12 mm, szczelina 2,6 mm) dawała 12,9% odkształcenia – pękłaby przy pierwszym wkładaniu;
  druga (v2): 1,2%, ale jej zaczep po zaokrągleniu nie miał płaskiej półki (pomiar STL: 0 mm poza fazą)
  i wysuwał się przy ok. 17 N. Obecna (v3, zaczepy r 0,4, wysięg 2 mm): 1,8%, oparcie ok. 1 mm,
  trzyma płasko (PETG z zapasem, PLA za słaby).
- MES z G-code (`symulacja-wydrukow`, przypadek `przyklady/listwa-molle/listwa_v3_petg.py`, ugięcie 2 mm
  na ramię, dysza 0,4, warstwa 0,2, 3 obrysy): PETG SF 2,5 (OK przy wielu cyklach), PLA SF 1,8 (za mało).
  Najbardziej wytężona jest nasada ramion przy końcu szczeliny, nie zaczep.
- `fem_listwa.py` – MES (Gmsh + scikit-fem, środowisko `~/.local/opt/fem-venv`), mapa odkształceń
  w [podglad/fem-grot.png](podglad/fem-grot.png). Nasada ramion: wersja pierwsza 4,5%, obecna 0,78%
  (PLA i PETG mieszczą się w dopuszczalnym odkształceniu); siła ściśnięcia 5,4 N (PETG) / 9 N (PLA) na ramię.
  Szczyt w narożach zaczepów to artefakt zadanego ugięcia, nie realne naprężenie.
- `bash test_pasowania.sh` – symulacja geometryczna w OpenSCAD (przecięcia brył): listwa zatrzaśnięta
  i w trakcie wsuwania, karta w kieszeni, piny ładowania względem okna, listwy względem okna.

Druk PLA: mięknie od ok. 57 °C (czarna kamizelka w słońcu, auto) – na psa lepiej PETG albo ASA.

Render (OpenSCAD 2025+ z Manifold, każda część renderuje się 5–15 s):

```
openscad --backend=Manifold --export-format=binstl -D 'czesc="podstawa"' -o stl/podstawa.stl t1000e-obroza.scad
openscad --backend=Manifold --export-format=binstl -D 'czesc="ramka"'    -o stl/ramka.stl    t1000e-obroza.scad
openscad --backend=Manifold --export-format=binstl -D 'czesc="listwy"'   -o stl/listwy.stl   t1000e-obroza.scad
```

Opcjonalnie `napis="tel. 600 000 000"` dodaje wgłębiony napis na dłuższym boku podstawy.
