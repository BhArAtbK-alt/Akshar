"""
Akshar — Semantic Translation Engine (meaning -> meaning, not sounds)

Backends
  online   Google Translate's public endpoint (needs internet; text you type
           in translation mode is sent to Google — see README "Privacy")
  offline  Argos Translate (pip install argostranslate + language packs;
           see tools/install_offline_models.py).  Fully local.

The router adds
  * a thread-safe LRU cache (instant repeats, no repeated network calls)
  * a back-off after a network failure, so typing never stalls on a dead link
  * translate_async() so a GUI/IME main loop is never blocked
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

logger = logging.getLogger("akshar")

# Akshar language code -> translation-service code
LANG_MAP = {
    "hi": "hi", "mr": "mr", "bn": "bn", "gu": "gu", "pa": "pa", "or": "or",
    "te": "te", "kn": "kn", "ml": "ml", "ta": "ta",
    "ja": "ja", "ja-kata": "ja", "ko": "ko",
    "ar": "ar", "ur": "ur", "ru": "ru", "el": "el",
}

MAX_CHARS = 1500            # keeps the GET URL well inside server limits
BACKOFF_SECONDS = 30        # skip the online backend this long after a failure


class TranslationEngine:
    def __init__(self, target_lang_code="hi", backend="auto", timeout=4.0, cache_size=512):
        """
        target_lang_code : Akshar language code ('hi', 'ja', 'ko', ...)
        backend          : auto (online, then offline) | online | offline | offline_first
        """
        self.source_lang = "en"
        self.target_lang = LANG_MAP.get(target_lang_code, target_lang_code or "hi")
        self.backend = backend
        self.timeout = timeout
        self.lang_map = LANG_MAP

        self._cache = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self._online_down_until = 0.0
        self._argos_cache = {}

    # ------------------------------------------------------------ #
    def set_target_language(self, akshar_lang_code):
        self.target_lang = LANG_MAP.get(akshar_lang_code, "hi")

    def supports(self, akshar_lang_code):
        return akshar_lang_code in LANG_MAP

    # ------------------------------------------------------------ #
    #                         cache                                 #
    # ------------------------------------------------------------ #
    def _cache_get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def _cache_put(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    # ------------------------------------------------------------ #
    #                         online                                #
    # ------------------------------------------------------------ #
    def translate_online(self, text):
        """Google Translate: 'how are you' -> 'आप कैसे हैं'. None on failure."""
        if not text or not text.strip():
            return text
        if time.monotonic() < self._online_down_until:
            return None

        url = ("https://translate.googleapis.com/translate_a/single?client=gtx"
               f"&sl={self.source_lang}&tl={self.target_lang}&dt=t&q="
               + urllib.parse.quote(text[:MAX_CHARS]))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
            return translated or None
        except (urllib.error.URLError, OSError, ValueError, IndexError, TypeError) as e:
            logger.error("Online translation failed: %s", e)
            self._online_down_until = time.monotonic() + BACKOFF_SECONDS
            return None

    # ------------------------------------------------------------ #
    #                         offline                               #
    # ------------------------------------------------------------ #
    def _argos_translation(self):
        """The installed Argos en->target translator, or None."""
        key = (self.source_lang, self.target_lang)
        if key in self._argos_cache:
            return self._argos_cache[key]
        result = None
        try:
            import argostranslate.translate as at          # optional dependency
            langs = at.get_installed_languages()
            src = next((l for l in langs if l.code == self.source_lang), None)
            dst = next((l for l in langs if l.code == self.target_lang), None)
            if src and dst:
                result = src.get_translation(dst)
        except Exception as e:                             # ImportError or model problems
            logger.debug("Argos unavailable: %s", e)
        self._argos_cache[key] = result
        return result

    def offline_available(self):
        return self._argos_translation() is not None

    def translate_offline(self, text):
        """Argos Translate (local neural MT). None if not installed / no model."""
        if not text or not text.strip():
            return text
        tr = self._argos_translation()
        if tr is None:
            return None
        try:
            return tr.translate(text) or None
        except Exception as e:
            logger.error("Offline translation failed: %s", e)
            return None

    # ------------------------------------------------------------ #
    #                         router                                #
    # ------------------------------------------------------------ #
    def translate(self, text, mode=None):
        """
        Translate English `text` into the target language. Returns None when
        every allowed backend failed (callers fall back to transliteration).
        `mode` overrides the configured backend: online | offline | auto | offline_first.
        """
        if not text or not text.strip():
            return text
        mode = mode or self.backend
        key = (self.target_lang, text)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        order = {
            "online": ("online",),
            "offline": ("offline",),
            "offline_first": ("offline", "online"),
        }.get(mode, ("online", "offline"))

        for name in order:
            result = self.translate_online(text) if name == "online" else self.translate_offline(text)
            if result:
                self._cache_put(key, result)
                return result
        return None

    def translate_async(self, text, callback, mode=None):
        """Translate in a worker thread; callback(result_or_None) runs on that thread."""
        def work():
            try:
                result = self.translate(text, mode)
            except Exception as e:                         # never let a worker die silently
                logger.error("translate_async crashed: %s", e)
                result = None
            callback(result)
        t = threading.Thread(target=work, name="akshar-translate", daemon=True)
        t.start()
        return t
