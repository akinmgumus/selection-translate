import json
import os
import stat

import pytest

import languages
from languages import dedupe, fetch_languages, normalize_code, save_languages


def test_normalize_code_matches_deepl_targets():
    assert normalize_code("en") == "en-us"
    assert normalize_code("TR") == "tr"
    assert normalize_code("pt") == "pt-br"
    assert normalize_code("zh-hans") == "zh-hans"


def test_dedupe_keeps_shortest_code_per_name_and_sorts_by_name():
    langs = [("en-gb", "English (British)"), ("de-de", "German"), ("de", "German")]
    assert dedupe(langs) == [("en-gb", "English (British)"), ("de", "German")]


def test_fallback_list_has_many_languages_including_turkish_and_english():
    langs = fetch_languages({"engine": "google", "deepl_key": ""})
    codes = dict(langs)
    assert codes["tr"] == "Turkish"
    assert codes["en-us"] == "English (American)"
    assert len(langs) > 100


class FakeHTTP:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_live_list_from_deepl_when_key_present(monkeypatch):
    seen = {}

    def urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        return FakeHTTP([{"language": "TR", "name": "Turkish"}, {"language": "EN-US", "name": "English (American)"}])

    monkeypatch.setattr(languages.urllib.request, "urlopen", urlopen)
    langs = fetch_languages({"engine": "deepl", "deepl_key": "k:fx"})
    assert langs == [("en-us", "English (American)"), ("tr", "Turkish")]
    assert seen["url"].startswith("https://api-free.deepl.com/v2/languages")
    assert seen["auth"] == "DeepL-Auth-Key k:fx"


def test_live_list_failure_falls_back(monkeypatch):
    def urlopen(request, timeout=None):
        raise OSError("offline")

    monkeypatch.setattr(languages.urllib.request, "urlopen", urlopen)
    langs = fetch_languages({"engine": "deepl", "deepl_key": "k:fx"})
    assert dict(langs)["tr"] == "Turkish"


def test_save_keeps_other_settings_and_stays_private(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"engine": "deepl", "deepl_key": "secret:fx", "ignore_apps": ["firefox"]}))
    save_languages("de", "en-us", cfg)
    data = json.loads(cfg.read_text())
    assert data == {"engine": "deepl", "deepl_key": "secret:fx", "ignore_apps": ["firefox"],
                    "my_language": "de", "second_language": "en-us"}
    assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600


def test_save_creates_missing_config(tmp_path):
    cfg = tmp_path / "sub" / "config.json"
    save_languages("tr", "en-us", cfg)
    assert json.loads(cfg.read_text()) == {"my_language": "tr", "second_language": "en-us"}


def test_same_language_twice_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_languages("en-us", "en-gb", tmp_path / "config.json")
