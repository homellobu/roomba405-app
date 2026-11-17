#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LAUNCHER="$PROJECT_DIR/scripts/roomba_gui_launcher.py"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "No existe el entorno virtual en $VENV_DIR"
  echo "Créalo primero:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -e ."
  exit 1
fi

APP_DIR="$PROJECT_DIR/Roomba.app"
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
    <key>CFBundlePackageType</key>    <string>APPL</string>
    <key>LSMinimumSystemVersion</key> <string>11.0</string>
    <key>NSHighResolutionCapable</key> <true/>
</dict>
</plist>
PLIST

cat > "$APP_DIR/Contents/MacOS/Roomba" <<LAUNCHER
#!/bin/bash
exec "$VENV_DIR/bin/python" "$LAUNCHER"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/Roomba"

echo ""
echo "✅ Aplicación creada en: $APP_DIR"
echo ""
echo "Para instalarla en Aplicaciones:"
echo "  mv '$APP_DIR' /Applications/"
echo ""
echo "La primera vez que la abras, si macOS muestra un aviso:"
echo "  clic derecho sobre Roomba.app > Abrir > Abrir"
