#!/usr/bin/env python3
"""
Build the additional language maps shipped with Akshar.

 * Indic scripts that mirror Devanagari's Unicode layout (Marathi, Bengali,
   Gujarati, Punjabi/Gurmukhi, Odia, Telugu, Kannada, Malayalam) are DERIVED
   from languages/hindi.json by shifting code points.  Every derived character
   is validated against the Unicode database; anything unassigned is dropped
   (never emitted as garbage).
 * Tamil, Korean, Arabic, Urdu, Russian and Greek are hand-written below.

Run:  python3 tools/build_languages.py
"""
import copy
import json
import os
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(os.path.dirname(HERE), "languages")


SYMBOLS = {"hi": "अ", "mr": "अ", "bn": "অ", "gu": "અ", "pa": "ਅ", "or": "ଅ", "te": "అ",
           "kn": "ಅ", "ml": "അ", "ta": "அ", "ja": "あ", "ja-kata": "ア", "ko": "한",
           "ar": "ع", "ur": "ا", "ru": "Я", "el": "Ω"}


def load(name):
    with open(os.path.join(LANG_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    data.setdefault("symbol", SYMBOLS.get(data["code"], data["code"].upper()))
    with open(os.path.join(LANG_DIR, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    n = sum(len(v) for v in data.values() if isinstance(v, dict))
    print(f"  wrote {name:28s} ({n} mappings)")


# ---------------------------------------------------------------------- #
#  Derived Indic scripts
# ---------------------------------------------------------------------- #

def shift(s, delta):
    """Shift a Devanagari string into another Indic block. None if any char is unassigned."""
    out = []
    for ch in unicodedata.normalize("NFD", s):
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            new = chr(cp + delta)
            if unicodedata.name(new, None) is None:
                return None
            out.append(new)
        else:
            out.append(ch)
    return "".join(out)


INDIC = {
    # file stem: (name, code, script, block base, aliases, keep danda?, south-style vowels?)
    "marathi":   ("Marathi",   "mr", "Devanagari", 0x0900, ["marathi", "mr"], False, False),
    "bengali":   ("Bengali",   "bn", "Bengali",    0x0980, ["bengali", "bangla", "bn"], True, False),
    "gujarati":  ("Gujarati",  "gu", "Gujarati",   0x0A80, ["gujarati", "gu"], False, False),
    "punjabi":   ("Punjabi",   "pa", "Gurmukhi",   0x0A00, ["punjabi", "gurmukhi", "pa"], True, False),
    "odia":      ("Odia",      "or", "Odia",       0x0B00, ["odia", "oriya", "or"], True, False),
    "telugu":    ("Telugu",    "te", "Telugu",     0x0C00, ["telugu", "te"], False, True),
    "kannada":   ("Kannada",   "kn", "Kannada",    0x0C80, ["kannada", "kn"], False, True),
    "malayalam": ("Malayalam", "ml", "Malayalam",  0x0D00, ["malayalam", "ml"], False, True),
}

# letters Devanagari has no equivalent for in a given script
EXTRA_CONSONANTS = {
    "bengali": {"v": "ব", "w": "ব"},          # Bengali has no separate 'va'
    "malayalam": {"zh": "\u0D34"},            # ഴ
}


def derive_indic(stem, spec, hindi):
    name, code, script, base, aliases, keep_danda, south = spec
    delta = base - 0x0900
    out = {
        "name": name, "code": code, "script": script, "script_type": "abugida",
        "aliases": aliases, "smart_capitalize": True,
        "separator": "_", "halant_key": "^",
    }
    for section in ("consonants", "conjuncts", "modifiers", "numbers"):
        out[section] = {}
        for k, v in hindi[section].items():
            sv = shift(v, delta)
            if sv:
                out[section][k] = sv
    out["halant"] = shift(hindi["halant"], delta)

    out["vowels_independent"], out["vowels_matra"] = {}, {}
    for k, v in hindi["vowels_independent"].items():
        ind = shift(v, delta)
        mat = shift(hindi["vowels_matra"][k], delta) if k in hindi["vowels_matra"] else None
        if ind and (mat is not None):          # keep only complete pairs
            out["vowels_independent"][k] = ind
            out["vowels_matra"][k] = mat

    if south:
        # Baraha-style: e/o are SHORT, E/O are LONG (these scripts distinguish them)
        pairs = {"e": (0x090E, 0x0946), "E": (0x090F, 0x0947),
                 "o": (0x0912, 0x094A), "O": (0x0913, 0x094B)}
        for k, (ind_cp, mat_cp) in pairs.items():
            out["vowels_independent"][k] = chr(ind_cp + delta)
            out["vowels_matra"][k] = chr(mat_cp + delta)

    for k, v in EXTRA_CONSONANTS.get(stem, {}).items():
        out["consonants"][k] = v

    out["specials"] = {}
    if keep_danda:
        out["specials"] = {".": "।", "..": "॥"}
    out["variants"] = copy.deepcopy(hindi["variants"])
    return out


# ---------------------------------------------------------------------- #
#  Tamil (hand-written: no aspirates, short/long e & o, pulli at word end)
# ---------------------------------------------------------------------- #

def tamil():
    cons = {
        "k": "க", "kh": "க", "g": "க", "gh": "க",
        "ng": "ங", "ch": "ச", "c": "ச", "chh": "ச", "s": "ச", "j": "ஜ", "jh": "ஜ",
        "ny": "ஞ", "T": "ட", "Th": "ட", "D": "ட", "Dh": "ட",
        "N": "ண", "t": "த", "th": "த", "d": "த", "dh": "த",
        "n": "ந", "w": "ன", "p": "ப", "ph": "ப", "f": "ப", "b": "ப", "bh": "ப",
        "m": "ம", "y": "ய", "r": "ர", "R": "ற", "l": "ல", "L": "ள",
        "zh": "ழ", "z": "ழ", "v": "வ",
        "S": "ஸ", "sh": "ஷ", "Sh": "ஷ", "h": "ஹ", "q": "ஃ",
    }
    conj = {"ksh": "க்ஷ", "x": "க்ஷ"}
    vi = {"a": "அ", "aa": "ஆ", "A": "ஆ", "i": "இ", "ii": "ஈ", "ee": "ஈ", "I": "ஈ",
          "u": "உ", "uu": "ஊ", "oo": "ஊ", "U": "ஊ",
          "e": "எ", "E": "ஏ", "ai": "ஐ", "o": "ஒ", "O": "ஓ", "au": "ஔ"}
    vm = {"a": "", "aa": "ா", "A": "ா", "i": "ி", "ii": "ீ", "ee": "ீ", "I": "ீ",
          "u": "ு", "uu": "ூ", "oo": "ூ", "U": "ூ",
          "e": "ெ", "E": "ே", "ai": "ை", "o": "ொ", "O": "ோ", "au": "ௌ"}
    nums = {str(i): chr(0x0BE6 + i) for i in range(10)}
    return {
        "name": "Tamil", "code": "ta", "script": "Tamil", "script_type": "abugida",
        "aliases": ["tamil", "ta"], "smart_capitalize": True,
        "separator": "_", "halant_key": "^",
        # Tamil words do not end in a bare consonant: it takes a pulli (்)
        "final_halant": True,
        "consonants": cons, "conjuncts": conj,
        "vowels_independent": vi, "vowels_matra": vm,
        "modifiers": {"M": "ஂ"}, "halant": "்", "specials": {}, "numbers": nums,
        "variants": [["ee", "i"], ["oo", "u"], ["n", "N"], ["n", "w"], ["t", "T"],
                     ["l", "L"], ["r", "R"], ["i$", "ee"], ["a$", "aa"]],
    }


# ---------------------------------------------------------------------- #
#  Korean (Hangul syllables composed algorithmically from Revised Romanization)
# ---------------------------------------------------------------------- #

def korean():
    return {
        "name": "Korean", "code": "ko", "script": "Hangul", "script_type": "hangul",
        "aliases": ["korean", "ko", "hangul", "hangeul", "kr"],
        "punctuation": {"?": "?", ".": ".", ",": ","},
        "variants": [["k", "g"], ["g", "k"], ["t", "d"], ["d", "t"], ["p", "b"], ["b", "p"],
                     ["eo", "o"], ["o", "eo"], ["ae", "e"], ["e", "ae"], ["eu", "u"], ["l", "r"]],
    }


# ---------------------------------------------------------------------- #
#  Arabic & Urdu (abjad: short vowels are normally not written)
# ---------------------------------------------------------------------- #

def arabic():
    return {
        "name": "Arabic", "code": "ar", "script": "Arabic", "script_type": "abjad",
        "aliases": ["arabic", "ar"],
        "smart_capitalize": False,         # capitals are meaningful here (H, S, D, T, Z)
        "consonants": {
            "b": "ب", "t": "ت", "th": "ث", "j": "ج", "H": "ح", "kh": "خ", "d": "د",
            "dh": "ذ", "r": "ر", "z": "ز", "s": "س", "sh": "ش", "S": "ص", "D": "ض",
            "T": "ط", "Z": "ظ", "E": "ع", "gh": "غ", "f": "ف", "q": "ق", "k": "ك",
            "l": "ل", "m": "م", "n": "ن", "h": "ه", "w": "و", "y": "ي",
            "'": "ء", "p": "ب", "v": "ف", "g": "ج", "c": "ك", "x": "كس",
        },
        "long_vowels": {"aa": "ا", "ee": "ي", "ii": "ي", "uu": "و", "oo": "و",
                        "ay": "ي", "ai": "ي", "aw": "و", "au": "و"},
        "initial_vowels": {"a": "أ", "i": "إ", "u": "أ", "e": "إ", "o": "أ"},
        "final_vowels": {"a": "ا", "i": "ي", "u": "و", "e": "ي", "o": "و"},
        "short_vowel_marks": {"a": "َ", "i": "ِ", "u": "ُ", "e": "ِ", "o": "ُ"},
        # Arabic chat alphabet: digits inside a word stand for letters
        "digit_letters": {"2": "ء", "3": "ع", "5": "خ", "6": "ط", "7": "ح", "8": "غ", "9": "ق"},
        "numbers": {str(i): chr(0x0660 + i) for i in range(10)},
        "punctuation": {",": "،", ";": "؛", "?": "؟"},
        "variants": [["a$", "aa"], ["aa", "a"], ["h", "H"], ["s", "S"], ["t", "T"], ["d", "D"], ["z", "Z"]],
    }


def urdu():
    return {
        "name": "Urdu", "code": "ur", "script": "Arabic (Urdu)", "script_type": "abjad",
        "aliases": ["urdu", "ur"],
        "smart_capitalize": False,
        "consonants": {
            "b": "ب", "bh": "بھ", "p": "پ", "ph": "پھ", "t": "ت", "th": "تھ",
            "T": "ٹ", "Th": "ٹھ", "s": "س", "j": "ج", "jh": "جھ", "ch": "چ", "chh": "چھ",
            "H": "ح", "kh": "خ", "d": "د", "dh": "دھ", "D": "ڈ", "Dh": "ڈھ", "z": "ز",
            "r": "ر", "R": "ڑ", "Rh": "ڑھ", "zh": "ژ", "sh": "ش", "S": "ص", "Z": "ض",
            "gh": "غ", "f": "ف", "q": "ق", "k": "ک", "kk": "کھ", "g": "گ", "gg": "گھ",
            "l": "ل", "m": "م", "n": "ن", "N": "ں", "v": "و", "w": "و", "h": "ہ",
            "y": "ی", "'": "ع", "E": "ع",
        },
        "long_vowels": {"aa": "ا", "ee": "ی", "ii": "ی", "uu": "و", "oo": "و",
                        "ay": "ے", "ai": "ے", "au": "او", "aw": "او"},
        "initial_vowels": {"a": "ا", "i": "ا", "u": "ا", "e": "ا", "o": "ا"},
        "final_vowels": {"a": "ا", "i": "ی", "u": "و", "e": "ے", "o": "و"},
        "short_vowel_marks": {"a": "َ", "i": "ِ", "u": "ُ", "e": "ِ", "o": "ُ"},
        "digit_letters": {},
        "numbers": {str(i): chr(0x06F0 + i) for i in range(10)},
        "punctuation": {",": "،", ";": "؛", "?": "؟", ".": "۔"},
        "variants": [["a$", "aa"], ["ee", "i"], ["oo", "u"], ["t", "T"], ["d", "D"], ["h", "H"]],
    }


# ---------------------------------------------------------------------- #
#  Alphabets: Russian, Greek
# ---------------------------------------------------------------------- #

def russian():
    m = {
        "a": "а", "b": "б", "v": "в", "w": "в", "g": "г", "d": "д", "e": "е", "yo": "ё",
        "zh": "ж", "z": "з", "i": "и", "j": "й", "k": "к", "l": "л", "m": "м", "n": "н",
        "o": "о", "p": "п", "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "kh": "х",
        "h": "х", "ts": "ц", "c": "ц", "ch": "ч", "sh": "ш", "shch": "щ", "sch": "щ",
        "y": "ы", "eh": "э", "yu": "ю", "ya": "я", "ye": "е", "x": "кс", "q": "к",
        "'": "ь", "''": "ъ",
    }
    return {
        "name": "Russian", "code": "ru", "script": "Cyrillic", "script_type": "alphabet",
        "aliases": ["russian", "ru", "cyrillic"],
        "alphabet": m,
        # 'y' after a vowel letter is the glide й (moy -> мой), otherwise ы (mysl -> мысль)
        "context_rules": {"y": {"after": "аеёиоуыэюя", "value": "й"}},
        "variants": [["e", "eh"], ["y", "j"], ["ch", "c"]],
    }


def greek():
    m = {
        "a": "α", "b": "β", "v": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η",
        "ee": "η", "th": "θ", "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "x": "ξ",
        "ks": "ξ", "o": "ο", "p": "π", "r": "ρ", "s": "σ", "t": "τ", "y": "υ", "u": "υ",
        "f": "φ", "ph": "φ", "ch": "χ", "ps": "ψ", "w": "ω", "ou": "ου", "c": "κ", "j": "τζ",
        # tonos: vowel + apostrophe
        "a'": "ά", "e'": "έ", "h'": "ή", "i'": "ί", "o'": "ό", "y'": "ύ", "w'": "ώ",
        "ee'": "ή", "ou'": "ού",
    }
    return {
        "name": "Greek", "code": "el", "script": "Greek", "script_type": "alphabet",
        "aliases": ["greek", "el", "gr"],
        "alphabet": m,
        "final_forms": {"σ": "ς"},
        "variants": [["e", "h"], ["h", "ee"], ["o", "w"], ["w", "o"], ["u", "y"]],
    }


def main():
    hindi = load("hindi.json")
    print("Deriving Indic scripts from hindi.json")
    for stem, spec in INDIC.items():
        save(f"{stem}.json", derive_indic(stem, spec, hindi))
    print("Writing hand-built languages")
    for stem, fn in (("tamil", tamil), ("korean", korean), ("arabic", arabic),
                     ("urdu", urdu), ("russian", russian), ("greek", greek)):
        save(f"{stem}.json", fn())


if __name__ == "__main__":
    main()
