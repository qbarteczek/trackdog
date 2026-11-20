#!/bin/sh
# TrackDog on Linux: adds TrackDog to the application menu.
#  - next to a built TrackDog (the tar.gz from build.py): uses that program;
#  - in the repository (desktop/): makes .venv from requirements.txt and runs from the source.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "$APPS" "$ICONS"

if [ -x "$HERE/TrackDog" ]; then
    EXEC="$HERE/TrackDog"
    ICON_SRC="$HERE/_internal/tdd/res/logo.svg"
else
    if [ ! -x "$HERE/.venv/bin/python" ]; then
        python3 -m venv "$HERE/.venv"
        "$HERE/.venv/bin/pip" install -q -r "$HERE/requirements.txt"
    fi
    EXEC="$HERE/.venv/bin/python $HERE/trackdog_desktop.py"
    ICON_SRC="$HERE/../design/logo.svg"
fi
cp "$ICON_SRC" "$ICONS/trackdog.svg"
cat > "$APPS/trackdog.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=TrackDog
GenericName=Dog tracker
GenericName[pl]=Tracker psa
Comment=Follows a dog with a LoRa tracker through a MeshCore radio
Comment[pl]=Śledzenie psa z trackerem LoRa przez radio MeshCore
Exec=$EXEC
Icon=trackdog
Categories=Utility;Network;
Terminal=false
DESK
update-desktop-database "$APPS" 2>/dev/null || true
echo "TrackDog is in the menu ($APPS/trackdog.desktop)"
echo "Bluetooth: pair the radio once with bluetoothctl (pair ADDRESS, PIN shown on the radio, default 123456)."
