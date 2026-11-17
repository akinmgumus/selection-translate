# Selection Translate

Select text with the mouse anywhere on your Linux desktop — a PDF in Evince,
a terminal, an editor — and a small popup shows its translation right under
the selection. Built for reading English technical papers in Turkish — and
usable with [any language DeepL supports](#use-it-with-your-language).

- Text in **any language → your language**, and your language → a second
  language (default: everything → Turkish, Turkish → English); 100+ languages
- Pick the languages in a small window: **Ctrl+Super+→**
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

This adds an autostart entry (it starts at login), "Selection Translate" On/Off
and Languages launchers in the Activities search, and the keyboard shortcuts,
then starts it.

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

## Use it with your language

It works with **every language DeepL supports** (100+); Turkish is only the
default. Two settings decide the direction:

- **My language** — every selection, in any language, is translated into it
- **Second language** — used when the selected text already *is* in My language

Press **Ctrl+Super+→** (or open **"Selection Translate: Languages"** from the
Activities search), pick both languages, and **Save**. No restart needed.

```
┌ Selection Translate — Languages ─────────┐
│ My language:       [ Turkish          ▾ ] │
│ Second language:   [ English (American)▾ ] │
│                         [Cancel] [Save]   │
└───────────────────────────────────────────┘
```

Examples (the window lists every available language — these are only examples):

| You are… | My language | Second language | Result |
|---|---|---|---|
| Turkish (default) | Turkish | English | anything → TR, TR → EN |
| German | German | English | anything → DE, DE → EN |
| Japanese | Japanese | English (British) | anything → JA, JA → EN-GB |

The list comes live from DeepL when a key is set, otherwise from a built-in
copy. You can also set `my_language` / `second_language` in `config.json` with
codes from DeepL's
[supported languages list](https://developers.deepl.com/docs/getting-started/supported-languages)
(`de`, `ja`, `en-gb`, `pt-pt`, …). If DeepL does not support your language, set
`"engine": "google"`.

## Usage

- Select a word, sentence or paragraph **with the mouse** and release.
- Close the popup: **Esc**, click anywhere else, click **×**, or select something new.
- **Copy** copies the translation; you can also select text inside the popup.
- On / off: **Ctrl+Super+↑ / ↓**, the Activities launchers, or
  `python3 selection_translate.py --on | --off`. A notification confirms.
- Languages: **Ctrl+Super+→** or `python3 selection_translate.py --settings`.

## Configuration

`~/.config/selection-translate/config.json`:

| Key | Meaning | Default |
|---|---|---|
| `engine` | `"deepl"` or `"google"` | `"google"` |
| `deepl_key` | your DeepL API key | — |
| `ignore_apps` | apps where selections are ignored (matched against the window's class name, e.g. `firefox`, `code`) | `["firefox"]` |
| `my_language` | language every selection is translated into | `"tr"` |
| `second_language` | target when the text is already in `my_language` | `"en"` |

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
| `engines.py` | DeepL / Google calls and the two-language direction |
| `textclean.py` | PDF text clean-up and "worth translating?" filter |
| `placement.py` | popup size and position |
| `input_rules.py` | mouse-vs-keyboard, selection bounds, ignored apps |
| `languages.py` | language list (live from DeepL or built-in) and saving the choice |
| `settings_window.py` | the Languages window (Ctrl+Super+→) |

## License

MIT
