# Selection Translate

Select text with the mouse anywhere on your Linux desktop — a PDF in Evince,
a terminal, an editor — and a small popup shows its translation right under
the selection. Built for reading English technical papers in Turkish.

- **English → Turkish**, and **Turkish → English**, detected automatically
- Popup sized to the text: small for a word, larger for a paragraph; never
  covers the text you selected
- Fixes PDF copy artefacts before translating (broken lines, `optimi-⏎zation`)
- Mouse selections only — keyboard selections (Shift+arrows, Ctrl+A) are ignored
- Skips Firefox by default (use a browser extension there); configurable
- On/off with **Ctrl+Super+↑ / Ctrl+Super+↓** (Super = Windows key)

Translations come from the **DeepL API** (bring your own free key). Without a
key it falls back to Google Translate's free web endpoint, which is noticeably
less fluent.

## Requirements

- Linux with an **X11** session (Ubuntu GNOME on Xorg; Wayland is not supported)
- Python 3.10+, GTK 3 bindings, `requests`, `notify-send`

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-requests libnotify-bin
```

## Install

```bash
git clone https://github.com/akinmgumus/selection-translate.git
cd selection-translate
./install.sh
```

This adds an autostart entry (it starts at login), "Selection Translate: On/Off"
launchers in the Activities search, and the keyboard shortcuts, then starts it.

## DeepL API key (recommended)

1. Create a free account at <https://www.deepl.com/en/developers> and choose
   **DeepL API Free**.
2. Copy your key from **Account → API Keys**. Free keys end in `:fx`.
3. Put it in your config — it stays on your machine, outside this repository:

```bash
mkdir -p ~/.config/selection-translate
cp config.example.json ~/.config/selection-translate/config.json
chmod 600 ~/.config/selection-translate/config.json
nano ~/.config/selection-translate/config.json   # paste your key
```

The config is re-read on every translation; no restart needed.

**Limits:** DeepL API Free has a monthly character quota (advertised as
500,000 characters; your account page shows your exact limit). Every character
you send counts, including spaces. When the quota is used up DeepL stops
answering until the next month — nothing is charged.

## Usage

- Select a word, sentence or paragraph **with the mouse** and release.
- Close the popup: **Esc**, click anywhere else, click **×**, or select something new.
- **Copy** copies the translation; you can also select text inside the popup.
- On / off: **Ctrl+Super+↑ / ↓**, the Activities launchers, or
  `python3 selection_translate.py --on | --off`. A notification confirms.

## Configuration

`~/.config/selection-translate/config.json`:

| Key | Meaning | Default |
|---|---|---|
| `engine` | `"deepl"` or `"google"` | `"google"` |
| `deepl_key` | your DeepL API key | — |
| `ignore_apps` | apps where selections are ignored (matched against the window's class name, e.g. `firefox`, `code`) | `["firefox"]` |

## Troubleshooting

Run it in a terminal with a log:

```bash
pkill -f selection_translate.py; python3 selection_translate.py --debug
```

## Uninstall

```bash
./uninstall.sh
```

Your config in `~/.config/selection-translate/` is left in place.

## Development

```bash
python3 -m pytest -q
```

| File | Role |
|---|---|
| `selection_translate.py` | GTK app: watches the selection, mouse and Esc; shows the popup |
| `engines.py` | DeepL / Google calls and EN⇄TR direction |
| `textclean.py` | PDF text clean-up and "worth translating?" filter |
| `placement.py` | popup size and position |
| `input_rules.py` | mouse-vs-keyboard, selection bounds, ignored apps |

## License

MIT
