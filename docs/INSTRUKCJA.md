# Instrukcja użytkowania

Co jest potrzebne: [SPRZET.md](SPRZET.md). Wgrywanie i ustawienia firmware: [FIRMWARE.md](FIRMWARE.md).

## 1. Przygotowanie (raz)

1. **Tracker**: wgraj firmware trackera, ustaw nazwę, radio, kanał i tryb trackera ([FIRMWARE.md](FIRMWARE.md)).
2. **Radio przy sobie**: zwykły companion MeshCore z Bluetooth. W oficjalnej aplikacji MeshCore ustaw te same
   parametry radia co na trackerze, dodaj kanał trackera (nazwa + sekret) i zmień PIN Bluetooth.
3. **Telefon**: zainstaluj TrackDog z pliku APK (`release/` w repozytorium). Android zapyta o zgodę na instalację
   z tego źródła. Kolejne wersje instaluj tak samo – wchodzą jako aktualizacja, ślad i mapy zostają.
4. Przy pierwszym uruchomieniu zgódź się na: **urządzenia w pobliżu** (Bluetooth), **lokalizację** (odległość
   i kierunek do psa liczone są od pozycji telefonu) i **powiadomienia**.
5. **Urządzenie → Wybierz radio (Bluetooth)** → wskaż swoje radio (nie tracker) → podaj PIN radia.
   W nagłówku pojawi się zielona kropka z nazwą radia.
6. **Urządzenie → Pobierz mapę Polski** (1,5 GB, przez Wi-Fi) albo **Dodaj mapę z pliku** dla innego kraju.
   Bez mapy aplikacja działa, tylko ślad jest rysowany na pustym tle.
7. W ustawieniach Androida: *Aplikacje → TrackDog → Bateria → Bez ograniczeń*. Inaczej system uśpi usługę
   po zgaszeniu ekranu i meldunki będą czekać w radiu.

Oficjalną aplikację MeshCore trzeba rozłączyć z radiem – radio obsługuje jedno połączenie Bluetooth naraz.

## 2. Przed spacerem

1. Włącz tracker (krótkie naciśnięcie przycisku). Przez 3 minuty po włączeniu ma otwarte okno Bluetooth do
   konfiguracji, potem wysyła meldunek „start” i zaczyna pracę. **Nie łącz telefonu z trackerem** – dopóki
   aplikacja jest z nim połączona, tracker nie melduje.
2. Włącz radio i weź je ze sobą. TrackDog połączy się sam (powiadomienie „połączono”).
3. Poczekaj na pierwszy meldunek z pozycją – na dworze zwykle minuta–dwie.

## 3. W czasie spaceru

Tracker sam decyduje, jak często melduje:

| Stan | Odstęp | Kiedy |
|---|---|---|
| stoi | 5 min | 3 minuty bez przesunięcia o 40 m |
| idzie | 1 min | pies się przemieszcza |
| biegnie | 30 s | prędkość powyżej 7 km/h (firmware trk7) |

Gdy pies ruszy z postoju, akcelerometr budzi tracker od razu (trk7), więc nie czekasz 5 minut na pierwszą pozycję.

### Zakładka Kompas

- Tarcza obraca się z telefonem; **głowa psa na obwodzie** pokazuje, w którą stronę iść. Trzymaj telefon poziomo.
- W środku odległość w linii prostej, pod nią kierunek (np. `NE · 47°`).
- „ostatnia znana pozycja · 12 min temu” oznacza, że nowszego meldunku z pozycją nie ma – pies mógł się oddalić.
- Kafelki: prędkość, bateria trackera, liczba satelitów i temperatura, siła sygnału (SNR; im bliżej zera
  i wyżej, tym lepiej, poniżej około −10 dB łączność jest na granicy).
- **Pokaż w Organic Maps** otwiera pozycję psa w aplikacji z mapą i nawigacją.

Jeśli kompas pokazuje zły kierunek, skalibruj czujnik telefonu: zatocz nim kilka ósemek w powietrzu.

### Zakładka Ślad

