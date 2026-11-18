#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LABEL="com.homellobu.roomba"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/.roomba_app"
UID_NUM="$(id -u)"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "No existe el entorno virtual en $VENV_DIR"
  echo "Créalo primero:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -e ."
  exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null \
    || launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Servicio eliminado. La app de escritorio (Roomba.app) sigue igual."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>             <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$PROJECT_DIR/scripts/roomba_web_launcher.py</string>
        <string>--headless</string>
    </array>
    <key>RunAtLoad</key>         <true/>
    <key>KeepAlive</key>         <true/>
    <key>WorkingDirectory</key>  <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>   <string>$LOG_DIR/service.log</string>
    <key>StandardErrorPath</key> <string>$LOG_DIR/service.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null \
  || launchctl unload "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>/dev/null \
  || launchctl load "$PLIST"

echo ""
echo "Servicio instalado y arrancado."
echo "  Estado:  launchctl list | grep roomba"
echo "  Log:     ~/.roomba_app/service.log"
echo "  Parar:   bash scripts/install_service.sh --uninstall"
echo ""
echo "Arranca solo cuando enciendas el Mac (con tu sesión iniciada)"
echo "y se reinicia solo si se cae. El iPad usa la URL que apareció"
echo "siguiendo la misma wifi (la dirección está en ~/.roomba_app/service.log)."
