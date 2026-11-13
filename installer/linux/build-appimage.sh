#!/usr/bin/env bash
# Pack the PyInstaller build (backend/dist/KnifeForge Pro) into a single AppImage:
# one file to download, make executable and double-click, on any recent x86_64 distribution.
#
#   installer/linux/build-appimage.sh <version> <path to appimagetool>
#
# Output: installer/output/KnifeForge-Pro-<version>-x86_64.AppImage
set -euo pipefail

version="$1"
appimagetool="$2"
root="$(cd "$(dirname "$0")/../.." && pwd)"
build="$root/backend/dist/KnifeForge Pro"
appdir="$root/installer/output/KnifeForge.AppDir"

[ -x "$build/KnifeForge Pro" ] || { echo "Build the program first (PyInstaller)"; exit 1; }

rm -rf "$appdir"
mkdir -p "$appdir/usr/lib/knifeforge"
cp -a "$build/." "$appdir/usr/lib/knifeforge/"

cat > "$appdir/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/knifeforge/KnifeForge Pro" "$@"
EOF
chmod +x "$appdir/AppRun"

cat > "$appdir/knifeforge-pro.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=KnifeForge Pro
Comment=Gestion d'atelier pour couteliers
Exec=knifeforge-pro
Icon=knifeforge-pro
Categories=Office;Graphics;
Terminal=false
EOF

# the largest image of the Windows icon, as the PNG the desktop shows
python3 - "$root/backend/desktop/icon.ico" "$appdir/knifeforge-pro.png" <<'EOF'
import sys
from PIL import Image

icon = Image.open(sys.argv[1])
icon.size = max(icon.ico.sizes())
icon.load()
icon.save(sys.argv[2])
EOF

mkdir -p "$root/installer/output"
# no FUSE on build machines: run the tool from its extracted copy
ARCH=x86_64 "$appimagetool" --appimage-extract-and-run "$appdir" "$root/installer/output/KnifeForge-Pro-$version-x86_64.AppImage"
rm -rf "$appdir"
