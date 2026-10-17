#!/usr/bin/env python3
"""
Generate japanese_hiragana.json and japanese_katakana.json from ONE master
romaji table, so the two scripts can never drift apart.

Run:  python3 tools/gen_japanese.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "languages")

# romaji -> hiragana (katakana is derived by shifting code points by 0x60)
BASE = {
    # --- vowels & plain rows ---
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "shi": "し", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "ta": "た", "chi": "ち", "ti": "ち", "tsu": "つ", "tu": "つ", "te": "て", "to": "と",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "fu": "ふ", "hu": "ふ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "la": "ら", "li": "り", "lu": "る", "le": "れ", "lo": "ろ",
    "wa": "わ", "wo": "を", "n": "ん",
    # --- voiced ---
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "za": "ざ", "ji": "じ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "di": "ぢ", "du": "づ", "dzi": "ぢ", "dzu": "づ", "de": "で", "do": "ど",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    # --- c as k/s (ca ci cu ce co) ---
    "ca": "か", "ci": "し", "cu": "く", "ce": "せ", "co": "こ",
    # --- contracted sounds (yoon) ---
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "sya": "しゃ", "syu": "しゅ", "syo": "しょ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",
    "zya": "じゃ", "zyu": "じゅ", "zyo": "じょ",
    "dya": "ぢゃ", "dyu": "ぢゅ", "dyo": "ぢょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "fya": "ふゃ", "fyu": "ふゅ", "fyo": "ふょ",
    # --- foreign-sound extensions ---
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "va": "ゔぁ", "vi": "ゔぃ", "vu": "ゔ", "ve": "ゔぇ", "vo": "ゔぉ",
    "she": "しぇ", "che": "ちぇ", "je": "じぇ",
    "tsa": "つぁ", "tsi": "つぃ", "tse": "つぇ", "tso": "つぉ",
    "thi": "てぃ", "thu": "てゅ", "dhi": "でぃ", "dhu": "でゅ",
    "kwa": "くぁ", "kwi": "くぃ", "kwe": "くぇ", "kwo": "くぉ",
    "gwa": "ぐぁ",
    "ye": "いぇ", "wu": "う",
    # --- small kana (x / l prefix) ---
    "xa": "ぁ", "xi": "ぃ", "xu": "ぅ", "xe": "ぇ", "xo": "ぉ",
    "xya": "ゃ", "xyu": "ゅ", "xyo": "ょ", "xwa": "ゎ",
    "xtu": "っ", "xtsu": "っ", "ltu": "っ", "ltsu": "っ",
    "lya": "ゃ", "lyu": "ゅ", "lyo": "ょ",
}

# Differences from the base table, per script
HIRAGANA_OVERRIDES = {
    "wi": "うぃ", "we": "うぇ",
    "di": "ぢ", "du": "づ",
}
KATAKANA_OVERRIDES = {
    # Loan-word friendly sounds (パーティー, ディスコ, ウィンドウ ...)
    "ti": "てぃ", "tu": "とぅ", "di": "でぃ", "du": "どぅ",
    "wi": "うぃ", "we": "うぇ", "wo": "を",
}

PUNCT = {
    ",": "、", ".": "。", "!": "！", "?": "？", "(": "（", ")": "）",
    "[": "「", "]": "」", "~": "〜", "-": "ー", ":": "：",
}


def to_katakana(s: str) -> str:
    out = []
    for ch in s:
        cp = ord(ch)
        if 0x3041 <= cp <= 0x3096:
            out.append(chr(cp + 0x60))
        else:
            out.append(ch)
    return "".join(out)


def build(script: str) -> dict:
    kana = dict(BASE)
    kana.update(HIRAGANA_OVERRIDES if script == "hiragana" else KATAKANA_OVERRIDES)
    # katakana wo/wi/we in modern usage; keep ヲ for 'wo'
    if script == "katakana":
        kana = {k: to_katakana(v) for k, v in kana.items()}
        kana["wo"] = "ヲ"
        kana["n"] = "ン"
    else:
        kana["n"] = "ん"
    is_kata = script == "katakana"
    return {
        "name": "Japanese (Katakana)" if is_kata else "Japanese (Hiragana)",
        "code": "ja-kata" if is_kata else "ja",
        "script": "Katakana" if is_kata else "Hiragana",
        "script_type": "syllabary",
        "symbol": "ア" if is_kata else "あ",
        "aliases": (["katakana", "kata", "ja-kata", "jakata"] if is_kata
                    else ["japanese", "hiragana", "hira", "ja", "jp"]),
        "small_tsu": "ッ" if is_kata else "っ",
        # 'mark' => a repeated vowel becomes ー (raamen -> ラーメン)
        "long_vowel_style": "mark" if is_kata else "none",
        "long_vowel_mark": "ー",
        "alt_candidates": ["japanese_hiragana.json" if is_kata else "japanese_katakana.json"],
        "kana": kana,
        "punctuation": {k: v for k, v in PUNCT.items()},
    }


if __name__ == "__main__":
    for script, fname in (("hiragana", "japanese_hiragana.json"), ("katakana", "japanese_katakana.json")):
        data = build(script)
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {fname}: {len(data['kana'])} kana entries")
