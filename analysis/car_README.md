# Car travel-time layer (`car_times.csv`)

## Source
- **Routing engine:** OSRM demo server table service
  (`https://router.project-osrm.org/table/v1/driving/...?sources=0&annotations=duration`),
  car profile on OpenStreetMap data.
- **Retrieved:** 2026-06-12.
- **Origin:** Briggate, Leeds city centre (53.7976, -1.5419).
- **Destinations:** 1,571 LSOA population-weighted centroids from
  `data/population/leeds_lsoa_population.csv`.
- **Method:** destinations batched ~95 per request (origin always index 0),
  ~0.8 s between calls, retries with backoff, custom User-Agent.
  All 1,571 rows returned successfully (0 failures).

## Columns
| column | description |
|---|---|
| `code` | LSOA 2011 code |
| `freeflow_min` | OSRM driving duration / 60, rounded to 0.1 min |

## Important: these are FREE-FLOW times
The OSRM demo server uses static OSM speed limits / defaults with **no traffic
data**. Times represent uncongested driving and include **no parking search,
parking, or walk-from-car time**. They will understate realistic 8am
door-to-door car journeys, especially into the city centre.

## Recommended adjustments for an 8am urban-England comparison (NOT applied here)

1. **Peak congestion multiplier.** The TomTom Traffic Index for Leeds (2025
   data, published Jan 2026) reports a **congestion level of ~34%** (i.e. trips
   take ~34% longer than free-flow on average), average in-city speed of
   ~22.9 km/h, and ~69 hours/year lost per driver at rush hour. Rush-hour
   congestion is higher than the all-day average; a multiplier of
   **~1.4–1.6 on free-flow times** is a reasonable assumption for the 8am peak
   in Leeds (1.34 is the all-day floor). Comparable UK studies (DfT Journey
   Time Statistics; INRIX UK scorecards) support peak/free-flow ratios of
   roughly 1.3–1.7 for major English cities.
   - Sources: [TomTom Traffic Index – Leeds](https://www.tomtom.com/traffic-index/city/leeds),
     [TomTom Traffic Index – UK](https://www.tomtom.com/traffic-index/country/united-kingdom),
     [TomTom Traffic Index 2026 headline numbers](https://www.tomtom.com/newsroom/explainers-and-insights/tomtom-traffic-index-2026-headline-numbers/)

2. **Park-and-walk penalty.** Accessibility literature and UK transport
   appraisal practice typically add a fixed **5–10 minutes** for parking
   search, parking, and walking from the car to the final destination in a
   city centre (e.g. terminal-time assumptions in DfT TAG / WebTAG unit A1.3
   and door-to-door accessibility studies). A central value of **7–8 min** for
   central Leeds is reasonable; suburban destinations warrant less (~2–5 min).

**Suggested adjusted time:** `adjusted_min ≈ freeflow_min × 1.4–1.6 + 5–10`.
These adjustments are documented only; `car_times.csv` contains raw free-flow
values so users can apply their own scenario assumptions.
