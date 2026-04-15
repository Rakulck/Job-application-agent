#!/usr/bin/env python3
"""
Run this ONCE before using the carousel generator.
Downloads Bebas Neue, Anton, and Oswald from Google Fonts into ./fonts/

Usage:
    python3 setup_fonts.py
"""

import os, sys, urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).parent / "fonts"
FONTS_DIR.mkdir(exist_ok=True)

FONTS = {
    "BebasNeue-Regular.ttf":  "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
    "Anton-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    "Oswald-Bold.ttf":        "https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Bold.ttf",
    "Oswald-Regular.ttf":     "https://github.com/google/fonts/raw/main/ofl/oswald/static/Oswald-Regular.ttf",
    "Montserrat-Bold.ttf":    "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf",
    "Montserrat-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Regular.ttf",
}

print("📦 Downloading fonts...\n")
ok = 0
for name, url in FONTS.items():
    dest = FONTS_DIR / name
    if dest.exists():
        print(f"  ✅ {name} (already downloaded)")
        ok += 1
        continue
    try:
        print(f"  ⬇️  {name}...", end=" ", flush=True)
        urllib.request.urlretrieve(url, dest)
        print(f"✅  ({dest.stat().st_size // 1024}kb)")
        ok += 1
    except Exception as e:
        print(f"❌  {e}")

print(f"\n{'🎉 All fonts ready!' if ok == len(FONTS) else f'⚠️  {ok}/{len(FONTS)} fonts downloaded'}")
print(f"Saved to: {FONTS_DIR}\n")
