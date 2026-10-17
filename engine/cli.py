#!/usr/bin/env python3
"""
Akshar — अक्षर — command-line tool

  akshar-cli                          interactive (Hindi)
  akshar-cli -l japanese              interactive, another language
  akshar-cli -t "namaste duniya"      convert one string
  akshar-cli -l ja -t konnichiwa -c   show alternate candidates (kanji, katakana...)
  echo "namaste" | akshar-cli         convert piped text, line by line
  akshar-cli --list                   list languages
  akshar-cli -t "how are you" --translate -l hi    meaning, not sounds
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    import readline
except ImportError:          # e.g. Windows
    readline = None

from engine import __version__
from engine.config import Config, config_dir
from engine.transliterate import create_engine, list_available_languages, resolve_language
from engine.translate import TranslationEngine
from engine.userdict import UserDict

CYAN, GREEN, YELLOW, RED = "\033[0;36m", "\033[0;32m", "\033[1;33m", "\033[0;31m"
BOLD, DIM, NC = "\033[1m", "\033[2m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    CYAN = GREEN = YELLOW = RED = BOLD = DIM = NC = ""


def banner():
    print(f"\n{CYAN}  अक्षर — Akshar {__version__}{NC}   {DIM}Universal Real-Time Linguistic Overlay{NC}")


def help_text():
    print(f"""
  {BOLD}Commands{NC}
    {CYAN}/lang <name>{NC}     switch language (hindi, tamil, japanese, katakana, korean ...)
    {CYAN}/mode{NC}            transliteration (sounds)  <->  translation (meaning)
    {CYAN}/cand on|off{NC}     show alternate candidates for each word
    {CYAN}/complete <p>{NC}    lexicon completions for a prefix
    {CYAN}/list{NC}            available languages
    {CYAN}/quit{NC}            exit

  {BOLD}Tips{NC}  long vowels: aa ee oo  ·  Hindi: M=ं  _=separator  ^=halant  ·  Capitals: T D N = retroflex
""")


def do_translate(text, code, backend):
    tr = TranslationEngine(code, backend=backend)
    return tr.translate(text)


def show_languages():
    for l in list_available_languages():
        print(f"  {l['symbol']:<3} {l['name']:<22} {l['code']:<8} {l['file'][:-5]}")


def convert_line(engine, line, cands, as_json):
    result = engine.transliterate(line)
    if as_json:
        row = {"input": line, "output": result}
        if cands:
            row["candidates"] = {w: engine.candidates(w) for w in line.split()}
        return json.dumps(row, ensure_ascii=False)
    if not cands:
        return result
    return result + "".join(f"\n  {DIM}{w}:{NC} " + "  |  ".join(engine.candidates(w))
                            for w in line.split())


def interactive(engine, backend):
    mode, cands = "transliterate", True
    ud = UserDict()
    hist = os.path.join(config_dir(), "cli_history")
    if readline:
        try:
            readline.read_history_file(hist)
        except OSError:
            pass
    print(f"  {GREEN}✓{NC} {BOLD}{engine.name}{NC}   {DIM}/help for commands{NC}\n")
    while True:
        try:
            line = input(f"  {CYAN}EN ▸{NC} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            parts = line.split()
            cmd = parts[0].lower()
            if cmd in ("/quit", "/exit", "/q"):
                break
            elif cmd == "/help":
                help_text()
            elif cmd == "/list":
                show_languages()
            elif cmd == "/mode":
                mode = "translate" if mode == "transliterate" else "transliterate"
                print(f"  {YELLOW}✦ {mode}{NC}\n")
            elif cmd == "/cand":
                cands = not (len(parts) > 1 and parts[1].lower() == "off")
                print(f"  candidates {'on' if cands else 'off'}\n")
            elif cmd == "/complete" and len(parts) > 1:
                for roman, native in engine.completions(parts[1], 8) + ud.suggest(engine.stem, parts[1], 5):
                    print(f"    {roman:<18} {native}")
                print()
            elif cmd == "/lang" and len(parts) > 1:
                f = resolve_language(parts[1])
                if f:
                    engine = create_engine(f)
                    print(f"  {GREEN}✓{NC} {BOLD}{engine.name}{NC}\n")
                else:
                    print(f"  {RED}✗{NC} unknown language (try /list)\n")
            else:
                print(f"  {RED}✗{NC} unknown command (/help)\n")
            continue

        if mode == "translate":
            out = do_translate(line, engine.code, backend)
            if out:
                print(f"  {GREEN}⇒{NC}  {BOLD}{out}{NC}\n")
            else:
                print(f"  {RED}✗{NC} translation failed (offline?) — phonetic: {engine.transliterate(line)}\n")
        else:
            print(f"  {GREEN}⇒{NC}  {BOLD}{convert_line(engine, line, cands, False)}{NC}\n")
            for w in line.split():
                first = engine.candidates(w, limit=1)
                if first:
                    ud.record(engine.stem, w, first[0])
    ud.flush()
    if readline:
        try:
            os.makedirs(os.path.dirname(hist), exist_ok=True)
            readline.write_history_file(hist)
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="akshar-cli", description="Akshar transliteration/translation tool")
    ap.add_argument("--lang", "-l", default=Config().default_language[:-5], help="language (default: %(default)s)")
    ap.add_argument("--text", "-t", help="convert this string and exit")
    ap.add_argument("--list", action="store_true", help="list languages and exit")
    ap.add_argument("--candidates", "-c", action="store_true", help="also print alternate candidates")
    ap.add_argument("--translate", action="store_true", help="translate meaning instead of transliterating")
    ap.add_argument("--backend", default="auto", choices=["auto", "online", "offline", "offline_first"])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--version", action="version", version=f"akshar {__version__}")
    args = ap.parse_args(argv)

    if args.list:
        show_languages()
        return 0

    file = resolve_language(args.lang)
    if not file:
        print(f"unknown language '{args.lang}'. Use --list.", file=sys.stderr)
        return 2
    engine = create_engine(file)

    def run(text):
        if args.translate:
            out = do_translate(text, engine.code, args.backend)
            return out if out is not None else engine.transliterate(text)
        return convert_line(engine, text, args.candidates, args.json)

    if args.text is not None:
        print(run(args.text))
        return 0
    if not sys.stdin.isatty():                          # piped input
        for line in sys.stdin:
            line = line.rstrip("\n")
            print(run(line) if line else "")
        return 0
    banner()
    interactive(engine, args.backend)
    return 0


if __name__ == "__main__":
    sys.exit(main())
