#!/usr/bin/env python3
"""Split the scanned timetable book pages into upscaled crop bands for
vision transcription. (The scans are two book pages stacked per PNG.)"""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from leeds_trams import DATA, PROJECT_ROOT

SCALE = 3
BAND_H = 170   # px in the original scan
OVERLAP = 40

# Tram pages of the book (pages >=16 are bus services, catalogued separately)
PAGES = {
    "p08": ("page 08-09.png", "top"), "p09": ("page 08-09.png", "bottom"),
    "p10": ("page 10-11.png", "top"), "p11": ("page 10-11.png", "bottom"),
    "p12": ("page 12-13.png", "top"), "p13": ("page 12-13.png", "bottom"),
    "p14": ("page 14.png", "full"),
}


def main():
    src = DATA / "timetables_input"
    out = DATA / "crops"
    out.mkdir(parents=True, exist_ok=True)
    for key, (fname, part) in PAGES.items():
        im = Image.open(src / fname)
        w, h = im.size
        if part == "top":
            im = im.crop((0, 0, w, h // 2))
        elif part == "bottom":
            im = im.crop((0, h // 2, w, h))
        w, h = im.size
        im.resize((w * 2, h * 2), Image.LANCZOS).save(out / f"{key}_full.png")
        y = i = 0
        while y < h:
            band = im.crop((0, y, w, min(h, y + BAND_H)))
            if band.height > 25:
                band.resize((band.width * SCALE, band.height * SCALE),
                            Image.LANCZOS).save(out / f"{key}_band{i}.png")
            y += BAND_H - OVERLAP
            i += 1
        print(f"{key}: {fname} ({part}) -> {i} bands")


if __name__ == "__main__":
    main()
