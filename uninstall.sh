#!/usr/bin/env bash
# Remove Selection Translate's autostart entry, launchers and shortcuts.
# Your config (~/.config/selection-translate/) is kept; delete it yourself if wanted.
set -euo pipefail

pkill -f selection_translate.py || true
rm -f "$HOME/.config/autostart/selection-translate.desktop" \
      "$HOME/.local/share/applications/selection-translate-on.desktop" \
      "$HOME/.local/share/applications/selection-translate-off.desktop"

if command -v gsettings >/dev/null; then
  python3 - <<'EOF'
import ast, subprocess

KEY = "org.gnome.settings-daemon.plugins.media-keys"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def gs(*args):
    return subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True).stdout.strip()

raw = gs("get", KEY, "custom-keybindings")
paths = ast.literal_eval(raw[3:].strip() if raw.startswith("@as") else raw)
ours = [f"{BASE}selection-translate-{s}/" for s in ("on", "off")]
for path in ours:
    for key in ("name", "command", "binding"):
        gs("reset", f"{KEY}.custom-keybinding:{path}", key)
gs("set", KEY, "custom-keybindings", str([p for p in paths if p not in ours]))
EOF
fi
echo "Selection Translate removed."
