"""Session state machine: buffering, candidates, hotkeys, learning, translation."""
import pytest

from engine.config import Config
from engine.session import Hotkey, Key, Session, MODE_TRANSLATE
from engine.userdict import UserDict


class Manual:
    """Scheduler whose timers fire only when the test says so."""
    supports_timers = True

    def __init__(self):
        self.jobs = {}
        self.n = 0

    def call_later(self, ms, fn):
        self.n += 1
        self.jobs[self.n] = fn
        return self.n

    def cancel(self, h):
        self.jobs.pop(h, None)

    def call_main(self, fn):
        fn()

    def fire(self):
        for h in list(self.jobs):
            self.jobs.pop(h)()


class FakeTranslator:
    def __init__(self, result="नमस्कार दुनिया"):
        self.result, self.calls = result, []

    def set_target_language(self, code):
        pass

    def translate_async(self, text, cb, mode=None):
        self.calls.append(text)
        cb(self.result)


def mk(tmp, lang="hindi", **kw):
    ud = kw.pop("learner", UserDict(path=f"{tmp}/ud.json"))
    return Session(config=Config(), learner=ud, language=lang, **kw)


def type_(s, text):
    commits = []
    for ch in text:
        r = s.process_key(Key.from_char(ch))
        commits += r.commits
    return commits


def press(s, name, **mods):
    return s.process_key(Key(name=name, **mods))


def test_type_and_space_commits(isolated_config):
    s = mk(isolated_config)
    type_(s, "namaste")
    assert s.preedit == "नमस्ते" and s.buffer == "namaste"
    r = press(s, "space")
    assert r.handled and r.commits == ["नमस्ते", " "] and s.buffer == ""


def test_enter_commits_and_passes_through(isolated_config):
    s = mk(isolated_config)
    type_(s, "aap")
    r = press(s, "return")
    assert r.commits == ["आप"] and r.handled is False


def test_backspace_and_escape(isolated_config):
    s = mk(isolated_config)
    type_(s, "kaa")
    assert press(s, "backspace").handled and s.buffer == "ka"
    assert press(s, "escape").handled and s.buffer == ""
    assert press(s, "escape").handled is False          # nothing buffered: pass through
    assert press(s, "backspace").handled is False


def test_empty_space_passes_through(isolated_config):
    assert mk(isolated_config)._hk_toggle and press(mk(isolated_config), "space").handled is False


def test_tab_cycles_candidates_and_commits_selection(isolated_config):
    s = mk(isolated_config)
    type_(s, "hindi")
    assert s.candidate_texts[:2] == ["हिन्दी", "हिंदी"] and s.lookup_visible
    press(s, "tab")
    assert s.cursor == 1 and s.preedit == s.candidate_texts[1]
    press(s, "tab", shift=True)
    assert s.cursor == 0
    press(s, "down")
    assert s.cursor == 1
    chosen = s.candidate_texts[1]
    assert press(s, "space").commits == [chosen, " "]       # Space commits the HIGHLIGHTED candidate


def test_ctrl_digit_picks_candidate(isolated_config):
    s = mk(isolated_config)
    type_(s, "hindi")
    want = s.candidate_texts[1]
    r = press(s, "2", ctrl=True)
    assert r.handled and r.commits == [want]


def test_ctrl_shortcut_flushes_then_passes_through(isolated_config):
    s = mk(isolated_config)
    type_(s, "aap")
    r = press(s, "c", ctrl=True)
    assert r.handled is False and r.commits == ["आप"]


def test_punctuation_flushes_word_and_converts(isolated_config):
    s = mk(isolated_config, "japanese")
    type_(s, "sakura")
    r = s.process_key(Key.from_char("!"))
    assert r.handled and r.commits == ["さくら", "！"]


def test_comma_with_nothing_buffered_in_japanese_is_converted(isolated_config):
    s = mk(isolated_config, "japanese")
    r = s.process_key(Key.from_char(","))
    assert r.handled and r.commits == ["、"]


def test_hindi_comma_passthrough_when_idle(isolated_config):
    s = mk(isolated_config)
    assert s.process_key(Key.from_char(",")).handled is False


def test_raw_english_with_backslash(isolated_config):
    s = mk(isolated_config)
    type_(s, "\\hello")
    assert s.preedit == "hello"
    assert press(s, "space").commits == ["hello", " "]


def test_hotkeys_toggle_off_passes_everything(isolated_config):
    s = mk(isolated_config)
    type_(s, "aap")
    r = press(s, "f12")
    assert r.handled and r.commits == ["आप"] and not s.enabled
    assert s.process_key(Key.from_char("a")).handled is False
    press(s, "f12")
    assert s.enabled


