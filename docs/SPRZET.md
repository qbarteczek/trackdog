# Sprzęt

TrackDog to trzy elementy: **tracker** na psie, **radio przy sobie** i **telefon**. Reszta (repeater, węzeł
w domu, serwer) jest dodatkiem, bez którego system też działa.

```
┌──────────────┐  LoRa 868 MHz   ┌───────────────────┐  Bluetooth  ┌──────────────────┐
│ tracker      │ ───────────────►│ radio przy sobie  │ ───────────►│ telefon, TrackDog │
│ (na psie)    │                 │ (companion)       │             └──────────────────┘
└──────┬───────┘                 └───────────────────┘
       │ LoRa                              opcjonalnie:
       ▼
┌──────────────┐  LoRa   ┌────────────────┐  USB  ┌─────────────────────────────┐
│ repeater     │ ───────►│ węzeł w domu   │ ─────►│ serwer: Traccar, Home Assistant │
└──────────────┘         └────────────────┘       └─────────────────────────────┘
```

## Minimum

| Element | Wymagania |
|---|---|
| Tracker | Seeed **SenseCAP T1000-E** z firmware [meshcore-tracker](https://github.com/qbarteczek/meshcore-tracker) – na razie jedyne urządzenie z gotowym plikiem firmware trackera |
| Radio przy sobie | dowolne urządzenie z firmware **MeshCore companion z Bluetooth** (bez modyfikacji), na tych samych ustawieniach radia co tracker |
| Telefon | Android 10 lub nowszy z Bluetooth LE; około 1,6 GB wolnego miejsca, jeśli chcesz mapę Polski |

## Zestaw autora

Ten zestaw jest używany na co dzień i na nim powstaje aplikacja.

| Rola | Sprzęt | Firmware | Uwagi |
|---|---|---|---|
| Tracker na psie | Seeed SenseCAP T1000-E (nRF52840 + LR1110, GPS, akcelerometr, brzęczyk, bateria 700 mAh, IP65) | meshcore-tracker `t1000e_tracker` | w drukowanej obudowie na kamizelce lub obroży (`obudowa/` w repozytorium firmware) |
| Radio przy sobie (2 szt.) | Seeed XIAO nRF52840 + Wio-SX1262 (zestaw), mała bateria Li-Po, antena 868 MHz | MeshCore companion BLE v1.18.0 | jedno w kieszeni, drugie zapasowe / dla drugiej osoby |
| Repeater | nRF52 + SX1262, panel słoneczny 5 W, na dachu | MeshCore repeater | przekazuje meldunki do domu; nie jest potrzebny do pracy aplikacji |
| Węzeł w domu | Heltec LoRa 32 V2 na USB w serwerze | MeshCore companion USB | własny skrypt przekazuje pozycje do Traccara i Home Assistanta |
| Telefon | Android z Bluetooth LE | TrackDog | |

Ustawienia radia: 869,618 MHz, pasmo 62,5 kHz, SF 8, CR 8, 22 dBm (ustawienia sieci MeshCore w Polsce).
Wszystkie urządzenia muszą mieć te same wartości.

## Inne możliwości

System jest luźno powiązany: tracker nadaje tekst na kanał, a każdy, kto ma kanał, może go odebrać. Dlatego
elementy można wymieniać.

**Radio przy sobie** – wystarczy, że jest companionem MeshCore z Bluetooth. Sprawdza się wszystko, na co MeshCore
wydaje taki firmware, np.:

- Seeed XIAO nRF52840 + Wio-SX1262 (mały i oszczędny),
- RAK WisBlock 4631, Heltec T114, LilyGo T-Echo, Seeed Wio Tracker L1 (nRF52 – małe zużycie energii),
- Heltec V3 / V4, LilyGo T-Beam, T-Deck, Station G2 (ESP32 – większy pobór prądu, częstsze ładowanie),
- drugi SenseCAP T1000-E ze zwykłym firmware companion.

Płytki z nRF52 są lepsze do kieszeni: Bluetooth i nasłuch kosztują je kilka–kilkanaście mA.

**Tracker** – tryb trackera to dodatek do firmware companion, więc da się go zbudować dla innej płytki z GPS
(np. RAK 4631 z modułem GPS, T-Beam, Wio Tracker L1, XIAO nRF52840 z modułem GPS na UART). Wymaga to własnej
kompilacji – opis w [FIRMWARE.md](FIRMWARE.md), rozdział „Tracker na innej płytce”. Bez akcelerometru tracker
działa tak samo, tylko nie budzi się wcześniej, gdy pies ruszy z postoju.

**Bez repeatera i bez domu** – tracker wysyła wtedy tylko kopię „zero-hop” (`trk_path` = `-`). To najprostszy
zestaw na wyjazd: tracker + radio + telefon.

**Kilka osób** – każdy, kto ma radio z kanałem trackera i TrackDog, widzi psa niezależnie. Jedno radio obsługuje
jeden telefon naraz.

**Kilka trackerów** – każdy tracker ma własną nazwę; aplikacja zapisuje ślady osobno, a tracker wybiera się
w zakładce Urządzenie.

**Zamiast TrackDog** – meldunki są czytelnym tekstem z linkiem do mapy, więc widać je też w oficjalnej aplikacji
MeshCore (bez śladu, kompasu i map).

## Zasięg

Między trackerem a radiem w kieszeni liczy się bezpośrednia łączność LoRa: w otwartym terenie kilka kilometrów,
w lesie i w dolinach wyraźnie mniej. Pomaga antena radia trzymana wysoko (plecak, nie kieszeń spodni).
Tracker na grzbiecie psa (kamizelka) ma lepszy zasięg niż na obroży pod szyją.

## Zgodność z przepisami

Pasmo 869,4–869,65 MHz: moc do 500 mW ERP i nadawanie przez najwyżej 10 % czasu. Firmware trackera mieści się
w tym limicie przy domyślnych odstępach; nie skracaj `trk_fast` poniżej 30 s.
