import json
import urllib.error
import urllib.parse

import pytest
import requests

import engines
from engines import TranslateError, google_translate, load_config, translate_auto


class FakeResponse:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _google_reply(params):
    """Pretend Google: detects Turkish if the text has 'Merhaba'."""
    q, tl = params["q"], params["tl"]
    if "Merhaba" in q:
        detected = "tr"
        out = "Hello" if tl == "en" else q
        return FakeResponse(payload=[[[out, q]], None, detected])
    if q == "Hello world":
        return FakeResponse(payload=[[["Merhaba ", "Hello "], ["dünya", "world"]], None, "en"])
    return FakeResponse(payload=[[["Merhaba", q]], None, "en"])


class FakeUrlopenResponse:
    def __init__(self, fake):
        self._fake = fake
        self.status = fake.status_code

    def read(self):
        return self._fake.text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _params_of(request):
    url = request.full_url if hasattr(request, "full_url") else request
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}


@pytest.fixture
def fake_get(monkeypatch):
    calls = []

    def urlopen(request, timeout=None):
        params = _params_of(request)
        calls.append(params)
        return FakeUrlopenResponse(_google_reply(params))

    monkeypatch.setattr(engines.urllib.request, "urlopen", urlopen)
    return calls


@pytest.fixture
def fake_get_500(monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.HTTPError("u", 500, "err", {}, None)

    monkeypatch.setattr(engines.urllib.request, "urlopen", urlopen)


@pytest.fixture
def fake_get_conn_error(monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(engines.urllib.request, "urlopen", urlopen)


@pytest.fixture
def fake_get_timeout(monkeypatch):
    def urlopen(request, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(engines.urllib.request, "urlopen", urlopen)


@pytest.fixture
def fake_get_garbage(monkeypatch):
    monkeypatch.setattr(engines.urllib.request, "urlopen",
                        lambda request, timeout=None: FakeUrlopenResponse(FakeResponse(payload={"weird": 1})))


@pytest.fixture
def fake_post(monkeypatch):
    seen = {}

    def post(url, data=None, headers=None, timeout=None, **kw):
        seen.update(url=url, data=data, headers=headers)
        return FakeResponse(payload={"translations": [{"text": "Merhaba", "detected_source_language": "EN"}]})

    monkeypatch.setattr(engines.requests, "post", post)
    return seen


def test_google_joins_chunks_and_detects(fake_get):
    assert google_translate("Hello world", "tr") == ("Merhaba dünya", "en")


def test_auto_english_goes_to_turkish(fake_get):
    t = translate_auto("Hello", {"engine": "google"})
    assert (t.source, t.target) == ("en", "tr")
    assert len(fake_get) == 1


def test_auto_turkish_goes_to_english(fake_get):
    t = translate_auto("Merhaba", {"engine": "google"})
    assert (t.source, t.target, t.text) == ("tr", "en", "Hello")
    assert [c["tl"] for c in fake_get] == ["tr", "en"]


def test_http_error_raises(fake_get_500):
    with pytest.raises(TranslateError):
        google_translate("x", "tr")


def test_network_down_raises(fake_get_conn_error):
    with pytest.raises(TranslateError):
        google_translate("x", "tr")


def test_timeout_raises(fake_get_timeout):
    with pytest.raises(TranslateError):
        google_translate("x", "tr")


def test_malformed_json_raises(fake_get_garbage):
    with pytest.raises(TranslateError):
        google_translate("x", "tr")


def test_deepl_used_when_configured(fake_post):
    t = translate_auto("Hello", {"engine": "deepl", "deepl_key": "k:fx"})
    assert (t.text, t.source, t.target) == ("Merhaba", "en", "tr")
    assert fake_post["url"].startswith("https://api-free.deepl.com/")
    assert fake_post["headers"]["Authorization"] == "DeepL-Auth-Key k:fx"


def test_load_config_defaults_when_missing(tmp_path):
    assert load_config(tmp_path / "nope.json") == {"engine": "google", "deepl_key": "",
                                                   "ignore_apps": ["firefox"]}


def test_load_config_keeps_default_ignore_list_when_not_set(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"engine": "deepl", "deepl_key": "k:fx"}')
    assert load_config(f)["ignore_apps"] == ["firefox"]
