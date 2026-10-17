"""Golden outputs + invariants for every shipped language."""
import json
import os
import random

import pytest

from engine.transliterate import (
    create_engine, get_languages_dir, list_available_languages, resolve_language,
)

ALL = [l["file"] for l in list_available_languages()]


def T(lang, text, **kw):
    return create_engine(lang).transliterate(text, **kw)


# ---------------- invariants over every language ---------------- #

@pytest.mark.parametrize("lang", ALL)
def test_language_loads_and_is_well_formed(lang):
    e = create_engine(lang)
    assert e.name and e.code and e.script_type
    assert resolve_language(e.code) == lang
    assert e.data.get("symbol")


@pytest.mark.parametrize("lang", ALL)
def test_empty_and_whitespace(lang):
    e = create_engine(lang)
    assert e.transliterate("") == ""
    assert e.transliterate("   ") == "   "
    assert e.candidates("") == []


@pytest.mark.parametrize("lang", ALL)
def test_fuzz_never_crashes(lang):
    e = create_engine(lang)
    rnd = random.Random(1234)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?'^_~-()[]"
    for _ in range(300):
        s = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 14)))
        out = e.transliterate(s)
        assert isinstance(out, str)
        assert e.get_preedit(s) is not None
        assert e.candidates(s.split()[0] if s.split() else s, limit=5) is not None


@pytest.mark.parametrize("lang", ALL)
def test_preedit_is_prefix_stable(lang):
    """Typing more never makes the live preview raise or go empty."""
    e = create_engine(lang)
    for w in ("namaste", "konnichiwa", "annyeong", "privet"):
        for i in range(1, len(w) + 1):
            assert e.get_preedit(w[:i]) != ""


@pytest.mark.parametrize("lang", ALL)
def test_lexicon_entries_are_strings(lang):
    e = create_engine(lang)
    for k, vals in e.lexicon.items():
        assert k == k.lower() and " " not in k
        assert vals and all(isinstance(v, str) and v for v in vals)


# ---------------- Hindi regressions (bugs found in v1) ---------------- #

class TestHindi:
    @pytest.mark.parametrize("src,out", [
        ("namaste", "नमस्ते"), ("dhanyavaad", "धन्यवाद"), ("priya", "प्रिय"), ("hari", "हरि"),
        ("somvar", "सोम्वर"), ("Namaste", "नमस्ते"), ("kaise ho", "कैसे हो"),
        ("k_h", "कह"), ("a_i", "अइ"), ("k^", "क्"), ("3.14", "३.१४"),
        ("pat.", "पत।"), ("ram", "राम"), ("OM", "ॐ"), ("om", "ॐ"),
    ])
    def test_golden(self, src, out):
        assert T("hindi.json", src) == out

    def test_smart_capitalize_respects_deliberate_caps(self):
        e = create_engine("hindi.json")
        # only the first letter capital -> treated as sentence-start capital (ta -> त)
        assert e.transliterate("Ta", use_lexicon=False) == "त"
        # deliberate capitals are kept (retroflex ट)
        assert e.transliterate("TaTa", use_lexicon=False) == "टट"
        e.smart_capitalize = False
        assert e.transliterate("Ta", use_lexicon=False) == "ट"

    def test_numbers_toggle(self):
        e = create_engine("hindi.json")
        e.convert_numbers = False
        assert e.transliterate("12") == "12"

    def test_candidates_include_lexicon_and_variants(self):
        c = create_engine("hindi.json").candidates("hindi")
        assert c[0] == "हिन्दी" and "हिंदी" in c and "हिन्दि" in c
        assert "संगीत" in create_engine("hindi.json").candidates("sangeet")
        assert "हैं" in create_engine("hindi.json").candidates("hain")

    def test_completions(self):
        comps = create_engine("hindi.json").completions("dhany")
        assert ("dhanyavaad", "धन्यवाद") in comps

    def test_trailing_punct_and_lead_punct(self):
        assert T("hindi.json", "(namaste)") == "(नमस्ते)"
        assert T("hindi.json", "namaste!") == "नमस्ते!"


# ---------------- Japanese ---------------- #

