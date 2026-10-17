"""Translation engine, config, CLI."""
import io
import json
import time
import urllib.error

import pytest

from engine import translate as tmod
from engine.cli import main as cli_main
from engine.config import DEFAULT_CONFIG, Config, config_file
from engine.translate import TranslationEngine


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def fake_urlopen_factory(calls, payload=None, fail=False):
    def fake(req, timeout=None):
        calls.append(req.full_url)
        if fail:
            raise urllib.error.URLError("down")
        return FakeResp(json.dumps(payload or [[["नमस्ते", "hello", None]]]).encode())
    return fake


def test_online_translate_parses_and_caches(monkeypatch):
    calls = []
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen_factory(calls))
    t = TranslationEngine("hi")
    assert t.translate("hello") == "नमस्ते"
    assert t.translate("hello") == "नमस्ते"
    assert len(calls) == 1 and "tl=hi" in calls[0]          # second call served from cache


def test_failure_backs_off_instead_of_hammering(monkeypatch):
    calls = []
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen_factory(calls, fail=True))
    t = TranslationEngine("hi", backend="online")
    assert t.translate("a") is None and t.translate("b") is None and t.translate("c") is None
    assert len(calls) == 1                                    # backed off after the first failure


def test_offline_backend_unavailable_returns_none():
    assert TranslationEngine("hi", backend="offline").translate("hello") is None


def test_target_language_mapping():
    t = TranslationEngine("ja-kata")
    assert t.target_lang == "ja"
    t.set_target_language("ko"); assert t.target_lang == "ko"
    assert t.supports("ta") and not t.supports("xx")


def test_async_callback(monkeypatch):
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen_factory([]))
    got = []
    TranslationEngine("hi").translate_async("hello", got.append).join(2)
    assert got == ["नमस्ते"]


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen_factory([]))
    t = TranslationEngine("hi", cache_size=3)
    for i in range(10):
        t.translate(f"w{i}")
    assert len(t._cache) == 3


# ---------------- config ---------------- #

def test_config_defaults_created_and_persist(isolated_config):
    c = Config()
    assert c.toggle_key == "F12" and c.get("learn") is True
    c.set("toggle_key", "F9")
    assert Config().toggle_key == "F9"


def test_config_rejects_bad_types_and_recovers_from_corruption(isolated_config):
    with open(config_file(), "w") as f:
        json.dump({"candidate_page_size": "lots", "toggle_key": "F8", "mystery": 1}, f)
    c = Config()
    assert c.get("candidate_page_size") == DEFAULT_CONFIG["candidate_page_size"]
    assert c.toggle_key == "F8" and c.get("mystery") == 1
    with open(config_file(), "w") as f:
        f.write("{not json")
    assert Config().toggle_key == "F12"                      # reset, and kept a .broken copy
    import os
    assert os.path.exists(config_file() + ".broken")


# ---------------- CLI ---------------- #

def test_cli_text(capsys):
    assert cli_main(["-l", "hindi", "-t", "namaste"]) == 0
    assert capsys.readouterr().out.strip() == "नमस्ते"


def test_cli_candidates_and_json(capsys):
    cli_main(["-l", "ja", "-t", "sakura", "-c", "--json"])
    row = json.loads(capsys.readouterr().out)
    assert row["output"] == "さくら" and "桜" in row["candidates"]["sakura"]


def test_cli_list_and_unknown(capsys):
    assert cli_main(["--list"]) == 0 and "Korean" in capsys.readouterr().out
    assert cli_main(["-l", "klingon", "-t", "x"]) == 2


def test_cli_translate_falls_back_when_offline(monkeypatch, capsys):
    monkeypatch.setattr(tmod.urllib.request, "urlopen", fake_urlopen_factory([], fail=True))
    cli_main(["-l", "hi", "-t", "namaste", "--translate", "--backend", "online"])
    assert capsys.readouterr().out.strip() == "नमस्ते"      # phonetic fallback, not a crash
