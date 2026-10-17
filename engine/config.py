"""
Akshar — Configuration Manager
User preferences live in ~/.config/akshar/config.json
(override the directory with $AKSHAR_CONFIG_DIR — handy for tests).
"""

import json
import os
import tempfile

DEFAULT_CONFIG = {
    # --- languages ---
    "default_language": "hindi.json",
    "cycle_languages": [],             # files F11 cycles through; [] = all of them

    # --- hotkeys (modifier+key, e.g. "F12", "ctrl+F12", "ctrl+shift+space") ---
    "toggle_key": "F12",               # transliteration ON / OFF
    "switch_language_key": "F11",      # cycle through languages
    "mode_key": "F10",                 # transliterate <-> translate (meaning)

    # --- typing behaviour ---
    "convert_numbers": False,          # 123 -> १२३ (Hindi) etc.
    "smart_capitalize": True,          # "Namaste" at sentence start behaves like "namaste"
    "show_preedit": True,
    "show_diacritics": False,          # Arabic/Urdu: write short-vowel marks

    # --- candidates & completion ---
    "show_candidates": True,           # lookup table with alternates
    "candidate_page_size": 6,
    "max_candidates": 12,
    "completion": True,                # suggest longer words from the lexicon / your history
    "completion_min_chars": 2,

    # --- learning ---
    "learn": True,                     # remember your candidate choices (local file only)

    # --- translation mode (meaning, not sounds) ---
    "translation_backend": "auto",     # auto | online | offline | offline_first
    "translation_debounce_ms": 600,
    "translation_timeout": 4.0,

    "auto_start": False,
    "theme": "dark",
}

# expected types, used to reject corrupt values from a hand-edited file
_TYPES = {k: type(v) for k, v in DEFAULT_CONFIG.items()}
_TYPES["translation_timeout"] = (int, float)


def config_dir():
    return os.environ.get("AKSHAR_CONFIG_DIR") or os.path.expanduser("~/.config/akshar")


def config_file():
    return os.path.join(config_dir(), "config.json")


# Kept for backward compatibility with code that imports these names
CONFIG_DIR = config_dir()
CONFIG_FILE = config_file()


class Config:
    """Manages Akshar user configuration."""

    def __init__(self):
        self._config = dict(DEFAULT_CONFIG)
        self.load()

    # ---------------------------------------------------------------- #
    def load(self):
        """Load from disk; create defaults on first run; recover from corruption."""
        path = config_file()
        if not os.path.exists(path):
            self.save()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError("config root must be an object")
        except (ValueError, OSError):
            # keep the broken file for inspection, then reset
            try:
                os.replace(path, path + ".broken")
            except OSError:
                pass
            self.save()
            return
        for key, value in saved.items():
            expected = _TYPES.get(key)
            if expected is None or isinstance(value, expected):
                if expected is int and isinstance(value, bool):
                    continue
                self._config[key] = value

    def save(self):
        """Atomically persist the current configuration."""
        d = config_dir()
        try:
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".config.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, config_file())
        except OSError:
            pass  # read-only home etc. — keep running with in-memory settings

    # ---------------------------------------------------------------- #
    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def __getitem__(self, key):
        return self._config[key]

    def to_dict(self):
        return dict(self._config)

    # --- convenience properties (backward compatible) ---
    @property
    def default_language(self):
        return self._config["default_language"]

    @default_language.setter
    def default_language(self, value):
        self.set("default_language", value)

    @property
    def toggle_key(self):
        return self._config["toggle_key"]

    @property
    def switch_language_key(self):
        return self._config["switch_language_key"]

    @property
    def mode_key(self):
        return self._config["mode_key"]

    @property
    def convert_numbers(self):
        return self._config["convert_numbers"]

    @property
    def show_preedit(self):
        return self._config["show_preedit"]