class TestJapanese:
    @pytest.mark.parametrize("src,out", [
        ("konnichiwa", "こんにちは"), ("sennsei", "せんせい"), ("matcha", "まっちゃ"),
        ("shinbun", "しんぶん"), ("kon'nichiwa", "こんにちわ"), ("onna", "おんな"),
        ("kanpai", "かんぱい"), ("n", "ん"), ("nn", "ん"), ("wi", "うぃ"),
        ("ohayou gozaimasu.", "おはよう ございます。"),
    ])
    def test_hiragana(self, src, out):
        assert T("japanese_hiragana.json", src) == out

    @pytest.mark.parametrize("src,out", [
        ("raamen", "ラーメン"), ("koohii", "コーヒー"), ("paatii", "パーティー"),
        ("konpyuutaa", "コンピューター"), ("ra-men", "ラーメン"), ("aisu", "アイス"),
        ("kitte", "キッテ"),
    ])
    def test_katakana(self, src, out):
        assert T("japanese_katakana.json", src) == out

    def test_live_preview_keeps_trailing_n_literal(self):
        e = create_engine("japanese_hiragana.json")
        assert e.get_preedit("kon") == "こn"
        assert e.transliterate("kon") == "こん"

    def test_kanji_and_katakana_candidates(self):
        c = create_engine("japanese_hiragana.json").candidates("sakura")
        assert c[:3] == ["さくら", "桜", "サクラ"]


# ---------------- Korean ---------------- #

@pytest.mark.parametrize("src,out", [
    ("annyeonghaseyo", "안녕하세요"), ("saranghae", "사랑해"), ("hangeul", "한글"),
    ("bibimbap", "비빔밥"), ("dalg", "닭"), ("seoul", "서울"), ("gangnam", "강남"),
    ("kimchi", "김치"), ("gamsahamnida", "감사합니다"),
])
def test_korean(src, out):
    assert T("korean.json", src) == out


# ---------------- other scripts ---------------- #

@pytest.mark.parametrize("lang,src,out", [
    ("tamil.json", "thamizh", "தமிழ்"), ("tamil.json", "vanakkam", "வணக்கம்"),
    ("telugu.json", "telugu", "తెలుగు"), ("arabic.json", "salaam", "سلام"),
    ("arabic.json", "mar7aba", "مرحبا"), ("arabic.json", "123", "١٢٣"),
    ("arabic.json", "3arabi", "عربي"), ("urdu.json", "urdu", "اردو"),
    ("russian.json", "privet", "привет"), ("russian.json", "moy", "мой"),
    ("russian.json", "Moskva", "Москва"), ("russian.json", "shchuka", "щука"),
    ("greek.json", "sas", "σας"), ("greek.json", "Athina", "Αθήνα"),
    ("bengali.json", "namaskar", "নমস্কর"), ("malayalam.json", "vazhi", "വഴി"),
    ("gujarati.json", "kem cho", "કેમ ચો"), ("marathi.json", "majha", "मझ"),
])
def test_other_scripts(lang, src, out):
    assert T(lang, src) == out


def test_arabic_diacritics_toggle():
    e = create_engine("arabic.json")
    plain = e.transliterate("kitab")
    e.show_diacritics = True
    assert e.transliterate("kitab") != plain


def test_derived_indic_scripts_use_their_own_unicode_block():
    ranges = {"bengali": (0x0980, 0x09FF), "gujarati": (0x0A80, 0x0AFF), "telugu": (0x0C00, 0x0C7F),
              "kannada": (0x0C80, 0x0CFF), "malayalam": (0x0D00, 0x0D7F), "odia": (0x0B00, 0x0B7F),
              "punjabi": (0x0A00, 0x0A7F), "tamil": (0x0B80, 0x0BFF)}
    for name, (lo, hi) in ranges.items():
        out = T(f"{name}.json", "namaste")
        assert all(lo <= ord(ch) <= hi for ch in out), (name, out)


# ---------------- resolver ---------------- #

def test_resolve_language_aliases():
    assert resolve_language("hindi") == "hindi.json"
    assert resolve_language("HI") == "hindi.json"
    assert resolve_language("japanese") == "japanese_hiragana.json"
    assert resolve_language("katakana") == "japanese_katakana.json"
    assert resolve_language("ja-kata") == "japanese_katakana.json"
    assert resolve_language("hangul") == "korean.json"
    assert resolve_language("nonsense-xyz") is None


def test_every_json_in_languages_dir_is_valid():
    d = get_languages_dir()
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".json"):
                json.load(open(os.path.join(root, f), encoding="utf-8"))
