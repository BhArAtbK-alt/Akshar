# Changelog

## 2.0.0
### Fixed (bugs in 1.0)
- IBus engine was created without a bus connection, so it could never register → fixed; verified against a real `ibus-daemon`.
- `akshar.xml` used `<n>` instead of `<name>` and lacked `--ibus`; it is now generated (one engine per language).
- Hindi: `ny`→ञ broke *dhanyavaad*; `ri`→ऋ broke *priya/hari/krishna*; `om`→ॐ broke *somvar*; `ng`/`ld` broke *sangeet*; capital first letter produced retroflex ण.
- Japanese: *konnichiwa* → こんいちわ; *matcha* → まtちゃ; katakana had no ー; trailing `n` resolved too early in live preview.
- README advertised `--text` / `--list` that the CLI never implemented; config hotkeys were ignored; `translate_offline` was a TODO; `setup.py` shipped no language files; wrong test expectation (`hindi`).

### Added
- 12 new languages (Marathi, Bengali, Gujarati, Punjabi, Odia, Telugu, Kannada, Malayalam, Tamil, Korean, Arabic, Urdu, Russian, Greek) via 4 new script engines.
- Lexicons with alternates (kanji, katakana); candidate list; completion; personal learning dictionary.
- Translate mode in the IME (debounced, async, cached, offline via Argos, phonetic fallback).
- Session state machine (testable without IBus), panel menu, configurable hotkeys.
- Full CLI (`--text`, `--list`, stdin, `--json`, `--candidates`, `--translate`).
- 225 tests, real-IBus integration test, CI workflow.
