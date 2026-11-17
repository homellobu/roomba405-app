#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LAUNCHER="$PROJECT_DIR/scripts/roomba_web_launcher.py"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "No existe el entorno virtual en $VENV_DIR"
  echo "Créalo primero:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -e ."
  exit 1
fi

APP_DIR="$PROJECT_DIR/Roomba.app"
INSTALL_DIR="/Applications/Roomba.app"
ICON_SRC="$PROJECT_DIR/assets/icon.png"
mkdir -p "$APP_DIR/Contents/MacOS"

cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>           <string>Roomba</string>
    <key>CFBundleDisplayName</key>    <string>Roomba</string>
    <key>CFBundleIdentifier</key>     <string>com.homellobu.roomba-app</string>
    <key>CFBundleVersion</key>        <string>0.1.0</string>
    <key>CFBundleExecutable</key>     <string>Roomba</string>
    <key>CFBundleIconFile</key>       <string>AppIcon</string>
    <key>CFBundlePackageType</key>    <string>APPL</string>
    <key>LSMinimumSystemVersion</key> <string>11.0</string>
    <key>NSHighResolutionCapable</key> <true/>
</dict>
</plist>
PLIST

if [ -f "$ICON_SRC" ] && command -v iconutil >/dev/null && command -v sips >/dev/null; then
  ICONSET="$PROJECT_DIR/build/AppIcon.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z $d $d "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  mkdir -p "$APP_DIR/Contents/Resources"
  iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/AppIcon.icns"
fi

cat > "$APP_DIR/Contents/MacOS/Roomba" <<LAUNCHER
#!/bin/bash
exec "$VENV_DIR/bin/python" "$LAUNCHER"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/Roomba"

if mv "$APP_DIR" "$INSTALL_DIR" 2>/dev/null; then
  echo ""
  echo "✅ Aplicación instalada en: $INSTALL_DIR"
  echo "   Ya la tienes en Launchpad y en la carpeta Aplicaciones."
else
  if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR" && mv "$APP_DIR" "$INSTALL_DIR" && \
      echo "" && echo "✅ Aplicación actualizada en: $INSTALL_DIR" && exit 0
  fi
  echo ""
  echo "✅ Aplicación creada en: $APP_DIR"
  echo "   (No se pudo mover a /Applications; arrástrala a la carpeta"
  echo "    Aplicaciones con el Finder para instalarla.)"
fi
echo ""
echo "La primera vez que la abras, si macOS muestra un aviso:"
echo "  clic derecho sobre Roomba.app > Abrir > Abrir"
