#!/usr/bin/env bash
# Install Selection Translate for the current user (Ubuntu / GNOME on X11).
# Creates: autostart entry, "On"/"Off" launchers, Ctrl+Super+Up/Down shortcuts.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$DIR/selection_translate.py"
PY="$(command -v python3)"
APPS="$HOME/.local/share/applications"
AUTOSTART="$HOME/.config/autostart"
mkdir -p "$APPS" "$AUTOSTART"

write_desktop() {  # <file> <name> <args> <extra lines>
  cat > "$1" <<EOF
[Desktop Entry]
Type=Application
Name=$2
Comment=Translate selected text (EN <-> TR) in a popup
Exec=$PY "$APP" $3
Icon=accessories-dictionary
Terminal=false
$4
EOF
}

write_desktop "$AUTOSTART/selection-translate.desktop" "Selection Translate" "" \
  $'NoDisplay=true\nX-GNOME-Autostart-enabled=true'
write_desktop "$APPS/selection-translate-on.desktop"  "Selection Translate: On"  "--on"  "Categories=Utility;"
write_desktop "$APPS/selection-translate-off.desktop" "Selection Translate: Off" "--off" "Categories=Utility;"
echo "Installed autostart entry and On/Off launchers."

if command -v gsettings >/dev/null; then
  "$PY" - "$PY" "$APP" <<'EOF'
import ast, subprocess, sys

py, app = sys.argv[1:3]
KEY = "org.gnome.settings-daemon.plugins.media-keys"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def gs(*args):
    return subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True).stdout.strip()

raw = gs("get", KEY, "custom-keybindings")
paths = ast.literal_eval(raw[3:].strip() if raw.startswith("@as") else raw)
for state, combo in (("on", "<Control><Super>Up"), ("off", "<Control><Super>Down")):
    path = f"{BASE}selection-translate-{state}/"
    if path not in paths:
        paths.append(path)  # keep the user's other custom shortcuts
    schema = f"{KEY}.custom-keybinding:{path}"
    gs("set", schema, "name", f"Selection Translate: {state.title()}")
    gs("set", schema, "command", f'{py} "{app}" --{state}')
    gs("set", schema, "binding", combo)
gs("set", KEY, "custom-keybindings", str(paths))
print("Shortcuts: Ctrl+Super+Up = on, Ctrl+Super+Down = off.")
EOF
fi

# Start it now (if it is already running this just switches it on).
setsid nohup "$PY" "$APP" --on >/dev/null 2>&1 < /dev/null &
echo "Selection Translate is running. Select text with the mouse to translate it."
