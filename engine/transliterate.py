"""
Akshar — Transliteration Engine

Converts romanised (Latin-keyboard) input into other scripts.

Script types (selected by "script_type" in a language JSON file):

  abugida    Devanagari, Bengali, Gujarati, Gurmukhi, Odia, Telugu, Kannada,
             Malayalam, Tamil ...   consonant + vowel-sign logic, halant clusters
  syllabary  Japanese Hiragana / Katakana   romaji -> kana, small tsu, ん, ー
  hangul     Korean   Revised-Romanization -> composed Hangul syllables
  abjad      Arabic, Urdu   short vowels omitted, long vowels written
  alphabet   Russian, Greek ...   direct longest-match letter mapping

On top of the raw algorithm every engine supports:

  * a per-language LEXICON of exact word overrides (and kanji / alternates)
  * smart capitalisation ("Namaste" behaves like "namaste")
  * alternate CANDIDATES (spelling variants, other scripts, lexicon entries)
  * prefix COMPLETIONS from the lexicon
"""

import bisect
import json
import os
import re

# ------------------------------------------------------------------ #
#                           CONSTANTS                                 #
# ------------------------------------------------------------------ #

SCRIPT_TYPES = ("abugida", "syllabary", "hangul", "abjad", "alphabet")

# Punctuation that is peeled off the edges of a word before conversion
LEAD_PUNCT = frozenset("([{<\"“‘¿¡")
TRAIL_PUNCT = frozenset(".,;:!?)]}>\"”’…")

_WS_SPLIT = re.compile(r"(\s+)")

# --- Hangul composition tables --------------------------------------- #
_H_INITIAL = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_H_VOWEL = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_H_FINAL = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ",
            "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

