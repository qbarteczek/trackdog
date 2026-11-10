#!/usr/bin/env bash
# Offline map for TrackDog (Mapsforge .map) from an OpenStreetMap extract of Geofabrik.
#
#   tools/make_map.sh europe/poland/mazowieckie [europe/poland/lubelskie ...]
#
# Needs Java 17+ and curl. Downloads Osmosis and the Mapsforge map-writer plugin on first use.
# Work files go to $TRACKDOG_MAPS (default: ~/trackdog-maps), the finished <region>.map too.
# Copy the .map to the phone and load it in TrackDog: Device -> Add an offline map.
# Map data (c) OpenStreetMap contributors, ODbL.
set -euo pipefail

WORK="${TRACKDOG_MAPS:-$HOME/trackdog-maps}"
OSMOSIS_VER=0.49.2
WRITER_VER=0.25.0
mkdir -p "$WORK"
cd "$WORK"

if [ ! -d "osmosis-$OSMOSIS_VER" ]; then
  curl -L --fail -o osmosis.tar "https://github.com/openstreetmap/osmosis/releases/download/$OSMOSIS_VER/osmosis-$OSMOSIS_VER.tar"
  tar xf osmosis.tar && rm osmosis.tar
fi
OSMOSIS="$WORK/osmosis-$OSMOSIS_VER"
PLUGIN="mapsforge-map-writer-$WRITER_VER-jar-with-dependencies.jar"
# Osmosis loads plugins from its lib folder (they are on the classpath of the start script)
if [ ! -f "$OSMOSIS/lib/$PLUGIN" ]; then
  curl -L --fail -o "$OSMOSIS/lib/$PLUGIN" "https://repo1.maven.org/maven2/org/mapsforge/mapsforge-map-writer/$WRITER_VER/$PLUGIN"
fi

export JAVA_OPTS="${JAVA_OPTS:--Xmx6g}"
for region in "$@"; do
  name="$(basename "$region")"
  [ -f "$name.osm.pbf" ] || curl -L --fail -o "$name.osm.pbf" "https://download.geofabrik.de/$region-latest.osm.pbf"
  # type=hd keeps the work data on disk, so a region fits in a few GB of RAM
  CLASSPATH="$OSMOSIS/lib/*" java $JAVA_OPTS -cp "$OSMOSIS/lib/*" org.openstreetmap.osmosis.core.Osmosis \
    --rb file="$name.osm.pbf" \
    --mapfile-writer file="$name.map" type=hd threads=4 comment="TrackDog, OpenStreetMap contributors"
  ls -la "$name.map"
done
