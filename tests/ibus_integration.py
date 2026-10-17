#!/usr/bin/env python3
"""
End-to-end check against a REAL ibus-daemon (not part of the pytest run).
    dbus-run-session -- python3 tests/ibus_integration.py
"""
import os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["AKSHAR_CONFIG_DIR"] = "/tmp/akshar-it-config"
import gi
gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus

daemon = subprocess.Popen(["ibus-daemon", "--panel", "disable", "--replace", "--xim"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
engine = subprocess.Popen([sys.executable, os.path.join(ROOT, "engine", "main.py")],
                          env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(2)
ok = False
try:
    IBus.init()
    bus = IBus.Bus()
    assert bus.is_connected(), "not connected to ibus"
    ctx = bus.create_input_context("akshar-it")
    ctx.set_capabilities(IBus.Capabilite.PREEDIT_TEXT | IBus.Capabilite.FOCUS) if hasattr(IBus, "Capabilite") else None
    committed, loop = [], GLib.MainLoop()
    ctx.connect("commit-text", lambda c, t: committed.append(t.get_text()))
    ctx.focus_in()
    ctx.set_engine("akshar-hindi")
    time.sleep(1.5)

    def press(keyval):
        ctx.process_key_event(keyval, 0, 0)
    def pump(sec=0.5):
        end = time.time() + sec
        while time.time() < end:
            GLib.MainContext.default().iteration(False); time.sleep(0.01)

    for ch in "namaste":
        press(ord(ch)); pump(0.15)
    press(IBus.KEY_space); pump(0.8)
    print("committed:", committed)
    ok = any("नमस्ते" in c for c in committed)
finally:
    engine.terminate(); daemon.terminate()
print("INTEGRATION", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