# roman -> (initial jamo, final jamo or None)
_H_CONSONANTS = {
    "g": ("ㄱ", "ㄱ"), "kk": ("ㄲ", "ㄲ"), "k": ("ㅋ", "ㄱ"),
    "n": ("ㄴ", "ㄴ"), "d": ("ㄷ", "ㄷ"), "tt": ("ㄸ", None), "t": ("ㅌ", "ㄷ"),
    "r": ("ㄹ", "ㄹ"), "l": ("ㄹ", "ㄹ"), "m": ("ㅁ", "ㅁ"),
    "b": ("ㅂ", "ㅂ"), "pp": ("ㅃ", None), "p": ("ㅍ", "ㅂ"),
    "s": ("ㅅ", "ㅅ"), "ss": ("ㅆ", "ㅆ"), "j": ("ㅈ", "ㅈ"), "jj": ("ㅉ", None),
    "ch": ("ㅊ", "ㅊ"), "h": ("ㅎ", "ㅎ"), "ng": ("ㅇ", "ㅇ"),
}
_H_VOWELS = {
    "a": "ㅏ", "ae": "ㅐ", "ya": "ㅑ", "yae": "ㅒ", "eo": "ㅓ", "e": "ㅔ", "yeo": "ㅕ",
    "ye": "ㅖ", "o": "ㅗ", "wa": "ㅘ", "wae": "ㅙ", "oe": "ㅚ", "yo": "ㅛ", "u": "ㅜ",
    "wo": "ㅝ", "we": "ㅞ", "wi": "ㅟ", "yu": "ㅠ", "eu": "ㅡ", "ui": "ㅢ", "i": "ㅣ",
}
_H_CLUSTERS = {
    ("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ",
    ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ", ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ",
    ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ",
}
_H_ALL_TOKENS = set(_H_CONSONANTS) | set(_H_VOWELS)


# ------------------------------------------------------------------ #
#                          THE ENGINE                                 #
# ------------------------------------------------------------------ #

class TransliterationEngine:
    """Convert romanised text into the target script described by a language file."""

    def __init__(self, language_file_path, load_lexicon=True):
        with open(language_file_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.path = os.path.abspath(language_file_path)
        self.file = os.path.basename(self.path)
        self.stem = os.path.splitext(self.file)[0]

        self.name = self.data["name"]
        self.code = self.data["code"]
        self.script = self.data.get("script", "")
        self.script_type = self.data["script_type"]
        if self.script_type not in SCRIPT_TYPES:
            raise ValueError(f"{self.file}: unknown script_type '{self.script_type}'")

        self.aliases = [a.lower() for a in self.data.get("aliases", [])]
        self.punctuation = self.data.get("punctuation", {})
        self.smart_capitalize = self.data.get("smart_capitalize", self.script_type == "abugida")
        self.convert_numbers = True          # sessions override from user config
        self.show_diacritics = False         # abjad: write short-vowel marks

        # Alternate-candidate machinery
        self.variants = [(re.compile(p), r) for p, r in self.data.get("variants", [])]
        self._alt_files = self.data.get("alt_candidates", [])
        self._alt_engines = None

        {
            "abugida": self._init_abugida,
            "syllabary": self._init_syllabary,
            "hangul": self._init_hangul,
            "abjad": self._init_abjad,
            "alphabet": self._init_alphabet,
        }[self.script_type]()

        self._build_prefix_set()

        self.lexicon = {}
        self._lex_keys = []
        if load_lexicon:
            self._load_lexicon()

    # ============================================================== #
    #                        INITIALISATION                           #
    # ============================================================== #

    def _init_abugida(self):
        d = self.data
        self.consonants = d.get("consonants", {})
        self.conjuncts = d.get("conjuncts", {})
        self.vowels_independent = d.get("vowels_independent", {})
        self.vowels_matra = d.get("vowels_matra", {})
        self.modifiers = d.get("modifiers", {})
        self.halant = d.get("halant", "")
        self.specials = d.get("specials", {})
        self.numbers = d.get("numbers", {})
        self.separator = d.get("separator", "_")
        self.halant_key = d.get("halant_key", "^")
        self.final_halant = d.get("final_halant", False)

        # Conjuncts take priority over plain consonants
        self._all_consonants = dict(self.consonants)
        self._all_consonants.update(self.conjuncts)

        self._vowel_keys = set(self.vowels_independent)
        self._consonant_keys = set(self._all_consonants)
        self._modifier_keys = set(self.modifiers)
        keys = (list(self._all_consonants) + list(self.vowels_independent)
                + list(self.modifiers) + list(self.specials))
        self._max_token = max((len(k) for k in keys), default=1)

    def _init_syllabary(self):
        d = self.data
        self.kana = d.get("kana", {})
        self.small_tsu = d.get("small_tsu", "")
        self.long_vowel_mark = d.get("long_vowel_mark", "ー")
        self.long_vowel_style = d.get("long_vowel_style", "none")
        # kept for backward compatibility with older language files
        self.double_consonant_triggers = d.get("double_consonant_triggers", [])
        self.n_standalone_triggers = d.get("n_standalone_triggers", [])
        self._max_token = max((len(k) for k in self.kana), default=1)

    def _init_hangul(self):
        self._max_token = 3

    def _init_abjad(self):
        d = self.data
        self.consonants = d.get("consonants", {})
        self.long_vowels = d.get("long_vowels", {})
        self.initial_vowels = d.get("initial_vowels", {})
        self.final_vowels = d.get("final_vowels", {})
        self.short_vowel_marks = d.get("short_vowel_marks", {})
        self.digit_letters = d.get("digit_letters", {})
        self.numbers = d.get("numbers", {})
        self._abjad_tokens = {}
        self._abjad_tokens.update({k: ("C", v) for k, v in self.consonants.items()})
        self._abjad_tokens.update({k: ("L", v) for k, v in self.long_vowels.items()})
        self._max_token = max(len(k) for k in self._abjad_tokens)

    def _init_alphabet(self):
        d = self.data
        self.alphabet = {k.lower(): v for k, v in d.get("alphabet", {}).items()}
        self.final_forms = d.get("final_forms", {})
        self.context_rules = d.get("context_rules", {})
        self._max_token = max(len(k) for k in self.alphabet)

    def _build_prefix_set(self):
        """All valid prefixes of input tokens — for 'could this buffer still grow?' checks."""
        t = self.script_type
        if t == "abugida":
            keys = (list(self._all_consonants) + list(self.vowels_independent)
                    + list(self.modifiers) + list(self.specials))
        elif t == "syllabary":
            keys = list(self.kana) + list(self.punctuation)
        elif t == "hangul":
            keys = list(_H_ALL_TOKENS)
        elif t == "abjad":
            keys = list(self._abjad_tokens) + ["a", "i", "u", "e", "o"]
        else:
            keys = list(self.alphabet)
        self._valid_prefixes = set()
        for key in keys:
            for i in range(1, len(key) + 1):
                self._valid_prefixes.add(key[:i])

    def _load_lexicon(self):
        spec = self.data.get("lexicon")
        words = None
        if isinstance(spec, dict):
            words = spec
        else:
            rel = spec if isinstance(spec, str) else os.path.join("lexicon", self.stem + ".json")
            path = os.path.join(os.path.dirname(self.path), rel)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        words = json.load(f).get("words", {})
                except (OSError, ValueError):
                    words = None
        if not words:
            return
        for roman, native in words.items():
            vals = [native] if isinstance(native, str) else list(native)
            if vals:
                self.lexicon[roman.lower()] = vals
        self._lex_keys = sorted(self.lexicon)

    # ============================================================== #
    #                           PUBLIC API                            #
    # ============================================================== #

    def transliterate(self, text, final=True, use_lexicon=True):
        """
        Convert romanised text (a word, or a whole sentence) to the target script.

        final=False is used for live preview while typing: ambiguous trailing
        input (like a lone 'n' in Japanese) is left as typed instead of being
        resolved early.
        """
        if not text:
            return ""
        parts = _WS_SPLIT.split(text)
        out = []
        for idx, part in enumerate(parts):
            if not part or part.isspace():
                out.append(part)
                continue
            last_word = all((not p) or p.isspace() for p in parts[idx + 1:])
            out.append(self._convert_token(part, final or not last_word, use_lexicon))
        return "".join(out)

    def get_preedit(self, buffer):
        """Live-preview text for the composing buffer."""
        return self.transliterate(buffer, final=False) if buffer else ""

    def has_possible_continuation(self, buffer):
        """True if `buffer` is a prefix of some valid input token."""
        return buffer in self._valid_prefixes or buffer.lower() in self._valid_prefixes

    def candidates(self, text, limit=8, final=True):
        """
        Ranked list of possible outputs for ONE word:
          lexicon entries  ->  algorithmic result  ->  spelling variants  ->  other scripts
        The first entry is what plain transliteration would commit.
        """
        if not text:
            return []
        if not text.strip() or _WS_SPLIT.search(text.strip()):
            return [self.transliterate(text, final=final)]

        lead, core, trail = self._split_token(text)
        core_final = final or bool(trail)
        lead_c = self._convert_core(lead, True) if lead else ""
        trail_c = self._convert_core(trail, True) if trail else ""

        results, seen = [], set()

        def add(s):
            if s and s not in seen:
                seen.add(s)
                results.append(lead_c + s + trail_c)

        if not core:
            return [lead_c + trail_c]

        c = self._smart_case(core)
        for w in self.lexicon.get(c.lower(), []):
            add(w)
        add(self._convert_core(c, core_final))
        for v in self._variant_inputs(c):
            add(self._convert_core(v, core_final))
        for alt in self._get_alt_engines():
            add(alt._convert_core(alt._smart_case(core), core_final))
        return results[:limit]

    def completions(self, prefix, limit=5):
        """Lexicon words starting with `prefix` -> [(roman, native), ...] (shortest first)."""
        p = prefix.lower()
        if not p or not self._lex_keys:
            return []
        lo = bisect.bisect_left(self._lex_keys, p)
        matches = []
        for k in self._lex_keys[lo:]:
            if not k.startswith(p):
                break
            if k != p:
                matches.append(k)
        matches.sort(key=lambda k: (len(k), k))
        return [(k, self.lexicon[k][0]) for k in matches[:limit]]

    # ============================================================== #
    #                       TOKEN-LEVEL HELPERS                       #
    # ============================================================== #

    @staticmethod
    def _split_token(token):
        i = 0
        while i < len(token) and token[i] in LEAD_PUNCT:
            i += 1
        j = len(token)
        while j > i and token[j - 1] in TRAIL_PUNCT:
            j -= 1
        return token[:i], token[i:j], token[j:]

    def _smart_case(self, core):
        """
        'Namaste' -> 'namaste' when only the FIRST letter is capital
        (sentence-start capitalisation), but leave deliberate capitals alone
        in 'NaMaste', 'DaTa', 'OM' and single letters.
        """
        if (self.smart_capitalize and len(core) > 1 and core[0].isupper()
                and not any(ch.isupper() for ch in core[1:])):
            return core[0].lower() + core[1:]
        return core

    def _convert_token(self, token, final, use_lexicon):
        lead, core, trail = self._split_token(token)
        out = self._convert_core(lead, True) if lead else ""
        if core:
            c = self._smart_case(core)
            hit = self.lexicon.get(c.lower()) if use_lexicon else None
            out += hit[0] if hit else self._convert_core(c, final or bool(trail))
        if trail:
            out += self._convert_core(trail, True)
        return out

    def _convert_core(self, text, final):
        t = self.script_type
        if t == "abugida":
            return self._convert_abugida(text, final)
        if t == "syllabary":
            return self._convert_syllabary(text, final)
        if t == "hangul":
            return self._convert_hangul(text)
        if t == "abjad":
            return self._convert_abjad(text, final)
        return self._convert_alphabet(text, final)

    def _variant_inputs(self, c, max_results=60):
        """
        Spelling-variant inputs.
        Level 1: every rule applied to all occurrences, then to single occurrences.
        Level 2: every rule applied (all occurrences) to the first few level-1 results,
                 so combinations such as  gujarati -> gujaraatee  are reachable.
        """
        seen = {c}
        level1 = []
        for pat, repl in self.variants:
            alls = pat.sub(repl, c)
            if alls not in seen:
                seen.add(alls)
                level1.append(alls)
            matches = list(pat.finditer(c))
            if len(matches) > 1:
                for m in matches[:3]:
                    one = c[:m.start()] + m.expand(repl) + c[m.end():]
                    if one not in seen:
                        seen.add(one)
                        level1.append(one)
        level2 = []
        for base in level1[:10]:
            for pat, repl in self.variants:
                v = pat.sub(repl, base)
                if v not in seen:
                    seen.add(v)
                    level2.append(v)
        return (level1 + level2)[:max_results]

    def _get_alt_engines(self):
        if self._alt_engines is None:
            self._alt_engines = []
            for fname in self._alt_files:
                path = os.path.join(os.path.dirname(self.path), fname)
                if os.path.exists(path):
                    try:
                        self._alt_engines.append(TransliterationEngine(path, load_lexicon=False))
                    except (OSError, ValueError, KeyError):
                        pass
        return self._alt_engines

    # ============================================================== #
    #                    ABUGIDA  (Hindi, Tamil, ...)                 #
    # ============================================================== #

    def _convert_abugida(self, text, final=True):
        """
        Longest-match scan, left to right.
          consonant after consonant  -> halant between them
          vowel after consonant      -> dependent vowel sign (matra)
          vowel otherwise            -> independent vowel letter
          '_'                        -> separator (breaks conjuncts / vowel pairs)
          '^' after a consonant      -> explicit halant
        """
        out = []
        i, n = 0, len(text)
        prev_cons = False

        while i < n:
            ch = text[i]

            if ch == self.separator:
                prev_cons = False
                i += 1
                continue

            # decimal point inside a number: keep as '.'
            if ch == "." and 0 < i < n - 1 and text[i - 1].isdigit() and text[i + 1].isdigit():
                out.append(".")
                prev_cons = False
                i += 1
                continue

            matched = False
            for length in range(min(self._max_token, n - i), 0, -1):
                chunk = text[i:i + length]
                if chunk in self.specials:
                    out.append(self.specials[chunk])
                    prev_cons = False
                elif chunk in self.modifiers:
                    out.append(self.modifiers[chunk])
                    prev_cons = False
                elif chunk in self._all_consonants:
                    if prev_cons:
                        out.append(self.halant)
                    out.append(self._all_consonants[chunk])
                    prev_cons = True
                elif chunk in self.vowels_independent:
                    if prev_cons:
                        out.append(self.vowels_matra.get(chunk, ""))
                    else:
                        out.append(self.vowels_independent[chunk])
                    prev_cons = False
                else:
                    continue
                i += length
                matched = True
                break
            if matched:
                continue

            if ch == self.halant_key and prev_cons:
                out.append(self.halant)
                prev_cons = False
                i += 1
                continue

            if ch in self.numbers and self.convert_numbers:
                out.append(self.numbers[ch])
            else:
                out.append(self.punctuation.get(ch, ch))
            prev_cons = False
            i += 1

        # Tamil-style: a word never ends in a bare consonant — add the pulli
        if self.final_halant and final and prev_cons:
            out.append(self.halant)
        return "".join(out)

    # ============================================================== #
    #                  SYLLABARY  (Hiragana / Katakana)               #
    # ============================================================== #

    def _convert_syllabary(self, text, final=True):
        """
        Rules: っ for doubled consonants (and 'tch'), ん handling
        (n' / nn / n before consonant / final n), longest-match kana,
        and ー for repeated vowels when long_vowel_style == 'mark'.
        """
        s = text.lower() if text else ""
        out = []
        i, n = 0, len(s)
        last_vowel = None            # vowel that ended the previous kana (for ー)
        mark_style = self.long_vowel_style == "mark"
        kana_n = self.kana.get("n", "ん")

        while i < n:
            ch = s[i]
            nxt = s[i + 1] if i + 1 < n else ""

            if ch in self.punctuation:
                out.append(self.punctuation[ch])
                last_vowel = None
                i += 1
                continue

            if ch == "'":                     # explicit separator: n'a -> んあ
                i += 1
                continue

            # --- ん handling ---
            if ch == "n":
                if not nxt:
                    if final:
                        out.append(kana_n)
                        last_vowel = None
                    else:
                        out.append("n")       # live preview: wait for more input
                    i += 1
                    continue
                if nxt == "'":
                    out.append(kana_n)
                    last_vowel = None
                    i += 2
                    continue
                if nxt == "n":
                    after = s[i + 2] if i + 2 < n else ""
                    if after and (after in "aeiouy"):
                        # konnichiwa: first n is ん, second starts 'ni'
                        out.append(kana_n)
                        last_vowel = None
                        i += 1
                    else:
                        out.append(kana_n)    # 'nn' alone / before consonant
                        last_vowel = None
                        i += 2
                    continue
                if nxt not in "aeiouy":
                    out.append(kana_n)        # n before a consonant
                    last_vowel = None
                    i += 1
                    continue
                # else: fall through to na / ni / nya ...

            # --- っ for doubled consonants ('kk') and 'tch' ---
            if ch.isalpha() and ch not in "aeioun":
                if nxt == ch or (ch == "t" and s[i + 1:i + 3] == "ch"):
                    if ch == "m" and nxt == "m":
                        out.append(kana_n)    # 'mm' -> ん + m...
                    else:
                        out.append(self.small_tsu)
                    last_vowel = None
                    i += 1
                    continue
                if ch == "m" and nxt in ("b", "p"):
                    out.append(kana_n)        # shimbun -> しんぶん
                    last_vowel = None
                    i += 1
                    continue

            # --- longest kana match ---
            for length in range(min(self._max_token, n - i), 0, -1):
                chunk = s[i:i + length]
                if chunk in self.kana:
                    if (mark_style and chunk in ("a", "i", "u", "e", "o")
                            and chunk == last_vowel):
                        out.append(self.long_vowel_mark)      # raamen -> ラーメン
                    else:
                        out.append(self.kana[chunk])
                    last_vowel = chunk[-1] if chunk[-1] in "aeiou" else None
                    i += length
                    break
            else:
                out.append(ch)                # unrecognised -> pass through
                last_vowel = None
                i += 1

        return "".join(out)

    # ============================================================== #
    #                         HANGUL (Korean)                         #
    # ============================================================== #

    @staticmethod
    def _hangul_tokenize(s):
        tokens, i, n = [], 0, len(s)
        while i < n:
            step = 1
            for length in (3, 2, 1):
                chunk = s[i:i + length]
                if chunk in _H_VOWELS:
                    tokens.append(("V", chunk))
                    step = length
                    break
                if chunk in _H_CONSONANTS:
                    tokens.append(("C", chunk))
                    step = length
                    break
            else:
                tokens.append(("X", s[i]))
            i += step
        # 'ng' directly before a vowel is really n + g  (hangeul -> han-geul)
        fixed = []
        for idx, (kind, val) in enumerate(tokens):
            nxt_kind = tokens[idx + 1][0] if idx + 1 < len(tokens) else None
            if kind == "C" and val == "ng" and nxt_kind == "V":
                fixed.extend([("C", "n"), ("C", "g")])
            else:
                fixed.append((kind, val))
        return fixed

    def _convert_hangul(self, text):
        out = []
        for run in re.split(r"([a-zA-Z]+)", text):
            if run and run.isascii() and run.isalpha():
                out.append(self._hangul_word(run.lower()))
            else:
                out.append("".join(self.punctuation.get(ch, ch)
                                   for ch in run if ch not in "-'"))
        return "".join(out)

    def _hangul_word(self, s):
        tokens = self._hangul_tokenize(s)
        out = []
        cur = None      # [initial, vowel, final]

        def flush():
            nonlocal cur
            if cur is None:
                return
            ini, vow, fin = cur
            if vow is not None:
                code = (0xAC00 + (_H_INITIAL.index(ini) * 21 + _H_VOWEL.index(vow)) * 28
                        + _H_FINAL.index(fin or ""))
                out.append(chr(code))
            else:
                out.append(ini)          # stray consonant: standalone jamo
            cur = None

        for idx, (kind, val) in enumerate(tokens):
            nxt = tokens[idx + 1][0] if idx + 1 < len(tokens) else None
            if kind == "X":
                flush()
                out.append(val)
            elif kind == "V":
                jamo = _H_VOWELS[val]
                if cur is None or cur[1] is not None:
                    flush()
                    cur = ["ㅇ", jamo, None]       # vowel-initial syllable: silent ㅇ
                else:
                    cur[1] = jamo
            else:  # consonant
                init, fin = _H_CONSONANTS[val]
                if cur is None:
                    cur = [init, None, None]
                elif cur[1] is None:                # consonant after consonant, no vowel yet
                    flush()
                    cur = [init, None, None]
                elif cur[2] is None:
                    if nxt == "V" or fin is None:   # starts the next syllable
                        flush()
                        cur = [init, None, None]
                    else:
                        cur[2] = fin
                else:                                # already has a final
                    cluster = _H_CLUSTERS.get((cur[2], fin)) if (fin and nxt != "V") else None
                    if cluster:
                        cur[2] = cluster
                    else:
                        flush()
                        cur = [init, None, None]
        flush()
        return "".join(out)

    # ============================================================== #
    #                       ABJAD (Arabic, Urdu)                      #
    # ============================================================== #

    def _convert_abjad(self, text, final=True):
        # pure number -> numerals
        if text and all(ch.isdigit() or ch in ".," for ch in text) and any(ch.isdigit() for ch in text):
            return "".join(self.numbers.get(ch, ch) if self.convert_numbers else ch
                           for ch in text)

        has_letters = any(ch.isalpha() for ch in text)
        out = []
        i, n = 0, len(text)
        at_start = True

        while i < n:
            ch = text[i]

            # chat-alphabet digits inside a word (3 -> ع, 7 -> ح ...)
            if ch.isdigit() and has_letters and ch in self.digit_letters:
                out.append(self.digit_letters[ch])
                at_start = False
                i += 1
                continue

            matched = False
            for length in range(min(self._max_token, n - i), 0, -1):
                chunk = text[i:i + length]
                for cand in (chunk, chunk.lower()):
                    tok = self._abjad_tokens.get(cand)
                    if tok:
                        out.append(tok[1])
                        at_start = False
                        i += length
                        matched = True
                        break
                if matched:
                    break
            if matched:
                continue

            low = ch.lower()
            if low in "aeiou":
                at_end = i == n - 1
                if at_start:
                    out.append(self.initial_vowels.get(low, ""))
                elif at_end:
                    out.append(self.final_vowels.get(low, ""))
                elif self.show_diacritics:
                    out.append(self.short_vowel_marks.get(low, ""))
                at_start = False
                i += 1
                continue

            if ch in self.numbers and self.convert_numbers:
                out.append(self.numbers[ch])
            else:
                out.append(self.punctuation.get(ch, ch))
            i += 1
        return "".join(out)

    # ============================================================== #
    #                     ALPHABET (Russian, Greek)                   #
    # ============================================================== #

    def _convert_alphabet(self, text, final=True):
        out = []
        i, n = 0, len(text)
        while i < n:
            matched = False
            for length in range(min(self._max_token, n - i), 0, -1):
                chunk = text[i:i + length]
                key = chunk.lower()
                if key in self.alphabet:
                    val = self.alphabet[key]
                    rule = self.context_rules.get(key)
                    if rule and out and out[-1][-1:] in rule["after"]:
                        val = rule["value"]
                    if chunk[0].isupper():
                        val = val.upper() if (len(chunk) > 1 and chunk.isupper()) else val[0].upper() + val[1:]
                    out.append(val)
                    i += length
                    matched = True
                    break
            if not matched:
                ch = text[i]
                out.append(self.punctuation.get(ch, ch))
                i += 1
        if final and self.final_forms and out:
            last = out[-1]
            if last and last[-1] in self.final_forms:
                out[-1] = last[:-1] + self.final_forms[last[-1]]
        return "".join(out)


# ------------------------------------------------------------------ #
#                      HELPERS / FACTORIES                            #
# ------------------------------------------------------------------ #

def get_languages_dir():
    """
    Locate the languages directory.
    Search order: $AKSHAR_LANG_DIR, project checkout, /usr/share/akshar,
    /usr/local/share/akshar, ~/.local/share/akshar.
    """
    candidates = [
        os.environ.get("AKSHAR_LANG_DIR", ""),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "languages"),
        "/usr/share/akshar/languages",
        "/usr/local/share/akshar/languages",
        os.path.expanduser("~/.local/share/akshar/languages"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return candidates[1]


def list_available_languages():
    """List every language file: [{file, path, name, code, script, aliases}, ...]."""
    lang_dir = get_languages_dir()
    languages = []
    if os.path.isdir(lang_dir):
        for fname in sorted(os.listdir(lang_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(lang_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                languages.append({
                    "file": fname,
                    "path": fpath,
                    "name": data.get("name", fname),
                    "code": data.get("code", ""),
                    "script": data.get("script", ""),
                    "symbol": data.get("symbol", data.get("code", "")[:2].upper()),
                    "aliases": [a.lower() for a in data.get("aliases", [])],
                })
            except (ValueError, OSError):
                pass
    return languages


def resolve_language(query):
    """
    Map a user-friendly name to a language file name.
    Accepts file name, file stem, language code, display name or any alias
    ('hindi', 'hi', 'ja', 'katakana', 'korean' ...). Returns None if unknown.
    """
    if not query:
        return None
    q = query.strip().lower()
    langs = list_available_languages()
    for lang in langs:                                  # exact file / stem / code / alias
        stem = lang["file"][:-5].lower()
        if q in (lang["file"].lower(), stem, lang["code"].lower()) or q in lang["aliases"]:
            return lang["file"]
    for lang in langs:                                  # display name
        if q == lang["name"].lower():
            return lang["file"]
    for lang in langs:                                  # unique prefix ('jap', 'kat')
        if lang["file"].lower().startswith(q) or any(a.startswith(q) for a in lang["aliases"]):
            return lang["file"]
    return None


def create_engine(language_file):
    """
    Create a TransliterationEngine from an absolute path, a file name in the
    languages/ directory, or any friendly name accepted by resolve_language().
    """
    if os.path.isabs(language_file):
        path = language_file
    else:
        path = os.path.join(get_languages_dir(), language_file)
        if not os.path.exists(path):
            resolved = resolve_language(language_file)
            if resolved:
                path = os.path.join(get_languages_dir(), resolved)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Language file not found: {path}")
    return TransliterationEngine(path)
