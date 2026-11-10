# Meldunek trackera i protokół companiona

## Meldunek

Tracker wysyła zwykłą wiadomość tekstową na kanał grupowy MeshCore. Tekst (po nazwie węzła i `": "`):

```
TRK1: idzie 93% 4,18V 9,3°C 12sat 5,4km/h k270 a12 nr81 https://maps.google.com/?q=52.22970,21.01220
```

| Pole | Znaczenie | Od wersji |
|---|---|---|
| `idzie` | stan: `start` (pierwszy po włączeniu), `idzie`, `stoi`, `OK` (2× przycisk), `SOS` (3× przycisk), `brak GPS` | trk6 |
| `93%` `4,18V` | bateria | trk6 |
| `9,3°C` | temperatura z czujnika trackera | trk6 |
| `12sat` | liczba satelitów (tylko z fixem) | trk6 |
| `5,4km/h` | prędkość z GPS (tylko z fixem) | trk7 |
| `k270` | kurs w stopniach (tylko powyżej 2 km/h) | trk7 |
| `a12` | aktywność z akcelerometru, 0–99: średnia zmiana przyspieszenia między próbkami w jednostkach 10 mg | trk7 |
| `bateria!` | bateria ≤ 10 % | trk6 |
| `nr81` | numer meldunku od włączenia – po przerwach widać, ile meldunków nie doszło | trk6 |
| `ost.` | przed linkiem: pozycja jest ostatnią znaną, nie z tego meldunku | trk6 |
| `…?q=lat,lon` | pozycja, 5 miejsc po przecinku (około 1 m) | trk6 |

Wymagane są tylko stan i numer; reszta jest opcjonalna i może przybywać. TrackDog czyta każde pole osobnym
wyrażeniem regularnym ([Report.kt](../app/src/main/java/pl/qbart/trackdog/Report.kt), testy w
[ReportParserTest.kt](../app/src/test/java/pl/qbart/trackdog/ReportParserTest.kt)), więc nieznane pola pomija,
a zwykłą rozmowę na kanale ignoruje.

Czas meldunku to znacznik nadawcy z pakietu (zegar trackera jest ustawiany z GPS). Para (tracker, czas) jest
kluczem w bazie – ten sam meldunek odebrany drugi raz nie tworzy duplikatu.

## Protokół companiona (Bluetooth)

Usługa Nordic UART `6e400001-b5a3-f393-e0a9-e50e24dcca9e`: zapis do `…0002`, powiadomienia z `…0003`.
Jeden zapis / jedno powiadomienie = jedna ramka (do 176 bajtów, dlatego aplikacja prosi o MTU 247).
Połączenie wymaga sparowania kodem PIN radia.

TrackDog używa tylko tych ramek:

| Kierunek | Kod | Ramka | Po co |
|---|---|---|---|
| → | 22 | `CMD_DEVICE_QUERY`, wersja 3 | początek rozmowy |
| → | 1 | `CMD_APP_START`, wersja 3, 6 bajtów zapasu, nazwa aplikacji | radio odpowiada `SELF_INFO` |
| ← | 5 | `RESP_SELF_INFO` – nazwa radia od bajtu 58 | nazwa na ekranie |
| → | 6 | `CMD_SET_DEVICE_TIME`, czas uint32 LE | radio bez zegara bierze czas z telefonu (tylko do przodu) |
| → | 20 | `CMD_GET_BATT_AND_STORAGE` | |
| ← | 12 | `RESP_BATT_AND_STORAGE` – napięcie uint16 LE w mV | bateria radia |
| → | 10 | `CMD_SYNC_NEXT_MESSAGE` | „daj następną wiadomość z kolejki” |
| ← | 17 | `RESP_CHANNEL_MSG_RECV_V3`: SNR×4 (int8), 2 bajty zapasu, nr kanału, długość trasy, typ, czas uint32 LE, tekst | meldunek |
| ← | 8 | `RESP_CHANNEL_MSG_RECV` (starszy): nr kanału, długość trasy, typ, czas, tekst | meldunek |
| ← | 7, 16, 27 | wiadomość prywatna / dane kanału | pomijane, ale pobierane, żeby zwolnić kolejkę |
| ← | 10 | `RESP_NO_MORE_MESSAGES` | kolejka pusta |
| ← | 0x83 | `PUSH_MSG_WAITING` | radio ma nową wiadomość → `SYNC_NEXT` |

Po każdej odebranej wiadomości aplikacja od razu prosi o następną, aż do `NO_MORE`. Co 30 s pyta sama,
na wypadek zgubionego powiadomienia. Kody pochodzą z `examples/companion_radio/MyMesh.cpp` w MeshCore.
