# Sprzęt do druku i montażu

Część sprzętowa systemu TrackDog: obudowy, mocowania i testy przed drukiem. Aplikacja jest w [app/](../app),
opis całego zestawu w [docs/SPRZET.md](../docs/SPRZET.md).

| Folder | Co | Stan |
|---|---|---|
| [radio-xiao-molle/](radio-xiao-molle/) | obudowa radia przy sobie (XIAO nRF52840 + Wio-SX1262, bateria LiPo 4000 mAh, gniazdo SMA, USB-C) na MOLLE/PALS, jedna listwa z zatrzaskiem | projekt gotowy, testy pasowania i MES zrobione, czeka na wydruk próbny |
| [tracker-t1000e/](tracker-t1000e/) | obudowa trackera SenseCAP T1000-E na kamizelkę MOLLE psa albo obrożę (podstawa, ramka, 2 listwy z zatrzaskiem, okno ładowania), schemat montażu, rendery | wydrukowana i używana (v3); przeniesiona 2026-11-15 z repozytorium firmware |

## Zasady dla nowych części

- Źródło w OpenSCAD (2025+, `--backend=Manifold`), wymiary do zmierzenia oznaczone w pliku `(!)`.
- **Test pasowania na sucho**: przecięcia brył w OpenSCAD (`test_pasowania.sh`), objętość kolizji ma być 0.
- **Test wytrzymałości** części z zatrzaskami, sprężynami lub obciążeniem: MES z G-code (krojenie PrusaSlicer,
  materiał ortotropowy według ścieżek). Wymagane SF ≥ 2 przy wielu cyklach, ≥ 1,5 przy obciążeniu jednorazowym.
  Przypadki są w `testy-wytrzymalosci/` każdej części.
- Na psa i na sprzęt noszony na zewnątrz: **PETG albo ASA**. PLA mięknie od ok. 57 °C, a zatrzaski z PLA
  pękają po wielu cyklach.
- Bez danych osobistych w plikach (nazwy urządzeń, współrzędne, numery telefonów), bo repozytorium jest publiczne.
