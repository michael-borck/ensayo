#!/usr/bin/env python3
"""WCAG contrast check for theme palettes (no deps).

Reads each themes/*/src/styles/theme.css, extracts the key colour variables, and
reports the contrast ratio for body text / muted text against backgrounds. Exits
non-zero if any normal-text pair is below the AA 4.5:1 threshold.

Run from the repo root:  python3 scripts/a11y/contrast.py
"""
import glob
import pathlib
import re
import sys

AA_NORMAL = 4.5


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    chans = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    fails = checked = 0
    for css in sorted(glob.glob("themes/*/src/styles/theme.css")):
        txt = pathlib.Path(css).read_text(encoding="utf-8")
        v = {}
        for name in ["bg", "surface", "text", "muted"]:
            m = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", txt)
            if m:
                v[name] = m.group(1)
        theme = css.split("/")[1]
        for fg, bg, label in [("text", "bg", "body text"),
                              ("muted", "bg", "muted on bg"),
                              ("muted", "surface", "muted on surface")]:
            if fg in v and bg in v:
                checked += 1
                r = ratio(v[fg], v[bg])
                ok = r >= AA_NORMAL
                fails += not ok
                print(f"  [{'ok ' if ok else 'FAIL'}] {theme:20} {label:18} {r:5.2f}:1")
    print(f"\n{checked} pairs checked, {fails} below {AA_NORMAL}:1 (AA normal text)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
