# Firmware

[meshcore-tracker/](meshcore-tracker/) to submoduł git: fork MeshCore (MIT) z trybem trackera dla SenseCAP T1000-E,
z własną historią i zdalnym `upstream` = meshcore-dev/MeshCore. Opis: `TRACKER.md` w submodule, skrót dla
TrackDog: [docs/FIRMWARE.md](../docs/FIRMWARE.md). Gotowe pliki `.uf2` są w `release/` submodułu.

Pobranie (repozytorium MeshCore jest duże, więc płytko):

```
git submodule update --init --depth 1 firmware/meshcore-tracker
```

Budowa: PlatformIO w `firmware/meshcore-tracker`, `pio run -e t1000e_tracker`.
