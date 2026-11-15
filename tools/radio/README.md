# Narzędzia radiowe (PC ↔ MeshCore)

Skrypty w Pythonie do przygotowania trackera i radia przez Bluetooth LE albo USB. Wymagają biblioteki
`meshcore` (`pip install meshcore bleak`). Na Windows parowanie z PIN-em działa przez WinRT: jeśli obok tego
repozytorium leży [MeshCore Desktop](https://github.com/qbarteczek/meshcore-desktop) (albo `$MESHCORE_DESKTOP`
wskazuje na niego), skrypty biorą z niego `ble_pair`; najprościej uruchamiać je pythonem z jego `.venv`.
Bez niego sparuj radio raz w ustawieniach Bluetooth systemu (PIN domyślnie 123456).

| Skrypt | Co robi |
|---|---|
| [configure_radio.py](configure_radio.py) | prywatny kanał trackera na radiu (`--new-channel` tworzy sekret, `--channel-file` go wgrywa), nazwa, radio, moc; z `--tracker` tryb trackera (`tracker`, `trk_ch`, `trk_path`, odstępy) |
| [listen_channel.py](listen_channel.py) | podgląd meldunków z kanału na komputerze (zabiera je z kolejki radia, jak aplikacja) |
| [fix_clock.py](fix_clock.py) | sprawdza i naprawia zegar companiona (zły zegar przeżywa restart przez `lastmod` kontaktów) |
| [set_coding_rate.py](set_coding_rate.py) | zmiana coding rate (CR) kilku radiów naraz |
| [../strip_exif_gps.py](../strip_exif_gps.py) | usuwa pozycję GPS z EXIF zdjęć przed publikacją |

Typowe przygotowanie (nazwy umowne jak w [docs/FIRMWARE.md](../../docs/FIRMWARE.md)):

```
python configure_radio.py scan --new-channel ~/pies.secret --name TRK1 --tracker --path a1
python configure_radio.py AA:BB:CC:DD:EE:FF --channel-file ~/pies.secret          # RADIO przy sobie
python listen_channel.py AA:BB:CC:DD:EE:FF --minutes 10
```

**Pliku z sekretem kanału nie trzymaj w publicznym repozytorium** – każdy, kto go ma, widzi pozycję psa.
`*.secret` i kopie kontaktów (`contacts-*.json`) są w `.gitignore`.