def test_f11_cycles_languages_and_commits_pending(isolated_config):
    s = mk(isolated_config)
    first = s.language_name
    type_(s, "aap")
    r = press(s, "f11")
    assert r.commits == ["आप"] and s.language_name != first and "अक्षर" in s.aux


def test_cycle_languages_config(isolated_config):
    cfg = Config(); cfg.set("cycle_languages", ["hindi", "korean"])
    s = Session(config=cfg, learner=False, language="hindi")
    press(s, "f11"); assert s.language_name == "Korean"
    press(s, "f11"); assert s.language_name == "Hindi"


def test_custom_hotkey(isolated_config):
    cfg = Config(); cfg.set("toggle_key", "ctrl+shift+space")
    s = Session(config=cfg, learner=False)
    assert press(s, "space", ctrl=True, shift=True).handled and not s.enabled


def test_hotkey_parse():
    assert Hotkey.parse("Ctrl+F12") == Hotkey("f12", ctrl=True)
    assert Hotkey.parse("esc").name == "escape"


def test_learning_promotes_choice_and_completes(isolated_config):
    s = mk(isolated_config)
    type_(s, "hindi"); press(s, "tab"); picked = s.candidate_texts[1]; press(s, "space")
    type_(s, "hindi")
    assert s.candidate_texts[0] == picked                  # learned choice now first
    press(s, "escape")
    type_(s, "dhany")                                      # lexicon completion
    assert "धन्यवाद" in s.candidate_texts


def test_learning_can_be_disabled(isolated_config):
    cfg = Config(); cfg.set("learn", False)
    s = Session(config=cfg, language="hindi")
    assert s.learner is None


def test_user_words_become_completions(isolated_config):
    ud = UserDict(path=f"{isolated_config}/u.json")
    s = mk(isolated_config, learner=ud)
    type_(s, "zzkart"); press(s, "space")
    type_(s, "zzk")
    assert any(c.kind == "complete" for c in s.candidates)


def test_user_dict_persists(isolated_config):
    p = f"{isolated_config}/ud.json"
    ud = UserDict(path=p); ud.record("hindi", "abc", "अबक"); ud.flush()
    assert UserDict(path=p).best("hindi", "abc") == ["अबक"]


def test_numbers_stay_ascii_by_default(isolated_config):
    s = mk(isolated_config)
    type_(s, "12")
    assert s.preedit == "12"


# ---------------- translation mode ---------------- #

def test_translate_mode_flow(isolated_config):
    tr = FakeTranslator()
    s = mk(isolated_config, translator=tr)
    press(s, "f10")
    assert s.mode == MODE_TRANSLATE
    type_(s, "hello world")                  # spaces stay in the phrase
    assert s.buffer == "hello world" and s.preedit == "hello world"
    assert s.candidate_texts[0] == "नमस्कार दुनिया"
    r = press(s, "return")
    assert r.handled and r.commits == ["नमस्कार दुनिया"] and s.buffer == ""


def test_translate_failure_falls_back_to_phonetic(isolated_config):
    s = mk(isolated_config, translator=FakeTranslator(result=None))
    press(s, "f10"); type_(s, "namaste")
    assert s.candidate_texts[0] == "नमस्ते" and "unavailable" in s.aux
    assert press(s, "return").commits == ["नमस्ते"]


def test_translate_debounce_and_pending_enter(isolated_config):
    sched, tr = Manual(), FakeTranslator()
    s = mk(isolated_config, translator=tr, scheduler=sched)
    press(s, "f10")
    type_(s, "how are you")
    assert tr.calls == []                                  # debounced: nothing sent yet
    r = press(s, "return")                                 # still pending: swallow, don't commit
    assert r.handled and r.commits == [] and s.buffer == "how are you"
    sched.fire()
    assert tr.calls == ["how are you"]                     # exactly ONE request for the whole phrase
    assert press(s, "return").commits == ["नमस्कार दुनिया"]


def test_stale_translation_ignored(isolated_config):
    s = mk(isolated_config, translator=FakeTranslator())
    press(s, "f10"); type_(s, "abc")
    s._on_translation("old text", "STALE")
    assert "STALE" not in s.candidate_texts


def test_punctuation_joins_phrase_in_translate_mode(isolated_config):
    s = mk(isolated_config, translator=FakeTranslator())
    press(s, "f10"); type_(s, "hi, there!")
    assert s.buffer == "hi, there!"
