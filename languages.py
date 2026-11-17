"""Language list for the settings window, and saving the chosen languages."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from engines import CONFIG_PATH, base_language, deepl_target_code

# Snapshot of DeepL's target languages (GET /v2/languages?type=target), used when
# there is no DeepL key or no connection. "code=Name" entries separated by "|".
_FALLBACK = (
    "af=Afrikaans|an=Aragonese|ar=Arabic|as=Assamese|ay=Aymara|az=Azerbaijani|ba=Bashkir|be=Belarusian|bg=Bulgarian|bn=Bengali|br=Breton|bs=Bosnian|ca=Catalan|cs=Czech|cy=Welsh|da=Danish|de=German|de-ch=German"
    " (Swiss)|de-de=German|el=Greek|en-gb=English (British)|en-us=English "
    "(American)|eo=Esperanto|es=Spanish|es-419=Spanish (Latin "
    "American)|es-es=Spanish|et=Estonian|eu=Basque|fa=Persian|fi=Finnish|fr=French|fr-ca=French"
    " "
    "(Canadian)|fr-fr=French|ga=Irish|gl=Galician|gn=Guarani|gu=Gujarati|ha=Hausa|he=Hebrew|hi=Hindi|hr=Croatian|ht=Haitian"
    " "
    "Creole|hu=Hungarian|hy=Armenian|id=Indonesian|ig=Igbo|is=Icelandic|it=Italian|ja=Japanese|jv=Javanese|ka=Georgian|kk=Kazakh|ko=Korean|ky=Kyrgyz|la=Latin|lb=Luxembourgish|ln=Lingala|lt=Lithuanian|lv=Latvian|mg=Malagasy|mi=Maori|mk=Macedonian|ml=Malayalam|mn=Mongolian|mr=Marathi|ms=Malay|mt=Maltese|my=Burmese|nb=Norwegian"
    " "
    "(bokmål)|ne=Nepali|nl=Dutch|oc=Occitan|om=Oromo|pa=Punjabi|pl=Polish|ps=Pashto|pt-br=Portuguese"
    " (Brazilian)|pt-pt=Portuguese "
    "(European)|qu=Quechua|ro=Romanian|ru=Russian|sa=Sanskrit|sk=Slovak|sl=Slovenian|sq=Albanian|sr=Serbian|st=Sesotho|su=Sundanese|sv=Swedish|sw=Swahili|ta=Tamil|te=Telugu|tg=Tajik|th=Thai|tk=Turkmen|tl=Tagalog|tn=Tswana|tr=Turkish|ts=Tsonga|tt=Tatar|uk=Ukrainian|ur=Urdu|uz=Uzbek|vi=Vietnamese|wo=Wolof|xh=Xhosa|yi=Yiddish|zh=Chinese"
    " (simplified)|zh-hans=Chinese (simplified)|zh-hant=Chinese "
    "(traditional)|zu=Zulu"
)
FALLBACK_LANGUAGES = [tuple(item.split("=", 1)) for item in _FALLBACK.split("|")]


def normalize_code(code: str) -> str:
    """Config code -> the code used in the list: "en" -> "en-us", "TR" -> "tr"."""
    return deepl_target_code(code).lower()


def dedupe(langs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """One entry per display name (keep the shortest code), sorted by name."""
    best: dict[str, str] = {}
    for code, name in langs:
        if name not in best or len(code) < len(best[name]):
            best[name] = code
    return sorted(((code, name) for name, code in best.items()), key=lambda item: item[1])


def fetch_languages(config: dict, timeout: float = 3.0) -> list[tuple[str, str]]:
    """DeepL's current target languages if a key is set, else the built-in snapshot."""
    key = config.get("deepl_key") or ""
    if key:
        host = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
        request = urllib.request.Request(f"{host}/v2/languages?type=target",
                                         headers={"Authorization": f"DeepL-Auth-Key {key}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                live = json.loads(resp.read().decode("utf-8"))
            return dedupe([(item["language"].lower(), item["name"]) for item in live])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # offline or unexpected answer: use the snapshot
    return dedupe(FALLBACK_LANGUAGES)


def save_languages(mine: str, second: str, path: Path = CONFIG_PATH) -> None:
    """Write my_language / second_language, keeping every other setting (and the key)."""
    if base_language(mine) == base_language(second):
        raise ValueError("My language and second language must be different.")
    path = Path(path)
    try:
        config = json.loads(path.read_text())
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError):
        config = {}
    config["my_language"] = mine
    config["second_language"] = second
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written config
