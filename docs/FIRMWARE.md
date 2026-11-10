# Firmware: tracker i radia

TrackDog jest tylko odbiornikiem. Meldunki nadaje tracker z firmware
**[meshcore-tracker](https://github.com/qbarteczek/meshcore-tracker)** – forkiem MeshCore (MIT) z trybem trackera
dla Seeed SenseCAP T1000-E. Pełny opis: `TRACKER.md` w tamtym repozytorium; tutaj skrót potrzebny do uruchomienia
TrackDog i wskazówki, jak przerobić inne urządzenia MeshCore.

Nazwy w opisie są umowne: **TRK1** – tracker, **RPT1** – repeater w zasięgu domu, **BAZA1** – węzeł w domu,
**RADIO** – companion noszony przy sobie.

## 1. Tracker (T1000-E)

Gotowe pliki są w `release/` repozytorium meshcore-tracker:

| Plik | Co to |
|---|---|
| `t1000e_tracker-v1.18.0-trk6.uf2` / `-dfu.zip` | wersja sprawdzona na spacerach: meldunek co 60 s w ruchu, co 300 s w postoju |
| `t1000e_tracker-v1.18.0-trk7.uf2` / `-dfu.zip` | **nowa, jeszcze nie sprawdzona na urządzeniu**: prędkość i kurs z GPS, krótszy odstęp przy szybkim ruchu, akcelerometr |

Wgrywanie: dwuklik przycisku przy podłączaniu USB → pojawia się dysk bootloadera → skopiuj plik `.uf2`.
Klucze, kontakty i kanały zostają. Powrót do zwykłego MeshCore: wgraj oryginalny companion.

Konfiguracja (aplikacja MeshCore w oknie Bluetooth trackera albo `set_custom_var`):

| Zmienna | Wartość |
|---|---|
| `tracker` | `1` – tryb trackera |
| `trk_ch` | nazwa kanału z meldunkami (domyślnie `Pies`) |
| `trk_path` | trasa pierwszej kopii przez repeater, np. `a1`; `-` = tylko zero-hop |
| `trk_still` | odstęp w postoju, s (300) |
| `trk_move` | odstęp w ruchu, s (60) |
| `trk_fast` | odstęp powyżej 7 km/h, s (30) – od trk7 |
| `trk_acc` | `1` – akcelerometr budzi tracker z postoju – od trk7 |

Kanał (nazwa + 16-bajtowy sekret) musi być dodany na trackerze i na każdym odbiorniku. Sekret jest kluczem do
pozycji psa – nie publikuj go.

### Co zmienia trk7

- **Prędkość i kurs** z GPS (zdanie RMC) trafiają do meldunku: `5,4km/h k270`. TrackDog pokazuje je i rysuje
  wykres; przy starszym firmware liczy prędkość sam z kolejnych pozycji.
- **Trzy odstępy**: postój 300 s, chód 60 s, powyżej 7 km/h 30 s (histereza: wraca poniżej 5 km/h).
  Krócej niż 30 s nie ma sensu: dwie kopie meldunku to około 2,4 s nadawania, a w paśmie 869,4–869,65 MHz
  wolno nadawać najwyżej 10 % czasu.
- **Akcelerometr** (QMA6100P w T1000-E, odczyt 4 razy na sekundę): gdy tracker stoi i poczuje co najmniej 2 s
  ciągłego ruchu, melduje od razu, zamiast czekać do końca 5 minut (najwyżej raz na minutę). W meldunku jest też
  wskaźnik aktywności `a0`–`a99` (średnia zmiana przyspieszenia) – do odróżniania leżenia, chodu i biegu przy
  analizie wędrówek.
- Akcelerometr **nigdy nie wydłuża odstępu**. Jeśli czujnik nie odpowie albo się zawiesi, tracker działa jak trk6.

## 2. Radio przy sobie

Zwykły **companion MeshCore z Bluetooth** – bez modyfikacji. Wystarczy:

1. te same ustawienia radia co tracker (częstotliwość, pasmo, SF, CR),
2. kanał trackera dodany w oficjalnej aplikacji MeshCore (nazwa + sekret),
3. zmieniony PIN Bluetooth.

TrackDog rozpoznaje meldunki po treści, na dowolnym kanale – w aplikacji nie wpisuje się ani nazwy kanału,
ani sekretu.

Companion trzyma nieodebrane wiadomości w pamięci RAM (`OFFLINE_QUEUE_SIZE`, w gotowych wersjach dla nRF52 256
pozycji; po zapełnieniu wypadają najstarsze wiadomości z kanałów, po restarcie znika wszystko). Dlatego ślad
powstaje w telefonie, a nie w radiu: TrackDog opróżnia kolejkę na bieżąco.

## 3. Inne urządzenia MeshCore

### Tracker na innej płytce

Tryb trackera to dwa pliki w `examples/companion_radio/` (`TrackerMode.h/.cpp`) włączane flagą `-D TRACKER_MODE=1`.
Żeby dodać go do innej płytki z GPS:

1. W `variants/<płytka>/platformio.ini` dodaj środowisko dziedziczące po companionie BLE:
   ```ini
   [env:moja_plytka_tracker]
   extends = env:moja_plytka_companion_radio_ble
   build_flags = ${env:moja_plytka_companion_radio_ble.build_flags}
     -D TRACKER_MODE=1
   ```
2. Płytka musi mieć `LocationProvider` (GPS przez `MicroNMEALocationProvider`) i najlepiej przycisk
   (`PIN_USER_BTN`) – bez przycisku nie będzie okna Bluetooth na żądanie, tylko 3 minuty po włączeniu.
3. Radio musi umieć `sleepRadio()` / `wakeRadio()` (jest dla SX126x w `RadioLibWrappers`).
4. Akcelerometr jest opcjonalny: `TrackerAccel.h` obsługuje QMA6100P (`HAS_QMA6100P`); dla innego układu wystarczy
   druga klasa z tymi samymi metodami (`begin`, `poll`, `movingNow`, `activity`).

### Repeater na trasie

Bez zmian w firmware. Tracker wysyła pierwszą kopię meldunku po stałej trasie (`trk_path` = skrót klucza repeatera),
więc repeater przekazuje ją raz, a sieć nie jest zalewana floodem.

### Węzeł w domu

Zwykły companion na USB + własny skrypt, który czyta kanał i przekazuje pozycje dalej (np. do Traccara protokołem
OsmAnd). Format meldunku: [PROTOCOL.md](PROTOCOL.md). Nowe pola trk7 są dopisane w środku meldunku tak, żeby
parser oparty na wyrażeniach regularnych (jak w TrackDog) ich nie zauważył, jeśli ich nie zna.

## Budowanie firmware

```
pio run -e t1000e_tracker
python bin/uf2conv/uf2conv.py .pio/build/t1000e_tracker/firmware.hex -c -f 0xADA52840 -o firmware.uf2
```
