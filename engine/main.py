#!/usr/bin/env python3
"""
Akshar — अक्षर — IBus engine (thin adapter around engine.session.Session)

IBus launches this with `--ibus`. Run without it for standalone debugging
(registers the component itself). All typing logic lives in session.py.
"""

import logging
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import gi
gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus

from engine import __version__
from engine.config import Config, config_dir
from engine.session import Key, Session
from engine.transliterate import list_available_languages, resolve_language

LOG_DIR = os.path.join(config_dir(), "logs")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(LOG_DIR, "akshar.log"),
        level=logging.DEBUG if os.environ.get("AKSHAR_DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
except OSError:
    logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("akshar")

BUS_NAME = "org.freedesktop.IBus.Akshar"
_ALIASES = {"kp_enter": "return", "iso_left_tab": "tab", "prior": "pageup", "next": "pagedown"}


# ------------------------------------------------------------------ #
#                          ADAPTERS                                   #
# ------------------------------------------------------------------ #

class GLibScheduler:
    """Timers and main-thread marshalling on the GLib main loop."""
    supports_timers = True

    def call_later(self, ms, fn):
        def run():
            try:
                fn()
            except Exception:
                logger.exception("scheduled call failed")
            return False
        return GLib.timeout_add(max(1, int(ms)), run)

    def cancel(self, handle):
        if handle:
            try:
                GLib.source_remove(handle)
            except Exception:
                pass

    def call_main(self, fn):
        def run():
            try:
                fn()
            except Exception:
                logger.exception("main-thread call failed")
            return False
        GLib.idle_add(run)


def key_from_ibus(keyval, state):
    """Translate an IBus key event into the abstract Key the Session understands."""
    name = (IBus.keyval_name(keyval) or "").lower()
    name = _ALIASES.get(name, name)
    char = ""
    if 0xFFB0 <= keyval <= 0xFFB9:                       # keypad digits
        char = chr(48 + keyval - 0xFFB0)
    elif 32 <= keyval <= 126:
        char = chr(keyval)
    if char == " ":
        name = "space"
    elif char:
        name = char.lower()
    return Key(
        name=name, char=char,
        shift=bool(state & IBus.ModifierType.SHIFT_MASK),
        ctrl=bool(state & IBus.ModifierType.CONTROL_MASK),
        alt=bool(state & IBus.ModifierType.MOD1_MASK),
        meta=bool(state & (IBus.ModifierType.SUPER_MASK | IBus.ModifierType.META_MASK
                           | IBus.ModifierType.MOD4_MASK)),
    )


# ------------------------------------------------------------------ #
#                          THE ENGINE                                 #
# ------------------------------------------------------------------ #

class AksharEngine(IBus.Engine):
    __gtype_name__ = "AksharEngine"

    def __init__(self, bus, object_path, engine_name="akshar"):
        super().__init__(connection=bus.get_connection(), object_path=object_path,
                         engine_name=engine_name)
        self._init_session(engine_name)

    def _init_session(self, engine_name):
        language = None
        if engine_name.startswith("akshar-"):               # per-language engines
            language = resolve_language(engine_name[len("akshar-"):])
        self.session = Session(config=Config(), scheduler=GLibScheduler(),
                               language=language, on_update=self._render)
        self._register_properties()
        logger.info("Engine '%s' ready (%s)", engine_name, self.session.language_name)

    # ---------------- rendering ---------------- #
    def _render(self):
        s = self.session
        try:
            pre = s.preedit
            if pre and s.config.get("show_preedit", True):
                text = IBus.Text.new_from_string(pre)
                text.append_attribute(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, len(pre))
                self.update_preedit_text_with_mode(text, len(pre), True, IBus.PreeditFocusMode.COMMIT)
            else:
                self.hide_preedit_text()

            if s.lookup_visible:
                n = s.page_size
                table = IBus.LookupTable.new(n, s.cursor, True, True)
                for c in s.candidate_texts:
                    table.append_candidate(IBus.Text.new_from_string(c))
                for i in range(n):
                    table.append_label(IBus.Text.new_from_string(f"^{i + 1}"))
                self.update_lookup_table(table, True)
            else:
                self.hide_lookup_table()

            if s.aux:
                self.update_auxiliary_text(IBus.Text.new_from_string(s.aux), True)
            else:
                self.hide_auxiliary_text()
        except Exception:
            logger.exception("render failed")

    def _commit(self, strings):
        if strings:
            combined = "".join(strings)
            if combined:
                self.commit_text(IBus.Text.new_from_string(combined))

    # ---------------- panel menu ---------------- #
    def _register_properties(self):
        try:
            s = self.session
            def text(t):
                return IBus.Text.new_from_string(t)
            subs = IBus.PropList()
            for lang in s.languages:
                subs.append(IBus.Property(
                    key=f"lang:{lang['file']}", prop_type=IBus.PropType.RADIO,
                    label=text(lang["name"]), icon="", tooltip=text(lang["name"]),
                    sensitive=True, visible=True,
                    state=IBus.PropState.CHECKED if lang["file"] == s.engine.file else IBus.PropState.UNCHECKED,
                    sub_props=None))
            props = IBus.PropList()
            props.append(IBus.Property(
                key="menu-lang", prop_type=IBus.PropType.MENU, label=text(s.status_text), icon="",
                tooltip=text("Akshar language"), sensitive=True, visible=True,
                state=IBus.PropState.UNCHECKED, sub_props=subs))
            props.append(IBus.Property(
                key="mode", prop_type=IBus.PropType.TOGGLE, label=text("Translate meaning (online/offline)"),
                icon="", tooltip=text("Translate instead of transliterate"), sensitive=True, visible=True,
                state=IBus.PropState.CHECKED if s.mode == "translate" else IBus.PropState.UNCHECKED,
                sub_props=None))
            self.register_properties(props)
        except Exception:
            logger.exception("could not register panel properties (non-fatal)")

    def do_property_activate(self, prop_name, state):
        s = self.session
        if prop_name.startswith("lang:"):
            self._commit(s.commit_pending())
            s.set_language(prop_name[5:])
        elif prop_name == "mode":
            self._commit(s.commit_pending())
            s.toggle_mode()
        self._register_properties()
        self._render()

    # ---------------- IBus virtuals ---------------- #
    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        try:
            result = self.session.process_key(key_from_ibus(keyval, state))
        except Exception:
            logger.exception("key handling failed")
            return False
        self._commit(result.commits)
        self._render()
        return result.handled

    def do_candidate_clicked(self, index, button, state):
        s = self.session
        s.cursor = (s.cursor // s.page_size) * s.page_size + index
        self._commit(s.commit_pending())
        self._render()

    def do_cursor_down(self):
        self.session._move(1); self._render()

    def do_cursor_up(self):
        self.session._move(-1); self._render()

    def do_page_down(self):
        self.session._move(self.session.page_size); self._render()

    def do_page_up(self):
        self.session._move(-self.session.page_size); self._render()

    def do_focus_in(self):
        self._register_properties()

    def do_focus_out(self):
        self._commit(self.session.commit_pending())
        self._render()
        self.session.shutdown()

    def do_reset(self):
        self.session.discard()
        self._render()

    def do_enable(self):
        logger.info("enabled")

    def do_disable(self):
        self._commit(self.session.commit_pending())
        self.session.shutdown()


class AksharEngineFactory(IBus.Factory):
    def __init__(self, bus):
        self._bus = bus
        self._counter = 0
        super().__init__(object_path=IBus.PATH_FACTORY, connection=bus.get_connection())

    def do_create_engine(self, engine_name):
        self._counter += 1
        path = f"/org/freedesktop/IBus/Engine/{self._counter}"
        logger.info("create engine %s at %s", engine_name, path)
        return AksharEngine(self._bus, path, engine_name)


# ------------------------------------------------------------------ #
#                               MAIN                                  #
# ------------------------------------------------------------------ #

def build_component():
    comp = IBus.Component.new(BUS_NAME, "Akshar — Universal Transliteration", __version__,
                              "MIT", "Bharat", "https://github.com/akshar-ime", "", "akshar")
    comp.add_engine(IBus.EngineDesc.new(
        "akshar", "Akshar अक्षर — Transliteration (all languages)",
        "Type English, get any script. F11 switches language.", "hi", "MIT", "Bharat",
        "input-keyboard-symbolic", "us"))
    for lang in list_available_languages():
        stem = lang["file"][:-5]
        desc = IBus.EngineDesc(
            name=f"akshar-{stem}", longname=f"Akshar अक्षर — {lang['name']}",
            description=f"Type English, get {lang['name']}", language=lang["code"].split("-")[0],
            license="MIT", author="Bharat", icon="input-keyboard-symbolic", layout="us",
            symbol=lang["symbol"])
        comp.add_engine(desc)
    return comp


def main():
    if "--version" in sys.argv:
        print(f"akshar {__version__}")
        return
    exec_by_ibus = "--ibus" in sys.argv

    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("ERROR: cannot connect to IBus. Try: ibus-daemon -drx", file=sys.stderr)
        sys.exit(1)

    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda b: loop.quit())
    factory = AksharEngineFactory(bus)          # noqa: F841  (must stay alive)

    if exec_by_ibus:
        bus.request_name(BUS_NAME, 0)
    else:
        bus.register_component(build_component())
        print("Akshar registered (standalone). Add it under Settings → Keyboard → Input Sources.")

    logger.info("Akshar %s running", __version__)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
