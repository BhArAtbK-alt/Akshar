"""
Akshar — Personal dictionary (learning)

Remembers which candidate you pick for a given romanised word, so your
favourite spelling floats to the top next time, and your own words show up
as completions.  Stored ONLY on your machine: ~/.config/akshar/userdict.json
"""

import json
import os
import tempfile
import threading

from engine.config import config_dir


class UserDict:
    FLUSH_EVERY = 10          # write to disk after this many new records

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "userdict.json")
        self._data = {}       # {lang: {roman: {native: count}}}
        self._dirty = 0
        self._lock = threading.Lock()
        self.load()

    # ------------------------------------------------------------ #
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._data = {l: w for l, w in data.items() if isinstance(w, dict)}
        except (OSError, ValueError):
            self._data = {}

    def flush(self):
        with self._lock:
            if not self._dirty:
                return
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix=".ud.", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
                self._dirty = 0
            except OSError:
                pass

    # ------------------------------------------------------------ #
    def record(self, lang, roman, native):
        """Note that, for `roman`, the user chose `native`."""
        if not roman or not native or roman == native:
            return
        with self._lock:
            words = self._data.setdefault(lang, {}).setdefault(roman, {})
            words[native] = words.get(native, 0) + 1
            self._dirty += 1
            should_flush = self._dirty >= self.FLUSH_EVERY
        if should_flush:
            self.flush()

    def best(self, lang, roman):
        """Chosen outputs for `roman`, most-used first."""
        words = self._data.get(lang, {}).get(roman, {})
        return [w for w, _ in sorted(words.items(), key=lambda kv: -kv[1])]

    def suggest(self, lang, prefix, limit=5):
        """[(roman, native), ...] for learned words starting with `prefix` (not equal to it)."""
        rows = []
        for roman, words in self._data.get(lang, {}).items():
            if roman != prefix and roman.startswith(prefix):
                native, count = max(words.items(), key=lambda kv: kv[1])
                rows.append((count, roman, native))
        rows.sort(key=lambda r: (-r[0], len(r[1]), r[1]))
        return [(r[1], r[2]) for r in rows[:limit]]

    def count(self, lang=None):
        if lang:
            return len(self._data.get(lang, {}))
        return sum(len(w) for w in self._data.values())

    def clear(self, lang=None):
        with self._lock:
            if lang:
                self._data.pop(lang, None)
            else:
                self._data = {}
            self._dirty += 1
        self.flush()
