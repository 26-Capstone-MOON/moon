# Domain Rules

## Decision Point (DP)
- Types: direction change, crosswalk, vertical move, departure/arrival, virtual (confirmation)
- Extracted from Tmap API by turnType code

### turnType Mapping (API spec)

| turnType | Meaning | DpType Enum |
|---|---|---|
| 12~19 | turn / U-turn | `DIRECTION_CHANGE` |
| 211~217 | crosswalk | `CROSSWALK` |
| 125 | overpass | `VERTICAL_MOVE` |
| 126 | underpass | `VERTICAL_MOVE` |
| 127~129 | stairs | `VERTICAL_MOVE` |
| 218 | elevator | `VERTICAL_MOVE` |
| 200 | origin | `DEPARTURE` |
| 201 | destination | `ARRIVAL` |
| — (null) | inserted on long straight | `VIRTUAL` |

### DP Guidance Patterns

| DpType | Structure | Example |
|---|---|---|
| `DIRECTION_CHANGE` | 3-step: [confirm] → [preview] → [action] | "GS25 on your right? Soon you'll see Olive Young. Turn right at Olive Young." |
| `CROSSWALK` | before-crossing POI + after-crossing POI | "Cross at the crosswalk in front of GS25, go straight toward Olive Young." |
| `VIRTUAL` | current landmark confirmation | "If you see Kookmin Bank on your left, you're on track. Keep going straight." |
| `VERTICAL_MOVE` | fixed instruction + POI location assist | "Past GS25 on your left, stairs right away. Go up the stairs." |

**Direction change 3-step trigger (via WebSocket):**
- GPS approach (30m) → `PRE_ALERT` trigger → preview TTS
- GPS arrival (10m) → `ARRIVAL` trigger → action TTS
- Single DP from Tmap. Do not split into two DPs.

**Vertical move fallback order:**
1. POI available → "Past GS25 on your left, stairs right away."
2. No POI + Vision available → "At the end of the red wall, there are stairs."
3. Neither → "There are stairs ahead. Go up the stairs."

---

## Virtual DP
- Inserted when distance between two consecutive DPs > 200m (threshold)
- Insertion process:
  1. Generate candidate points at 20~50m intervals along the route
  2. POI search + scoring at each candidate
  3. Confirm only top-scoring candidates as Virtual DPs
  4. Enforce minimum 90m spacing between confirmed VDPs
- `dpType: VIRTUAL`, `turnType: null`
- Panorama: 3 directions (front + left + right), same as regular DPs

---

## Landmark
- Selected by Python scoring model: `S_final = (P × h × U) × D`
- Frontend NEVER selects landmarks
- Frontend receives `selectedLandmark` in each DP
- If no landmark → `selectedLandmark: null` → fallback to basic instruction

---

## Scoring Model (Python dp-pipeline)

### Formula
```
S_final =    (P × h × U)  ×   D
           ├─ Intrinsic ─┤   ├ Spatial ┤
```
All parameters are **multiplicative**. No additive components.

### P — Category Recognition (key values)

Kakao `category_group_code` based:

| Code | Category | P value |
|---|---|---|
| MT1 | Large mart | 1.0 |
| PO3 | Public institution | 0.95 |
| BK9 | Bank | 0.9 |
| SC4 | School | 0.85 |
| SW8 | Subway station | 0.8 |
| OL7 | Gas station | 0.75 |
| CS2 | Convenience store | 0.7 |
| CE7 | Cafe | 0.45 |
| FD6 | Restaurant | 0.4 |

Full 18-category table + sub-classification overrides: see `services/dp-pipeline/.claude/rules/scoring.md`.

### h — Business Hours Correction (Google Places API `isOpen()`)
- Open: ×1.0 / Closed: ×0.5 / Unknown: ×0.7

### U — Uniqueness
Same `category_group_code` count within 100m:
- 1 (unique): 1.0 / 2: 0.7 / 3: 0.4 / 4+: 0.2

### D — Distance Fitness
```
D = 1 - d / MD
```
- `d`: straight-line distance from DP to landmark (m)
- `MD`: adaptive search radius from POI collection (30m / 50m / 75m)

### Scoring Example (3pm, search radius 100m)

| Landmark | Intrinsic (P×h×U) | D | S_final |
|---|---|---|---|
| Kookmin Bank (30m, unique, open) | 0.9×1.0×1.0=0.9 | 0.7 | **0.630** |
| GS25 (20m, 1 of 3, open) | 0.7×1.0×0.4=0.28 | 0.8 | **0.224** |
| Private restaurant (50m, unique, closed) | 0.25×0.5×1.0=0.125 | 0.5 | **0.063** |

---

## Sequence Optimization

- **Phase 1 (forward greedy)**: no consecutive same name/category
- **Phase 2 (direction consistency)**: detect left-right-left zigzag → swap within 20% score drop
- O(n×k). Requires full route context.

---

## POI Collection — Adaptive Radius

```
Search at 50m → 0 results: 75m / 20+ results: 30m / 1~19: keep
```

Left/right: bearing-based, recorded in `position` field. Opposite-side NOT filtered.

---

## Panorama + Vision (STEP 4)

- Server generates `panoramaRequest` → client executes Naver Panorama API
- All DPs (including Virtual DP): 3 directions (front + left + right)
- turnType-based isPrimary: left turn→left, right turn→right, other→front
- Vision validation: if turnType facility not visible in primary → distance-based fallback
- Panorama/Vision results are used for guidance text enrichment, NOT for scoring

---

## Off-Route Detection (Python deviation service)

### Detection Flow (every GPS via WebSocket, 1-second interval)

```
[Speed filter]
  Instant speed > 15km/h → GPS error → ignore

[1. Distance threshold]
  Shortest distance to route LineString ≤ 20m → normal → reset timer
  > 20m → deviation suspected

[2. Duration]
  < 3s → ignore / ≥ 3s → warning / ≥ 5s → continuity check

[3. Continuity check] (d1, d2, d3)
  d1 < d2 < d3 → confirmed → reroute
  d1 > d2 > d3 → returning → wait
  Irregular → keep monitoring
```

### Key Thresholds
- **20m**: absorbs GPS error (5~10m) while catching real deviation
- **15km/h**: above pedestrian speed = GPS error
- **3s/5s**: under 3s transient, over 5s intentional

### Distance Calculation
Haversine perpendicular distance to each LineString segment. Take minimum.

### NavigationState Enum

| Value | Meaning |
|---|---|
| `ON_ROUTE` | Normal |
| `DEVIATION_SUSPECTED` | >20m, <3s |
| `DEVIATION_WARNING` | >20m, ≥3s |
| `DEVIATION_CONFIRMED` | ≥5s + distance increasing |
| `RETURNING` | Distance decreasing |
| `REROUTING` | Reroute in progress |
| `ARRIVED` | Destination reached |

### Re-routing
Tmap re-request (current GPS → destination) → re-run STEP 1~5 (reuse cached overlapping data). Response includes `isRerouted: true`, `previousRouteId`.

### Return Detection
Distance decreasing → wait → return within 20m → resume original route.

---

## Fallback Rule
Always have fallback guidance.
- No landmark → distance-based instruction
- No POI + no Vision → "There are stairs ahead."
- Never show empty guidance.