#!/usr/bin/env python3
"""Merge per-page bus transcriptions into per-line records.

Joint services ("42 & 66") are normalised to one line; service 46's two route
variants (Belle Isle / Middleton) become separate lines; the unnumbered
Whitkirk shuttle and night buses are kept but flagged for exclusion from the
daytime analysis. Output: data/historical/bus_lines.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from leeds_trams import DATA

KEY_NORMALISE = {
    "50 & 51": "50/51", "74, 75 and 76": "74/75/76", "8, 52 & 53": "8/52/53",
    "42 & 66": "42/66",
}


def line_key(service: dict) -> str | None:
    num = str(service.get("service_number"))
    num = KEY_NORMALISE.get(num, num)
    if num in ("None", "none", ""):
        return None  # unnumbered Whitkirk-Crossgates shuttle: excluded
    if num == "NIGHT":
        return None  # night network: not part of the 08:00 daytime analysis
    if num == "46":  # two route variants under one number
        return "46M" if "MIDDLETON" in service["route_name"].upper() else "46"
    return num.replace(" ", "")


def main():
    pages = {f.stem: json.loads(f.read_text())
             for f in sorted((DATA / "transcriptions_bus").glob("*.json"))}

    lines: dict[str, dict] = {}
    conflicts = []
    for pkey, page in sorted(pages.items()):
        for s in page.get("services", []):
            k = line_key(s)
            if k is None:
                continue
            line = lines.setdefault(k, {
                "line_id": "B" + re.sub(r"[^0-9A-Za-z]", "_", k),
                "service_number": k,
                "route_names": [],
                "source_pages": [],
                "day_tables": [],
                "headnotes": [],
            })
            if s["route_name"] not in line["route_names"]:
                line["route_names"].append(s["route_name"])
            line["source_pages"].append(pkey)
            line["headnotes"] += s.get("headnotes", [])
            for dt in s["day_tables"]:
                for d in dt["directions"]:
                    existing = [
                        (i, x) for i, x in enumerate(line["day_tables"])
                        if x["day_type"] == dt["day_type"]
                        and x["direction"]["stops"][0]["name"].lower()
                        == d["stops"][0]["name"].lower()
                        and x["direction"]["stops"][-1]["name"].lower()
                        == d["stops"][-1]["name"].lower()
                    ]
                    rec = {"day_type": dt["day_type"], "direction": d, "page": pkey}
                    if existing:
                        i, x = existing[0]
                        # keep the richer transcription
                        if len(d["service_pattern"]) > len(x["direction"]["service_pattern"]):
                            line["day_tables"][i] = rec
                        conflicts.append(f"{k}: duplicate {dt['day_type']} "
                                         f"{d['stops'][0]['name']}->{d['stops'][-1]['name']} "
                                         f"on {pkey} and {x['page']}")
                    else:
                        line["day_tables"].append(rec)

    weekday_ok, weekday_missing = [], []
    for k, line in sorted(lines.items()):
        wk = [t for t in line["day_tables"]
              if t["day_type"] in ("monday_to_friday", "monday_to_saturday", "daily")]
        (weekday_ok if len(wk) >= 1 else weekday_missing).append(k)
        line["weekday_directions"] = len(wk)

    out = {"lines": sorted(lines.values(), key=lambda x: x["line_id"]),
           "conflicts": conflicts,
           "weekday_missing": weekday_missing}
    (DATA / "historical" / "bus_lines.json").write_text(json.dumps(out, indent=1))
    print(f"{len(lines)} lines; weekday tables present for {len(weekday_ok)}, "
          f"missing for {weekday_missing}; {len(conflicts)} merge conflicts")
    for c in conflicts:
        print(" conflict:", c)
    for line in out["lines"]:
        dirs = ", ".join(sorted({t["day_type"][:3] for t in line["day_tables"]}))
        print(f"  {line['line_id']:8s} {line['route_names'][0][:52]:52s} [{dirs}] "
              f"wk_dirs={line['weekday_directions']}")


if __name__ == "__main__":
    main()
