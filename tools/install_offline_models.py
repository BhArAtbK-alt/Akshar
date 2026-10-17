#!/usr/bin/env python3
"""
Download offline translation models (Argos Translate) for Akshar's translate mode.

    pip install argostranslate
    python3 tools/install_offline_models.py hi ja ko
"""
import sys


def main(codes):
    try:
        import argostranslate.package as pkg
    except ImportError:
        sys.exit("argostranslate is not installed:  pip install argostranslate")
    pkg.update_package_index()
    available = pkg.get_available_packages()
    for code in codes or ["hi"]:
        match = next((p for p in available if p.from_code == "en" and p.to_code == code), None)
        if not match:
            print(f"  ✗ no en→{code} model published")
            continue
        print(f"  ↓ en→{code} ...")
        pkg.install_from_path(match.download())
        print(f"  ✓ en→{code} installed")


if __name__ == "__main__":
    main(sys.argv[1:])
