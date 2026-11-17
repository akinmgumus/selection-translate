"""Translation engines (Google free endpoint, DeepL API) and two-language auto-direction."""
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import requests

CONFIG_PATH = Path.home() / ".config" / "selection-translate" / "config.json"
DEFAULT_CONFIG = {
    "engine": "google",
    "deepl_key": "",
    "ignore_apps": ["firefox"],
    "my_language": "tr",      # everything is translated into this language...
    "second_language": "en",  # ...unless it already is in it; then into this one
}

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"
# DeepL needs a regional variant for some target languages.
DEEPL_DEFAULT_VARIANTS = {"en": "EN-US", "pt": "PT-BR"}


class TranslateError(Exception):
    """Any failure to get a translation (network, HTTP status, bad response)."""


@dataclass
class Translation:
    text: str    # the translated text
    source: str  # detected source language, e.g. "en"
    target: str  # language translated into, e.g. "tr"


def base_language(code: str) -> str:
    """"EN-US" -> "en", "de" -> "de": the language without its region."""
    return code.split("-")[0].lower()


def deepl_target_code(lang: str) -> str:
    """User code -> DeepL target_lang: "en" -> "EN-US", "en-gb" -> "EN-GB", "da" -> "DA"."""
    if "-" in lang:
        return lang.upper()
    return DEEPL_DEFAULT_VARIANTS.get(lang.lower(), lang.upper())


def google_translate(text: str, target: str, timeout: float = 8.0) -> tuple[str, str]:
    # urllib, not requests: Google answers this endpoint with HTTP 429 to
    # `requests` (urllib3's TLS setup) but serves Python's standard urllib fine.
    params = {"client": "gtx", "sl": "auto", "tl": base_language(target), "dt": "t", "q": text}
    url = GOOGLE_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise TranslateError(f"Google returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:  # offline, DNS failure, timeout
        raise TranslateError("No connection to Google Translate") from exc
    try:
        data = json.loads(body)
        # data[0] = [[translated_chunk, original_chunk, ...], ...], data[2] = detected language
        translated = "".join(chunk[0] for chunk in data[0] if chunk and chunk[0])
        detected = base_language(str(data[2]))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise TranslateError("Unexpected response from Google") from exc
    return translated, detected


def deepl_translate(text: str, target: str, key: str, timeout: float = 8.0) -> tuple[str, str]:
    url = DEEPL_FREE_URL if key.endswith(":fx") else DEEPL_PRO_URL
    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    data = {"text": text, "target_lang": deepl_target_code(target)}
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise TranslateError(f"Network error: {exc.__class__.__name__}") from exc
    if resp.status_code != 200:
        raise TranslateError(f"DeepL returned HTTP {resp.status_code}")
    try:
        item = resp.json()["translations"][0]
        return item["text"], base_language(item["detected_source_language"])
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise TranslateError("Unexpected response from DeepL") from exc


def translate_auto(text: str, config: dict) -> Translation:
    """Translate into my_language; if the text already is my_language, into second_language."""
    mine = config.get("my_language") or DEFAULT_CONFIG["my_language"]
    second = config.get("second_language") or DEFAULT_CONFIG["second_language"]
    if config.get("engine") == "deepl" and config.get("deepl_key"):
        engine = lambda t, tgt: deepl_translate(t, tgt, config["deepl_key"])
    else:
        engine = google_translate
    translated, source = engine(text, mine)
    if source == base_language(mine):
        translated, _ = engine(text, second)
        return Translation(translated, source, second.lower())
    return Translation(translated, source, mine.lower())


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy: callers may edit lists
    try:
        loaded = json.loads(Path(path).read_text())
        if isinstance(loaded, dict):
            config.update(loaded)
    except (OSError, ValueError):
        pass
    return config