- Trasa wybranego dnia na mapie: szary – postój, żółty – chód, czerwony – bieg. Białe kółko to początek,
  złote – pies teraz, niebieskie – Ty.
- Mapę przesuwasz i powiększasz palcami; **◎** wraca do całego śladu.
- Strzałki ‹ › zmieniają dzień. Obok daty: liczba meldunków odebranych i zgubionych.
- Pod mapą wykres prędkości, dystans, czas w ruchu, prędkość średnia i największa.
- **Otwórz ślad w Organic Maps** zapisuje ślad dnia jako GPX (także w `Pobrane/TrackDog`) i otwiera go.

Zakładki zmienia się przyciskami na dole albo przesunięciem palca w bok (na mapie przesunięcie rusza mapą).

### Powiadomienia

- Stałe powiadomienie pokazuje ostatni meldunek i stan połączenia z radiem – widać je bez otwierania aplikacji.
- **SOS** i **słaba bateria trackera** (≤ 10 %) dają osobny, głośny alarm.

## 4. Przycisk trackera (T1000-E)

| Naciśnięcie | Co robi | Potwierdzenie |
|---|---|---|
| 1× krótko | meldunek od razu | 1 mignięcie |
| 2× krótko | meldunek „OK” | 2 mignięcia |
| 3× krótko | **SOS**: meldunek co 30 s przez 15 min | 4 mignięcia + długi sygnał |
| 3× krótko w czasie SOS | koniec SOS | 2 krótkie sygnały |
| przytrzymaj 2–6 s | okno Bluetooth na 10 min (konfiguracja) | 3 mignięcia |
| przytrzymaj ponad 6 s | wyłączenie | 5 mignięć |
| naciśnij, gdy wyłączony | włączenie | – |

Bateria trackera: 2 krótkie sygnały przy 20 %, 3 sygnały przy 10 % (wtedy melduje najwyżej co 10 minut).

## 5. Po spacerze

- Wyłącz tracker (przytrzymaj ponad 6 s) albo zostaw włączony – w domu melduje co 5 minut.
- Ładowanie trackera: kabel magnetyczny. Według obliczeń przy 2 godzinach spaceru dziennie bateria wystarcza
  na kilka dni – sprawdź u siebie.
- Ślad zostaje w telefonie. **Urządzenie → Usuń zapisany ślad** kasuje wszystko.

## 6. Gdy coś nie działa

| Objaw | Co sprawdzić |
|---|---|
| Kropka w nagłówku żółta, „czekam na radio…” | radio wyłączone, rozładowane albo poza zasięgiem Bluetooth (kilka metrów); czy nie jest z nim połączona oficjalna aplikacja MeshCore |
| „parowanie: podaj PIN” i nic dalej | odrzucone okno z PIN-em; w ustawieniach Bluetooth Androida usuń radio z listy i wybierz je ponownie w TrackDog |
| Połączono, ale „brak meldunków” | czy na radiu jest kanał trackera z tym samym sekretem; czy radio i tracker mają te same parametry (częstotliwość, pasmo, SF, CR); czy tracker jest włączony i nie ma otwartego okna Bluetooth |
| Meldunki przychodzą tylko przy włączonym ekranie | wyłącz oszczędzanie baterii dla TrackDog (punkt 1.7) |
| „brak GPS” w stanie | tracker jest w budynku albo pod gęstą osłoną; pokazywana jest ostatnia znana pozycja |
| „czekam na GPS telefonu” | włącz lokalizację w telefonie i wyjdź pod gołe niebo |
| Dużo zgubionych meldunków | słaby sygnał (kafelek SNR); nieś radio wyżej, załóż lepszą antenę |
| Mapa pusta w miejscu śladu | ślad jest poza obszarem wczytanej mapy – dodaj mapę tego kraju |
| Nowa wersja nie chce się zainstalować | plik pochodzi z innego źródła niż poprzednia wersja (inny podpis); trzeba raz odinstalować starą – ślad wtedy przepada |

## 7. Tryb pokazowy

**Urządzenie → Tryb pokazowy** uruchamia symulowany spacer. Służy do obejrzenia aplikacji bez sprzętu;
po wyłączeniu dane pokazowe znikają.
