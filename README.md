# अक्षर — Akshar

### Universal Real-Time Linguistic Overlay

> Type in English on any QWERTY keyboard → get **Hindi, Tamil, Japanese, Korean, Arabic, Russian…** — **in every app on your device.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux-orange.svg)]()
[![IBus](https://img.shields.io/badge/Framework-IBus-green.svg)]()

```
namaste        →  नमस्ते          konnichiwa  →  こんにちは
thamizh        →  தமிழ்            annyeonghaseyo → 안녕하세요
raamen (カタカナ) →  ラーメン          privet      →  привет
```

---

## Features

|                             |                                                                                                                                                           |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **17 languages**            | Hindi, Marathi, Bengali, Gujarati, Punjabi, Odia, Telugu, Kannada, Malayalam, Tamil, Japanese (Hiragana + Katakana), Korean, Arabic, Urdu, Russian, Greek |
| **Smart candidates**        | Press `Tab` to cycle alternates: `hindi` → हिन्दी · हिंदी · …; `sakura` → さくら · 桜 · サクラ                                                            |
| **Completion**              | Start a word → suggestions from the built-in lexicon _and your own history_                                                                               |
| **Learns you**              | Your chosen spelling floats to the top next time (stored locally only)                                                                                    |
| **Translate mode**          | `F10` switches from _sounds_ to _meaning_: type `how are you` → आप कैसे हैं — online or fully offline                                                     |
| **Live preview**            | Underlined preview while you type; commit with Space/Enter                                                                                                |
| **Smart typing**            | `Namaste` at sentence start works (no accidental ण); `\word` types raw English                                                                            |
| **System-wide**             | A real IBus input method — browsers, editors, terminals, chat apps                                                                                        |
| **One engine per language** | Add _Akshar — Tamil_ etc. in system settings, or use the all-in-one engine + `F11`                                                                        |
| **Panel menu**              | Switch language/mode from the IBus panel                                                                                                                  |
| **Offline**                 | Transliteration needs no internet, ever                                                                                                                   |

---

## Install

```bash
git clone https://github.com/YOUR_USERNAME/akshar.git
cd akshar && chmod +x install.sh && ./install.sh
```

Then **Settings → Keyboard (Region & Language) → Input Sources → + → search "Akshar"**, add your language(s), and switch with **Super+Space**.

Requirements: `ibus`, Python ≥ 3.8, `python3-gi` + `gir1.2-ibus-1.0` (the installer fetches them on apt/dnf/pacman).

---

## Keys

| Key                            | Action                                          |
| ------------------------------ | ----------------------------------------------- |
| `Space`                        | commit the highlighted candidate + a space      |
| `Enter`                        | commit (Enter then passes through to the app)   |
| `Tab` / `Shift+Tab`, `↓` / `↑` | next / previous candidate                       |
| `Ctrl+1 … 9`                   | pick that candidate on the current page         |
| `Esc` / `Backspace`            | cancel word / delete last letter                |
| `F12`                          | transliteration ON / OFF                        |
| `F11`                          | next language (restrict with `cycle_languages`) |
| `F10`                          | transliterate ⇄ translate                       |
| `\hello`                       | type `hello` untouched                          |

All hotkeys are configurable (`"ctrl+shift+space"`, `"F9"` …) in `~/.config/akshar/config.json`.
_(F12 opens dev-tools in some browsers — remap `toggle_key` if that bites.)_

---

## Typing guide

**Indic scripts** (Hindi, Marathi, Bengali, Gujarati, Punjabi, Odia, Telugu, Kannada, Malayalam, Tamil)

- A consonant carries an inherent _a_: `ka` → क. Long vowels are doubled: `aa ee oo` → आ ई ऊ.
- `M` anusvara ं · `H` visarga ः · `~` chandrabindu ँ
- Capitals are retroflex: `T D N` → ट ड ण. _(Only a single leading capital is treated as a sentence capital.)_
- `_` is a separator (`a_i` → अइ, not ऐ) · `^` forces a halant (`k^` → क्)
- South Indian scripts: `e o` are **short**, `E O` are **long**.
- Wrong spelling? **Tab** — alternates (long/short vowels, anusvara, retroflex) are offered automatically.

**Japanese** — `ou`→おう · `nn` or `n'` → ん · `kk`→っ · Katakana mode writes long vowels with ー (`raamen` → ラーメン, `-` also works) · small kana via `xa`, `xtu`, `xya`…

**Korean** — Revised Romanization: `annyeonghaseyo`, `hangeul`, `bibimbap`. Syllables are composed automatically.

**Arabic / Urdu** — short vowels are omitted like in real writing (`kitab` → كتب, `kitaab` → كتاب); chat digits work inside words (`3arabi` → عربي, `mar7aba` → مرحبا). Capitals pick emphatic letters (`S T D Z H`).

**Russian / Greek** — `zh sh ch shch ya yu`; `y` after a vowel is й (`moy` → мой); Greek tonos via apostrophe (`a'` → ά), final ς automatic.

---

## Translate mode (meaning, not sounds)

Press `F10`, type a whole phrase (spaces stay in the phrase), pause — the translation appears in the candidate list; `Enter` inserts it. If translation is unavailable you automatically get the phonetic spelling.

- **Online** uses Google's public endpoint → **the text you type in translate mode is sent to Google.** Transliteration mode never touches the network.
- **Offline**: `pip install argostranslate && python3 tools/install_offline_models.py hi ja` then set `"translation_backend": "offline"` (or `"offline_first"`).

---

## CLI

```bash
akshar-cli                                  # interactive
akshar-cli -l tamil -t "vanakkam"           # one string
akshar-cli -l ja -t "konnichiwa" -c         # with alternates (kanji, katakana…)
echo "namaste bharat" | akshar-cli -l hindi # pipe
akshar-cli -t "how are you" --translate -l hi
akshar-cli --list                           # all languages  ·  --json for machine output
```

## Configuration — `~/.config/akshar/config.json`

`default_language` · `cycle_languages` · `toggle_key` / `switch_language_key` / `mode_key` · `convert_numbers` · `smart_capitalize` · `show_candidates` · `candidate_page_size` · `completion` · `learn` · `translation_backend` · `translation_debounce_ms` · `show_diacritics` (Arabic/Urdu). Your learned words: `~/.config/akshar/userdict.json` (delete it any time).

---

## Architecture

```
engine/
  transliterate.py  5 script engines (abugida · syllabary · hangul · abjad · alphabet),
                    lexicon, candidates, completions            ← pure Python, no deps
  session.py        input state machine: buffer · candidates · hotkeys · learning · translation
  main.py           thin IBus adapter around Session (GLib timers, panel menu)
  translate.py      online/offline translation, cache, back-off, async
  userdict.py       local learning store          config.py   validated settings
  cli.py            terminal tool
languages/          *.json maps  +  lexicon/*.json (exact words, kanji, alternates)
tools/              generators: gen_japanese · build_languages · gen_ibus_xml · install_offline_models
tests/              225 tests  +  ibus_integration.py (drives a real ibus-daemon)
```

## Adding / improving a language

1. **Indic script with a Devanagari-like layout** → add a row to `INDIC` in `tools/build_languages.py`; run it.
2. **Anything else** → create `languages/xx.json` (see `russian.json` for the simplest `alphabet` type, `hindi.json` for `abugida`). Required: `name`, `code`, `script_type`. Optional: `aliases`, `symbol`, `variants` (regex spelling alternates), `smart_capitalize`.
3. **Better words** → add exact spellings (and alternates) to `languages/lexicon/xx.json`. Value = string, or list `[default, alt, alt…]`.
4. `python3 tools/gen_ibus_xml.py` then `pytest tests`.

## Tests

```bash
pip install pytest && python -m pytest tests -q              # 225 tests
dbus-run-session -- python3 tests/ibus_integration.py        # real IBus end-to-end
```

## Known limits (honest list)

- Linux/IBus only (Fcitx5, Windows, macOS: not yet).
- Phonetic input can't know every word: that's what candidates, the lexicon and learning are for. Lexicons are starter-size (Hindi ≈170 words, Japanese ≈95 with kanji); contributions welcome.
- Tamil, Korean, Arabic and Urdu schemes are solid but simple — native speakers' corrections are the most valuable contribution.
- Japanese has no full kana→kanji conversion beyond the lexicon candidates.

## Uninstall

```bash
./uninstall.sh
```

## 🤝 Contribute — anyone can help!

Akshar is an open, community project. **You don't need to be a programmer** — speaking a language is enough.

| I can…                  | Do this                                                  |
| ----------------------- | -------------------------------------------------------- |
| Find a wrong conversion | Open an issue → _Wrong output_                           |
| Speak a language        | Fix/add words in `languages/lexicon/<language>.json`     |
| Add a new language      | Copy `languages/russian.json`, edit, open a PR           |
| Write Python            | Pick a `good first issue` (see [ROADMAP.md](ROADMAP.md)) |
| Test on my distro       | Run `./install.sh` and report                            |

Start here: [CONTRIBUTING.md](CONTRIBUTING.md) · [ROADMAP.md](ROADMAP.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SECURITY.md](SECURITY.md)

---

## License

MIT — see [LICENSE](LICENSE).

<p align="center"><b>अक्षर</b> — Every keyboard speaks every language.</p>
