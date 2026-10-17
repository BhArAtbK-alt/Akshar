"""
Akshar — Tests for Transliteration Engine
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.transliterate import TransliterationEngine, create_engine, get_languages_dir


class TestHindiTransliteration:
    """Test Hindi (Devanagari) transliteration."""

    def setup_method(self):
        self.engine = create_engine("hindi.json")

    def test_basic_vowels(self):
        assert self.engine.transliterate("a") == "अ"
        assert self.engine.transliterate("aa") == "आ"
        assert self.engine.transliterate("i") == "इ"
        assert self.engine.transliterate("ee") == "ई"
        assert self.engine.transliterate("u") == "उ"
        assert self.engine.transliterate("oo") == "ऊ"
        assert self.engine.transliterate("e") == "ए"
        assert self.engine.transliterate("o") == "ओ"
        assert self.engine.transliterate("ai") == "ऐ"
        assert self.engine.transliterate("au") == "औ"

    def test_basic_consonants(self):
        # Consonants alone get inherent 'a' vowel
        assert self.engine.transliterate("k") == "क"
        assert self.engine.transliterate("kh") == "ख"
        assert self.engine.transliterate("g") == "ग"
        assert self.engine.transliterate("ch") == "च"
        assert self.engine.transliterate("t") == "त"
        assert self.engine.transliterate("p") == "प"
        assert self.engine.transliterate("m") == "म"

    def test_consonant_vowel_combinations(self):
        assert self.engine.transliterate("ka") == "क"    # 'a' matra is empty (inherent)
        assert self.engine.transliterate("ki") == "कि"
        assert self.engine.transliterate("ku") == "कु"
        assert self.engine.transliterate("ke") == "के"
        assert self.engine.transliterate("ko") == "को"
        assert self.engine.transliterate("kee") == "की"
        assert self.engine.transliterate("koo") == "कू"
        assert self.engine.transliterate("kai") == "कै"
        assert self.engine.transliterate("kau") == "कौ"

    def test_words(self):
        assert self.engine.transliterate("namaste") == "नमस्ते"
        assert self.engine.transliterate("bharat") == "भारत"          # lexicon spelling
        assert self.engine.transliterate("hindi") == "हिन्दी"          # lexicon spelling
        assert self.engine.transliterate("hindi", use_lexicon=False) == "हिन्दि"   # raw algorithm
        assert self.engine.transliterate("dhanyavaad") == "धन्यवाद"
        assert self.engine.transliterate("priya") == "प्रिय"
        assert self.engine.transliterate("somvar") == "सोम्वर"

    def test_conjuncts(self):
        assert self.engine.transliterate("ksh") == "क्ष"
        assert self.engine.transliterate("tr") == "त्र"
        assert self.engine.transliterate("gy") == "ज्ञ"

    def test_consonant_clusters(self):
        # Two consonants together should produce halant
        assert self.engine.transliterate("nk") == "न्क"
        assert self.engine.transliterate("st") == "स्त"

    def test_numbers(self):
        assert self.engine.transliterate("0") == "०"
        assert self.engine.transliterate("9") == "९"

    def test_specials(self):
        assert self.engine.transliterate("om") == "ॐ"

    def test_passthrough(self):
        # Non-recognized chars pass through
        assert self.engine.transliterate("@") == "@"
        assert self.engine.transliterate("#") == "#"

    def test_mixed(self):
        result = self.engine.transliterate("ram", use_lexicon=False)   # raw algorithm
        assert result == "रम"
        assert self.engine.transliterate("ram") == "राम"               # lexicon

    def test_preedit(self):
        preview = self.engine.get_preedit("nam")
        assert len(preview) > 0  # Should produce some Devanagari output

    def test_has_continuation(self):
        assert self.engine.has_possible_continuation("k") == True  # could be "kh", "ksh"
        assert self.engine.has_possible_continuation("s") == True  # could be "sh"
        assert self.engine.has_possible_continuation("zzz") == False


class TestJapaneseHiraganaTransliteration:
    """Test Japanese Hiragana transliteration."""

    def setup_method(self):
        self.engine = create_engine("japanese_hiragana.json")

    def test_basic_vowels(self):
        assert self.engine.transliterate("a") == "あ"
        assert self.engine.transliterate("i") == "い"
        assert self.engine.transliterate("u") == "う"
        assert self.engine.transliterate("e") == "え"
        assert self.engine.transliterate("o") == "お"

    def test_k_row(self):
        assert self.engine.transliterate("ka") == "か"
        assert self.engine.transliterate("ki") == "き"
        assert self.engine.transliterate("ku") == "く"
        assert self.engine.transliterate("ke") == "け"
        assert self.engine.transliterate("ko") == "こ"

    def test_s_row(self):
        assert self.engine.transliterate("sa") == "さ"
        assert self.engine.transliterate("shi") == "し"
        assert self.engine.transliterate("su") == "す"
        assert self.engine.transliterate("se") == "せ"
        assert self.engine.transliterate("so") == "そ"

    def test_n_row(self):
        assert self.engine.transliterate("na") == "な"
        assert self.engine.transliterate("ni") == "に"
        assert self.engine.transliterate("nu") == "ぬ"
        assert self.engine.transliterate("ne") == "ね"
        assert self.engine.transliterate("no") == "の"

    def test_standalone_n(self):
        # 'n' at end of string
        assert self.engine.transliterate("n") == "ん"
        # 'nn' should produce ん
        assert self.engine.transliterate("nn") == "ん"

    def test_n_before_consonant(self):
        # 'n' before a consonant (not vowel, not y) → ん + next syllable
        result = self.engine.transliterate("senpai")
        assert "ん" in result

    def test_double_consonant(self):
        # Double consonant → っ + syllable
        result = self.engine.transliterate("kitte")
        assert "っ" in result

    def test_combination_kana(self):
        assert self.engine.transliterate("kya") == "きゃ"
        assert self.engine.transliterate("sha") == "しゃ"
        assert self.engine.transliterate("cha") == "ちゃ"
        assert self.engine.transliterate("nya") == "にゃ"

    def test_dakuten(self):
        assert self.engine.transliterate("ga") == "が"
        assert self.engine.transliterate("za") == "ざ"
        assert self.engine.transliterate("da") == "だ"
        assert self.engine.transliterate("ba") == "ば"

    def test_handakuten(self):
        assert self.engine.transliterate("pa") == "ぱ"
        assert self.engine.transliterate("pi") == "ぴ"
        assert self.engine.transliterate("pu") == "ぷ"

    def test_words(self):
        result = self.engine.transliterate("sakura")
        assert result == "さくら"

        result = self.engine.transliterate("tokyo")
        assert result == "とうきょう"           # lexicon
        assert self.engine.transliterate("tokyo", use_lexicon=False) == "ときょ"

    def test_punctuation(self):
        assert self.engine.transliterate(".") == "。"
        assert self.engine.transliterate(",") == "、"


class TestJapaneseKatakanaTransliteration:
    """Test Japanese Katakana transliteration."""

    def setup_method(self):
        self.engine = create_engine("japanese_katakana.json")

    def test_basic_vowels(self):
        assert self.engine.transliterate("a") == "ア"
        assert self.engine.transliterate("i") == "イ"
        assert self.engine.transliterate("u") == "ウ"

    def test_k_row(self):
        assert self.engine.transliterate("ka") == "カ"
        assert self.engine.transliterate("ki") == "キ"
        assert self.engine.transliterate("ku") == "ク"

    def test_double_consonant(self):
        result = self.engine.transliterate("kitte")
        assert "ッ" in result


class TestEngineFactory:
    """Test engine creation and language listing."""

    def test_list_languages(self):
        from engine.transliterate import list_available_languages
        languages = list_available_languages()
        assert len(languages) >= 2  # At least Hindi and Japanese
        names = [l["name"] for l in languages]
        assert any("Hindi" in n for n in names)
        assert any("Japanese" in n for n in names)

    def test_create_by_filename(self):
        engine = create_engine("hindi.json")
        assert engine.name == "Hindi"
        assert engine.script_type == "abugida"

    def test_create_japanese(self):
        engine = create_engine("japanese_hiragana.json")
        assert engine.name == "Japanese (Hiragana)"
        assert engine.script_type == "syllabary"

    def test_invalid_file_raises(self):
        try:
            create_engine("nonexistent.json")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    # Simple test runner (no pytest dependency needed)
    import traceback

    test_classes = [
        TestHindiTransliteration,
        TestJapaneseHiraganaTransliteration,
        TestJapaneseKatakanaTransliteration,
        TestEngineFactory,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n{'='*60}")
        print(f"  {cls.__name__}")
        print(f"{'='*60}")
        instance = cls()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                total += 1
                try:
                    if hasattr(instance, "setup_method"):
                        instance.setup_method()
                    getattr(instance, method_name)()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {e}")
                    errors.append((cls.__name__, method_name, traceback.format_exc()))
                    failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    if errors:
        print("\nFailed tests:")
        for cls_name, method, tb in errors:
            print(f"\n--- {cls_name}.{method} ---")
            print(tb)

    sys.exit(0 if failed == 0 else 1)
