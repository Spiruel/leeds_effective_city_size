# Leeds buried its tram network. It’s been a smaller city ever since

**Leeds’ public transport accessibility to its centre is substantially worse today than in 1957, despite serving a much larger population.**
---

## Methods & Reproduction Guide

All 65 services of the winter 1956/57 Leeds City Transport timetable were transcribed from scans and rebuilt as a GTFS feed (~8,650 weekday departures); the modern comparison is the DfT Bus Open Data Service feed for Tuesday 16 June 2026. 

Both networks were routed identically (RAPTOR, 4.8 km/h walking, 08:00–08:20 departures averaged) against Census 2021 LSOA populations. Both eras use timetabled times — 2026's timetables have congestion baked in. Heavy rail is excluded from both sides; it would help 2026 mainly where stations exist (Cross Gates, Morley, Horsforth), and helps not at all in Middleton, Belle Isle, Harehills or Chapeltown. The 1957 figure ignores everything West Riding, Samuel Ledgard and the railways ran into Leeds, so it is an underestimate.

If you’d like to run the analysis yourself, this repository contains the full start-to-end pipeline. The transcribed data is provided out-of-the-box, but you can also regenerate it using our local OCR setup.

### 1. Set up the environment
Make sure you have Python 3.12+ and `uv` installed.
```bash
uv sync
```

### 2. Transcription (Optional)
The finished timetable JSONs are in `data/transcriptions/` and `data/transcriptions_bus/`. 
To regenerate them from the raw scans (`data/crops/`), we use a state-of-the-art local pipeline (Surya OCR + Gemini):

```bash
# Generate upscaled overlapping bands for OCR
uv run python scripts/prepare_crops.py 

# Run the Surya OCR pipeline
cd scripts/surya_ocr
SURYA_MAX_TOKENS_FULL_PAGE=4096 ./run_gpu.sh "bands:p08,p09,p10,p11,p12,p13,p14"
.venv/bin/python sweep.py bands
cd ../..
```

### 3. Build the Historical GTFS
Compile the transcription JSONs and route geometry (`data/historical/route_geometry.json`) into standard GTFS feeds:

```bash
uv run python scripts/merge_bus_transcriptions.py     # bus pages -> historical/bus_lines.json
uv run python scripts/build_historical_gtfs.py        # trams        -> gtfs_historical/
uv run python scripts/build_full_1957_gtfs.py         # trams+buses  -> gtfs_historical_full/
```

### 4. Run the Analysis
Filter the modern feed and run the RAPTOR routing for both eras:

```bash
# Filter the modern BODS GTFS feed to a 30km radius for a specific day
uv run python scripts/filter_modern_gtfs.py 20260616  

# Run the core routing analysis -> stats.json and isochrones
uv run python scripts/run_analysis.py                 

# Run deeper corridor/suburb breakdowns
uv run python scripts/run_extended_analysis.py        

# Generate all the maps and charts in the analysis/ folder
uv run python scripts/make_figures.py                 
```
