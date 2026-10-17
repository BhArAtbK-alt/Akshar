# Contributing to Akshar (अक्षर)

Thank you! Akshar is an open project. **You do not need to be a programmer** — speaking a language is enough.

## Ways to help (easiest first)

| I can… | Do this |
|---|---|
| Spot a wrong conversion | Open an issue → **Wrong output** |
| Speak a language | Add/fix words in `languages/lexicon/<language>.json` |
| Add a new language | See "Add a language" below |
| Write Python | Pick an issue labelled `good first issue` |
| Test on my distro | Run `./install.sh`, report the result |
| Improve docs | Edit any `.md` file and open a PR |

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/akshar.git && cd akshar
pip install pytest
python -m pytest tests -q          # all tests must pass
python3 engine/cli.py -l hindi -t "namaste"    # try it, no install needed
```

## Add or fix words (no code)

Open `languages/lexicon/hindi.json` (or your language). Format:

```json
{ "words": {
    "dhanyavaad": "धन्यवाद",
    "sakura": ["さくら", "桜"]
}}
```
* Key = what a person types, **lowercase, no spaces**.
* Value = the correct spelling, or a list: `[default, alternate, …]`.
* Only add spellings you are sure about.

## Add a language

1. Copy a similar file in `languages/` (`russian.json` is the simplest; `hindi.json` for Indic scripts).
2. Set `name`, `code`, `script_type` (`abugida`, `syllabary`, `hangul`, `abjad`, `alphabet`), `symbol`, `aliases`.
3. Fill in the letter mappings. Optionally add `languages/lexicon/<name>.json`.
4. If the script mirrors Devanagari's Unicode layout, add a row to `INDIC` in `tools/build_languages.py` instead and run it.
5. Regenerate: `python3 tools/gen_ibus_xml.py`
6. Add a few golden examples to `tests/test_languages.py`, then run the tests.

## Code changes

* Typing behaviour lives in `engine/session.py`; conversion in `engine/transliterate.py`; `engine/main.py` is only an IBus adapter.
* Keep changes small and add a test.
* Generated files (`languages/japanese_*.json`, derived Indic JSONs, `akshar.xml`) come from `tools/` — edit the generator, then rerun it:
  `python3 tools/gen_japanese.py && python3 tools/build_languages.py && python3 tools/gen_ibus_xml.py`
* Optional real-IBus check: `dbus-run-session -- python3 tests/ibus_integration.py`

## Pull requests

1. Fork → branch (`fix-tamil-nandri`) → commit → PR.
2. Tests pass, JSON valid.
3. For language changes, say whether a native speaker checked it.

Be kind — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
