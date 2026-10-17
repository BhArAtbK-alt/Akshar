#!/usr/bin/env python3
"""Generate akshar.xml (IBus component) with one engine per language file.

    python3 tools/gen_ibus_xml.py [output_path] [exec_path]
"""
import os
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import __version__                      # noqa: E402
from engine.transliterate import list_available_languages   # noqa: E402


def build(exec_path="/usr/share/akshar/engine/main.py"):
    e = escape
    out = ['<?xml version="1.0" encoding="utf-8"?>', "<component>",
           "  <name>org.freedesktop.IBus.Akshar</name>",
           "  <description>Akshar — Universal Real-Time Linguistic Overlay</description>",
           f"  <exec>{e(exec_path)} --ibus</exec>",
           f"  <version>{__version__}</version>",
           "  <author>Bharat</author>", "  <license>MIT</license>",
           "  <homepage>https://github.com/akshar-ime</homepage>",
           "  <textdomain>akshar</textdomain>", "  <engines>"]

    def engine(name, longname, desc, lang, symbol):
        out.extend(["    <engine>", f"      <name>{e(name)}</name>", f"      <language>{e(lang)}</language>",
                    "      <license>MIT</license>", "      <author>Bharat</author>",
                    "      <icon>input-keyboard-symbolic</icon>", "      <layout>us</layout>",
                    f"      <longname>{e(longname)}</longname>", f"      <description>{e(desc)}</description>",
                    "      <rank>99</rank>", f"      <symbol>{e(symbol)}</symbol>", "    </engine>"])

    engine("akshar", "Akshar अक्षर — Transliteration (all languages)",
           "Type English, get any script. F11 switches language.", "hi", "अ")
    for l in list_available_languages():
        engine("akshar-" + l["file"][:-5], f"Akshar अक्षर — {l['name']}",
               f"Type English, get {l['name']}", l["code"].split("-")[0], l["symbol"])
    out.extend(["  </engines>", "</component>", ""])
    return "\n".join(out)


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "akshar.xml")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(build(*sys.argv[2:3]))
    print("wrote", dest)
