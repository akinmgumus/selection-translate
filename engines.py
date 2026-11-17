"""Translation engines (Google free endpoint, DeepL API) and EN<->TR auto-direction."""
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import requests

CONFIG_PATH = Path.home() / ".config" / "selection-translate" / "config.json"
DEFAULT_CONFIG = {"engine": "google", "deepl_key": "", "ignore_apps": ["firefox"]}

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"
DEEPL_TARGETS = {"tr": "TR", "en": "EN-US"}


class TranslateError(Exception):
    """Any failure to get a translation (network, HTTP status, bad response)."""


@dataclass
class Translation:
    text: str    # the translated text
    source: str  # detected source language, e.g. "en"
    target: str  # language translated into, "tr" or "en"


def google_translate(text: str, target: str, timeout: float = 8.0) -> tuple[str, str]:
    # urllib, not requests: Google answers this endpoint with HTTP 429 to
    # `requests` (urllib3's TLS setup) but serves Python's standard urllib fine.
    params = {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text}
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
        detected = str(data[2])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise TranslateError("Unexpected response from Google") from exc
    return translated, detected


def deepl_translate(text: str, target: str, key: str, timeout: float = 8.0) -> tuple[str, str]:
    url = DEEPL_FREE_URL if key.endswith(":fx") else DEEPL_PRO_URL
    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    data = {"text": text, "target_lang": DEEPL_TARGETS[target]}
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise TranslateError(f"Network error: {exc.__class__.__name__}") from exc
    if resp.status_code != 200:
        raise TranslateError(f"DeepL returned HTTP {resp.status_code}")
    try:
        item = resp.json()["translations"][0]
        return item["text"], item["detected_source_language"].lower()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise TranslateError("Unexpected response from DeepL") from exc


def translate_auto(text: str, config: dict) -> Translation:
    """Translate to Turkish; if the text turns out to be Turkish, translate to English instead."""
    if config.get("engine") == "deepl" and config.get("deepl_key"):
        engine = lambda t, tgt: deepl_translate(t, tgt, config["deepl_key"])
    else:
        engine = google_translate
    translated, source = engine(text, "tr")
    if source == "tr":
        translated, _ = engine(text, "en")
        return Translation(translated, "tr", "en")
    return Translation(translated, source, "tr")


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy: callers may edit lists
    try:
        loaded = json.loads(Path(path).read_text())
        if isinstance(loaded, dict):
            config.update(loaded)
    except (OSError, ValueError):
        pass
    return config
