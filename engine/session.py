"""
Akshar — Input Session (the brain of the IME, free of any IBus dependency)

A Session receives abstract Key events and decides what to do:
buffer text, build candidates, commit, switch language/mode, translate.
The IBus engine (main.py) is a thin adapter around it, which means every
behaviour here is unit-testable without a desktop.
"""

import os
from dataclasses import dataclass

from engine.config import Config
from engine.transliterate import (
    create_engine, get_languages_dir, list_available_languages, resolve_language,
)
from engine.translate import TranslationEngine
from engine.userdict import UserDict

MODE_TRANSLITERATE = "transliterate"
MODE_TRANSLATE = "translate"

# Typing one of these ends the current word (and is itself converted: ',' -> '、' in Japanese)
FLUSH_PUNCT = frozenset(",;:!?()[]{}<>\"")

_KEY_ALIASES = {
    "enter": "return", "esc": "escape", "pgup": "pageup", "pgdn": "pagedown",
    "prior": "pageup", "next": "pagedown", "kp_enter": "return", "del": "delete",
    "iso_left_tab": "tab",
}


# ------------------------------------------------------------------ #
#                           KEY MODEL                                 #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class Key:
    """An abstract key press. `name` is lowercase ('space', 'f12', 'a'); `char` is the printable char."""
    name: str = ""
    char: str = ""
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    meta: bool = False

    @classmethod
    def from_char(cls, ch):
        name = "space" if ch == " " else ch.lower()
        return cls(name=name, char=ch, shift=ch.isalpha() and ch.isupper())


@dataclass(frozen=True)
class Hotkey:
    name: str
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    meta: bool = False

    @classmethod
    def parse(cls, spec):
        """'F12', 'ctrl+F12', 'ctrl+shift+space' ..."""
        parts = [p.strip().lower() for p in str(spec).split("+") if p.strip()]
        mods = {"ctrl": False, "alt": False, "shift": False, "meta": False}
        name = ""
        for p in parts:
            if p in ("ctrl", "control"):
                mods["ctrl"] = True
            elif p == "alt":
                mods["alt"] = True
            elif p == "shift":
                mods["shift"] = True
            elif p in ("super", "meta", "win"):
                mods["meta"] = True
            else:
                name = _KEY_ALIASES.get(p, p)
        return cls(name=name, **mods)

    def matches(self, key):
        return (key.name == self.name and key.ctrl == self.ctrl and key.alt == self.alt
                and key.shift == self.shift and key.meta == self.meta)


@dataclass
class KeyResult:
    handled: bool                 # True = we consumed the key, False = let the app see it
    commits: list                 # text to commit BEFORE the key is passed on (may be empty)


@dataclass
class Candidate:
    text: str
    kind: str = "alt"             # learned | alt | complete | raw | translation | phonetic | english
    roman: str = ""               # the romanised input this candidate stands for


class NullScheduler:
    """No timers (CLI / simple tests). Callbacks marshalled to 'main' run immediately."""
    supports_timers = False

    def call_later(self, ms, fn):
        return None

    def cancel(self, handle):
        pass

    def call_main(self, fn):
        fn()


# ------------------------------------------------------------------ #
#                             SESSION                                 #
# ------------------------------------------------------------------ #

class Session:
    def __init__(self, config=None, learner=None, translator=None, scheduler=None,
                 language=None, on_update=None):
        """
        learner   : UserDict, None (create default if config.learn), or False (disable)
        translator: TranslationEngine or None (created lazily)
        scheduler : object with call_later/cancel/call_main (GLib adapter in main.py)
        on_update : callback fired when state changes asynchronously (translation arrived ...)
        """
        self.config = config or Config()
        if learner is None:
            learner = UserDict() if self.config.get("learn", True) else False
        self.learner = learner or None
        self.translator = translator
        self.scheduler = scheduler or NullScheduler()
        self.on_update = on_update

        self.languages = list_available_languages()
        self._engines = {}
        self.engine = None

        self.enabled = True
        self.mode = MODE_TRANSLITERATE
        self.buffer = ""
        self.candidates = []
        self.cursor = 0
        self.aux = ""
        self._tr_state = "idle"        # idle | pending | ready | failed
        self._tr_timer = None
        self._aux_timer = None

        self._parse_hotkeys()
        self.set_language(language or self.config.default_language)

    # ============================================================== #
    #                         PUBLIC STATE                            #
    # ============================================================== #

    @property
    def language_name(self):
        return self.engine.name if self.engine else "—"

    @property
    def lang_key(self):
        return self.engine.stem if self.engine else ""

    @property
    def candidate_texts(self):
        return [c.text for c in self.candidates]

    @property
    def page_size(self):
        return max(1, int(self.config.get("candidate_page_size", 6)))

    @property
    def preedit(self):
        """Text shown underlined in the application while composing."""
        if not self.buffer:
            return ""
        if self.mode == MODE_TRANSLATE:
            return self.buffer                       # show what was typed; translations go in the list
        if self.candidates:
            return self.candidates[min(self.cursor, len(self.candidates) - 1)].text
        return self.engine.get_preedit(self.buffer)

    @property
    def lookup_visible(self):
        if not self.buffer or not self.config.get("show_candidates", True):
            return False
        return len(self.candidates) >= (1 if self.mode == MODE_TRANSLATE else 2)

    @property
    def status_text(self):
        mode = "⇄" if self.mode == MODE_TRANSLATE else "⌨"
        return f"{mode} {self.language_name}" + ("" if self.enabled else " (off)")

    # ============================================================== #
    #                    LANGUAGE / MODE / SWITCHES                   #
    # ============================================================== #

    def _parse_hotkeys(self):
        c = self.config
        self._hk_toggle = Hotkey.parse(c.get("toggle_key", "F12"))
        self._hk_lang = Hotkey.parse(c.get("switch_language_key", "F11"))
        self._hk_mode = Hotkey.parse(c.get("mode_key", "F10"))

    def _load_engine(self, file):
        if file not in self._engines:
            self._engines[file] = create_engine(file)
        eng = self._engines[file]
        eng.convert_numbers = bool(self.config.get("convert_numbers", False))
        eng.show_diacritics = bool(self.config.get("show_diacritics", False))
        if not self.config.get("smart_capitalize", True):
            eng.smart_capitalize = False
        return eng

    def set_language(self, name):
        """Switch language by file name, code or alias. Returns True on success."""
        file = resolve_language(name) or name
        try:
            eng = self._load_engine(file)
        except (OSError, ValueError, KeyError):
            if self.engine is None:                       # first load failed: fall back to Hindi
                try:
                    eng = self._load_engine("hindi.json")
                except (OSError, ValueError, KeyError):
                    return False
            else:
                return False
        self.engine = eng
        if self.translator is not None:
            self.translator.set_target_language(eng.code)
        self._reset_buffer()
        return True

    def _cycle_files(self):
        wanted = self.config.get("cycle_languages", []) or []
        files = [l["file"] for l in self.languages]
        chosen = [resolve_language(w) for w in wanted]
        chosen = [f for f in chosen if f in files]
        return chosen or files

    def cycle_language(self):
        files = self._cycle_files()
        if not files:
            return False
        cur = self.engine.file if self.engine else None
        nxt = files[(files.index(cur) + 1) % len(files)] if cur in files else files[0]
        ok = self.set_language(nxt)
        if ok:
            self.flash(f"अक्षर · {self.language_name}")
        return ok

    def toggle_enabled(self):
        self.enabled = not self.enabled
        self.flash(f"अक्षर: {'ON ✓' if self.enabled else 'OFF ✗'}")

    def toggle_mode(self):
        self.mode = MODE_TRANSLATE if self.mode == MODE_TRANSLITERATE else MODE_TRANSLITERATE
        if self.mode == MODE_TRANSLATE and self._get_translator() is None:
            self.mode = MODE_TRANSLITERATE
            self.flash("Translation unavailable")
            return
        label = "Translate (meaning)" if self.mode == MODE_TRANSLATE else "Transliterate (sounds)"
        self.flash(f"अक्षर · {self.language_name} · {label}")

    def flash(self, message, ms=2000):
        """Show a transient auxiliary message."""
        self.aux = message
        self.scheduler.cancel(self._aux_timer)
        self._aux_timer = self.scheduler.call_later(ms, self._clear_aux)
        self._notify()

    def _clear_aux(self):
        self.aux = ""
        self._notify()

    def _notify(self):
        if self.on_update:
            self.on_update()

    # ============================================================== #
    #                      CANDIDATE GENERATION                       #
    # ============================================================== #

    def _build_candidates(self, final):
        buf = self.buffer
        if not buf:
            return []
        if buf.startswith("\\"):                        # \word  -> type English as-is
            raw = buf[1:]
            return [Candidate(raw, "raw", buf)] if raw else []

        eng = self.engine
        limit = int(self.config.get("max_candidates", 12))
        out, seen = [], set()

        def add(text, kind, roman=None):
            if text and text not in seen:
                seen.add(text)
                out.append(Candidate(text, kind, roman if roman is not None else buf))

        if self.learner:
            for w in self.learner.best(self.lang_key, buf):
                add(w, "learned")
        for w in eng.candidates(buf, limit=limit, final=final):
            add(w, "alt")

        if (self.config.get("completion", True) and len(buf) >= int(self.config.get("completion_min_chars", 2))
                and not any(ch.isspace() for ch in buf)):
            comps = eng.completions(buf, limit=3)
            if self.learner:
                comps = comps + self.learner.suggest(self.lang_key, buf, limit=3)
            for roman, native in comps:
                add(native, "complete", roman)
        return out

    def _refresh(self):
        self.cursor = 0
        if not self.buffer:
            self.candidates = []
            self.scheduler.cancel(self._tr_timer)
            self._tr_state = "idle"
            return
        if self.mode == MODE_TRANSLATE:
            self._refresh_translate()
        else:
            self.candidates = self._build_candidates(final=False)

    # ============================================================== #
    #                           TRANSLATION                           #
    # ============================================================== #

    def _get_translator(self):
        if self.translator is None:
            try:
                self.translator = TranslationEngine(
                    self.engine.code if self.engine else "hi",
                    backend=self.config.get("translation_backend", "auto"),
                    timeout=float(self.config.get("translation_timeout", 4.0)),
                )
            except Exception:
                self.translator = None
        elif self.engine:
            self.translator.set_target_language(self.engine.code)
        return self.translator

    def _phonetic_and_english(self):
        return [
            Candidate(self.engine.transliterate(self.buffer, final=True), "phonetic", self.buffer),
            Candidate(self.buffer, "english", self.buffer),
        ]

    def _refresh_translate(self):
        self.candidates = self._phonetic_and_english()
        self._tr_state = "pending"
        self.scheduler.cancel(self._tr_timer)
        text = self.buffer
        ms = int(self.config.get("translation_debounce_ms", 600))
        if ms <= 0 or not self.scheduler.supports_timers:
            self._request_translation(text)
        else:
            self._tr_timer = self.scheduler.call_later(ms, lambda: self._request_translation(text))

    def _request_translation(self, text):
        if text != self.buffer or self.mode != MODE_TRANSLATE:
            return
        tr = self._get_translator()
        if tr is None:
            self._on_translation(text, None)
            return

        def cb(result):                                   # runs on the worker thread
            self.scheduler.call_main(lambda: self._on_translation(text, result))
        tr.translate_async(text, cb)

    def _on_translation(self, text, result):
        if text != self.buffer or self.mode != MODE_TRANSLATE:
            return                                        # user kept typing — stale
        if result:
            self._tr_state = "ready"
            self.candidates = [Candidate(result, "translation", text)] + self._phonetic_and_english()
            self.cursor = 0
            self.aux = ""
        else:
            self._tr_state = "failed"
            self.aux = "Translation unavailable — showing phonetic spelling"
        self._notify()

    # ============================================================== #
    #                         COMMIT / RESET                          #
    # ============================================================== #

    def _reset_buffer(self):
        self.scheduler.cancel(self._tr_timer)
        self.buffer = ""
        self.candidates = []
        self.cursor = 0
        self._tr_state = "idle"

    def commit_pending(self):
        """Commit whatever is being composed (focus loss, mode switch ...). Returns a list of strings."""
        if not self.buffer:
            return []
        if self.mode == MODE_TRANSLATE:
            text = (self.candidates[min(self.cursor, len(self.candidates) - 1)].text
                    if self.candidates else self.buffer)
            self._reset_buffer()
            return [text]

        final = self._build_candidates(final=True)
        if not final:
            self._reset_buffer()
            return []
        cand = final[min(self.cursor, len(final) - 1)]
        if self.learner and cand.kind != "raw" and self.config.get("learn", True):
            roman = cand.roman
            if len(roman) >= 2:
                self.learner.record(self.lang_key, roman, cand.text)
        self._reset_buffer()
        return [cand.text]

    def discard(self):
        """Drop the composing buffer without committing (Escape / engine reset)."""
        self._reset_buffer()

    def shutdown(self):
        if self.learner:
            self.learner.flush()

    # ============================================================== #
    #                           KEY HANDLING                          #
    # ============================================================== #

    def _move(self, delta):
        n = len(self.candidates)
        if n:
            self.cursor = (self.cursor + delta) % n

    def process_key(self, key):
        """Feed one key press. Returns KeyResult(handled, commits)."""
        # ---- global hotkeys work even when switched off ----
        for hk, action in ((self._hk_toggle, self.toggle_enabled),
                           (self._hk_lang, self.cycle_language),
                           (self._hk_mode, self.toggle_mode)):
            if hk.matches(key):
                commits = self.commit_pending()
                action()
                return KeyResult(True, commits)

        if not self.enabled or self.engine is None:
            return KeyResult(False, [])

        # ---- Ctrl/Alt/Super combos ----
        if key.ctrl or key.alt or key.meta:
            if (key.ctrl and not key.alt and not key.meta and len(key.name) == 1
                    and key.name in "123456789" and self.lookup_visible):
                idx = (self.cursor // self.page_size) * self.page_size + int(key.name) - 1
                if idx < len(self.candidates):
                    self.cursor = idx
                    return KeyResult(True, self.commit_pending())
            return KeyResult(False, self.commit_pending())     # app shortcut: flush, then pass through

        name = key.name
        translating = self.mode == MODE_TRANSLATE

        if name == "escape":
            if self.buffer:
                self.discard()
                return KeyResult(True, [])
            return KeyResult(False, [])

        if name == "backspace":
            if self.buffer:
                self.buffer = self.buffer[:-1]
                self._refresh()
                return KeyResult(True, [])
            return KeyResult(False, [])

        if name == "space":
            if not self.buffer:
                return KeyResult(False, [])
            if translating:                                   # spaces belong to the phrase
                self.buffer += " "
                self._refresh()
                return KeyResult(True, [])
            commits = self.commit_pending()
            commits.append(" ")
            return KeyResult(True, commits)

        if name == "return":
            if not self.buffer:
                return KeyResult(False, [])
            if translating:
                if self._tr_state == "pending":
                    self.flash("Translating…")
                    return KeyResult(True, [])
                return KeyResult(True, self.commit_pending())  # commit, swallow Enter
            return KeyResult(False, self.commit_pending())     # commit, let Enter through

        if name == "tab":
            if self.buffer and len(self.candidates) > 1:
                self._move(-1 if key.shift else 1)
                return KeyResult(True, [])
            return KeyResult(False, self.commit_pending())

        if name in ("down", "up") and self.buffer and self.candidates:
            self._move(1 if name == "down" else -1)
            return KeyResult(True, [])

        if name in ("pagedown", "pageup") and self.buffer and self.candidates:
            self._move(self.page_size if name == "pagedown" else -self.page_size)
            return KeyResult(True, [])

        # ---- printable characters ----
        ch = key.char
        if ch and len(ch) == 1 and 32 < ord(ch) < 127:
            if not translating and ch in FLUSH_PUNCT:
                commits = self.commit_pending()
                converted = self.engine.transliterate(ch)
                if commits or converted != ch:
                    commits.append(converted)
                    return KeyResult(True, commits)
                return KeyResult(False, [])
            self.buffer += ch
            self._refresh()
            return KeyResult(True, [])

        # ---- anything else (arrows, Home, Delete, F-keys ...) ----
        return KeyResult(False, self.commit_pending())
