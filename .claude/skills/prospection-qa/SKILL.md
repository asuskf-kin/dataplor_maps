---
name: prospection-qa
description: |
  QA skill for prospection/matching algorithm output. Takes two files — client_base (known client outlets) and prospection_output (algorithm results with match/no_match labels) — and produces interactive HTML maps, a mistakes report, category analysis Excel files, and a full HTML QA report.

  Use this skill whenever the user wants to: visualize client base vs prospection output on a map; find false negatives (no_match outlets that exist in client_base); debug or improve a matching algorithm; analyze match/no_match breakdown by business category; flag non-beverage categories; compare match rate against Coca-Cola market penetration benchmarks; or produce a full QA report.

  Trigger on: "plot my prospection results", "check mistakes in no_match", "map client base vs prospection", "find false negatives", "visualize outlet match results", "compare my client base and prospection output", "QA my prospection algorithm", "which no_match outlets are actually in my client base"
---

# Prospection QA Skill

You are helping the user audit the output of a prospection/matching algorithm. You'll receive two files and produce interactive HTML maps, category analysis Excel files, a market benchmark comparison, and a full QA report.

## Shortcut — pipeline code (saves tokens)

If the repo has `src/qa.py`, run `python src/qa.py <pais>/<region>` instead of re-implementing Steps
1–5 and 7–9. Name matching ignores case and accents. Then do Step 6 (web search), save it as
`benchmark.json` and re-run with `--benchmark`.

## What you're working with

**client_base**: A file (xlsx or csv) containing all outlets the client is actively working with. Columns include outlet name, latitude, longitude, address, and an ID.

**prospection_output**: A file (xlsx or csv) of prospected outlets, each labeled as `match` or `no_match` by an algorithm. Contains the same fields as client_base plus a `match_no_match` column.

---

## Step 1: Install dependencies and load the files

```bash
pip install folium rapidfuzz geopy openpyxl xlsxwriter --break-system-packages -q
```

> **Important — TF-IDF corpus**: After loading both files, immediately build an IDF (inverse document frequency) dictionary from ALL outlet names across both files. Each name is one "document". Tokenize by splitting on non-alphanumeric characters and lowercasing. Compute `idf[token] = log(N / (1 + df))` where `N` = total names and `df` = how many names contain that token. This corpus is used in Step 3 to down-weight ubiquitous tokens like "shop", "store", "general", "pan" during name matching.

Load both files with pandas. Auto-detect the format from file extension (.xlsx → `pd.read_excel`, .csv → `pd.read_csv`). After loading, print column names and 3 sample rows from each to understand the schema.

**Auto-detect these columns** (ask the user if genuinely ambiguous):

| Field | Look for (case-insensitive) |
|---|---|
| latitude | lat, latitude, y, lat_wgs84 |
| longitude | lon, lng, longitude, x, lon_wgs84 |
| name | name, outlet_name, nom, store_name, shop_name, label, enseigne |
| id | id, outlet_id, code, ref, key, identifiant — pick the most specific/unique one |
| match_no_match | match_no_match, match, status, verdict, result (prospection_output only) |
| business_category | category, business_category, type, business_type, secteur, categorie, trade_channel, channel, sous_type, enseigne_type, segment |

Normalize the `match_no_match` column: lowercase and strip whitespace, then map variants (`"1"` → `"match"`, `"0"` → `"no_match"`, `"yes"` → `"match"`, etc.) to a clean `"match"` / `"no_match"`.

**If no `match_no_match` column exists**, look for a `total_score` column (or similar: `score`, `similarity_score`, `confidence`). If found, ask the user:

> "I didn't find a match/no_match column. I found a `total_score` column — what threshold should I use? Rows with `total_score >= threshold` will be treated as **match**, and below as **no_match**."

Wait for the user's answer, then derive the `match_no_match` column from the threshold before continuing. If neither column exists, ask the user to clarify how matches are indicated in their file.

**Business category**: If a `business_category` column is found in either file, note it. Store both as `cat_prospection` (from prospection_output) and `cat_client` (from client_base). If only one file has it, note which.

---

## Step 2: Build Map 1 — Full overview

Use Folium to build an interactive Leaflet map with **three layers**:

- 🔴 **Red markers** (`CircleMarker`, radius=7): All outlets from client_base
- 🔵 **Blue markers** (`CircleMarker`, radius=7): Outlets from prospection_output where `match_no_match == "match"`
- 🟢 **Green markers** (`CircleMarker`, radius=7): Outlets from prospection_output where `match_no_match == "no_match"`

Each marker popup should show:
- Outlet name and ID
- Address (if available)
- Business category (if available)
- Source file and match status

Add a `folium.LayerControl` so the user can toggle each group. Center the map on the overall data centroid. Always render individual `CircleMarker` points — do not use `MarkerCluster`.

---

## Step 3: Detect mistakes (false negatives)

A **mistake** is a prospection_output point labeled as `no_match` that actually corresponds to an outlet in client_base — meaning the algorithm incorrectly rejected it.

Detection uses a **combined score** that weighs both geographic proximity and name similarity together. Neither signal alone is reliable enough: a close outlet with a completely different name might be a different business entirely, while a very similar name far away might just be a chain. The combined score rewards pairs that are strong on both dimensions.

### Computing the combined score

For each `no_match` point, compare it against every outlet in client_base and compute a combined score for each candidate pair:

**1. Distance score** (`geo_score`): Use `geopy.distance.geodesic` to compute the distance in meters. Convert to a 0–1 score that decays linearly to 0 at **300 meters**:
```python
geo_score = max(0.0, 1.0 - distance_m / 300)
```

**2. Name score** (`name_score`): Use a **hybrid score** that blends fuzzy string matching with TF-IDF cosine similarity. This is critical because outlet names in many markets share extremely common business-type words ("General Store", "Pan Shop", "Kiryana Store"). Plain fuzzy matching gives high scores to outlets that share only these generic words but have completely different proper names — producing many false positives. The TF-IDF component automatically down-weights these ubiquitous tokens and emphasizes the distinctive parts of a name (the owner's name, a neighborhood reference, etc.).

```python
# Component 1: Fuzzy score (handles typos, abbreviations, word reordering)
fuzzy_score = token_sort_ratio(name_a, name_b) / 100

# Component 2: TF-IDF cosine similarity (emphasizes distinctive tokens)
# Tokenize both names, build TF vectors, weight by IDF from the corpus built in Step 1,
# then compute cosine similarity between the two TF-IDF vectors.
def tfidf_cosine(name_a, name_b, idf_dict):
    tokens_a = tokenize(name_a)  # re.findall(r'[a-z0-9]+', name.lower())
    tokens_b = tokenize(name_b)
    if not tokens_a or not tokens_b:
        return 0.0
    tf_a, tf_b = Counter(tokens_a), Counter(tokens_b)
    dot = norm_a = norm_b = 0.0
    for t in set(tokens_a) | set(tokens_b):
        w = idf_dict.get(t, 1.0)
        va, vb = tf_a.get(t, 0) * w, tf_b.get(t, 0) * w
        dot += va * vb
        norm_a += va * va
        norm_b += vb * vb
    return dot / (sqrt(norm_a) * sqrt(norm_b)) if norm_a > 0 and norm_b > 0 else 0.0

tfidf_score = tfidf_cosine(name_a, name_b, idf)

# Hybrid: 50/50 blend
name_score = 0.5 * fuzzy_score + 0.5 * tfidf_score
```

Why 50/50: fuzzy matching is essential for catching spelling variants and abbreviations (e.g. "IMRAN" vs "NEW IMRAN"), while TF-IDF is essential for preventing false matches on generic words alone. Neither is sufficient on its own.

**3. Combined score**: Weighted average giving slightly more weight to name, since names are a stronger discriminator in practice:
```python
combined_score = 0.4 * geo_score + 0.6 * name_score
```

For each `no_match` point, pick the client_base candidate with the **highest combined score**. Flag the pair as a mistake if `combined_score >= 0.65`.

This strict threshold ensures only high-confidence false negatives are flagged. With TF-IDF weighting already filtering out common-word noise, 0.65 means a pair must be strong on both axes — a genuinely similar distinctive name AND reasonable geographic proximity. This dramatically reduces false positives compared to lower thresholds while still catching real algorithm mistakes.

### What to record for each mistake

```python
{
    "prospection_outlet_name": ...,
    "prospection_outlet_id": ...,
    "prospection_lat": ...,
    "prospection_lon": ...,
    "prospection_category": ...,       # if available
    "client_base_outlet_name": ...,
    "client_base_outlet_id": ...,
    "client_base_lat": ...,
    "client_base_lon": ...,
    "client_base_category": ...,       # if available
    "distance_meters": ...,
    "name_similarity_pct": ...,        # fuzzy token_sort_ratio (0–100)
    "tfidf_cosine": ...,               # TF-IDF cosine similarity (0–1)
    "hybrid_name_score": ...,          # 0.5*fuzzy + 0.5*tfidf (0–1)
    "geo_score": ...,                  # 0–1
    "name_score": ...,                 # same as hybrid_name_score (0–1)
    "combined_score": ...,             # 0.4*geo + 0.6*name (0–1), the decisive metric
    "match_reason": ...                # "proximity_dominant" / "name_dominant" / "both_strong"
                                       # proximity_dominant: geo_score > name_score
                                       # name_dominant: name_score >= geo_score
                                       # both_strong: both >= 0.6
}
```

The IDs from both bases are the most important output — they're what the user needs to feed back into the algorithm.

---

## Step 4: Build Map 2 — Mistakes map

Build a second Folium map showing only the detected mistake pairs. This map helps the user visually confirm each flagged pair and extract IDs for algorithm improvement.

- 🟠 **Orange markers** (`CircleMarker`, radius=9, fill): The no_match prospection point (the potential mistake)
- 🟣 **Purple markers** (`CircleMarker`, radius=9, fill): The matching client_base outlet

Draw a `folium.PolyLine` between each pair (light grey, weight=2, dashed).

Each marker popup must show:
- Outlet name and **ID** (from its respective file — this is critical)
- Business category (if available)
- Distance between the pair (meters)
- Name similarity score (%)
- Combined score (0–1)
- Match reason (proximity_dominant / name_dominant / both_strong)

---

## Step 5: Category analysis

Only run this step if a `business_category` column was found in at least one of the files.

### 5a — No-match share per category

Using the `prospection_output` file, compute for each category:
- Total outlets
- Count of `match` and `no_match`
- `no_match_share` = no_match / total (as a percentage)

Sort by `no_match_share` descending. This tells the user which categories the algorithm is struggling with most.

### 5b — Category mapping Excel

The two files may use different category naming conventions. Build a mapping that covers **all unique categories from both files**, regardless of match/no_match status — the goal is a clean crosswalk between the two taxonomies, not a QA filter.

1. Collect the unique category values from `prospection_output` (`prospection_category`) and from `client_base` (`client_base_category`) independently.
2. For each unique category in prospection_output, find the best equivalent in client_base using both fuzzy string matching (`rapidfuzz.fuzz.token_sort_ratio`) and semantic understanding (e.g. "Supérette" → "Convenience Store", "Bar Tabac" → "On-Trade Bar"). If no reasonable match exists, leave `client_base_category` blank.
3. Assign a `confidence` level: **High** = clear semantic or near-exact match, **Medium** = plausible but ambiguous, **Low** = weak or guessed match.
4. Save as `category_mapping.xlsx` with columns: `prospection_category`, `client_base_category`, `confidence`, `notes`.

Keep a lookup dict of this mapping in memory — it will be used in Step 5d to enrich the no_match file.

### 5c — Non-beverage category issue list

Using your knowledge of the market (FMCG, on-trade, off-trade, food service), classify each unique category in `prospection_output` as either **beverage-relevant** or **non-beverage**. A category is non-beverage if it clearly does not sell or stock drinks (e.g. clothing stores, hardware shops, pharmacies with no food section, auto parts, etc.). When in doubt, lean toward keeping it — flag only clear mismatches.

Save any non-beverage categories as `category_issues.xlsx` with columns:
- `category`: the category name from prospection_output
- `outlet_count`: number of outlets with this category
- `no_match_count`: how many were labeled no_match
- `reason`: brief explanation of why this category likely doesn't sell beverages

If all categories look beverage-relevant, create the file with a note row: "No non-beverage categories detected."

### 5d — Enriched no_match file

Take all rows from `prospection_output` where `match_no_match == "no_match"` and produce `no_match_enriched.xlsx`. Start from the original columns, then append three new ones:

**`excluding_suggestion`** — reason to exclude this outlet from the algorithm's no_match population. Use the most specific applicable value:

- `false_negative_proximity` — flagged as a mistake in Step 3 with `match_reason == "proximity_dominant"` (geo signal was the decisive factor)
- `false_negative_name_similarity` — flagged as a mistake in Step 3 with `match_reason == "name_dominant"` (name signal was the decisive factor)
- `false_negative_both_strong` — flagged as a mistake in Step 3 with `match_reason == "both_strong"` (both signals were strong)
- `false_negative_category` — not caught by Step 3 proximity/name detection, but the outlet's `mapped_category` (from Step 5b) maps to a category that exists in client_base AND the mapping confidence is Medium or High. This is a weaker, category-level signal suggesting the outlet type belongs in the client base even if the specific outlet wasn't matched.
- `no_beverage_category` — the outlet's category was flagged as non-beverage in Step 5c
- Leave blank if none of the above apply — the outlet is a genuine no_match with no known data quality issue

**Priority when multiple flags apply**: `false_negative_both_strong` > `false_negative_proximity` > `false_negative_name_similarity` > `false_negative_category` > `no_beverage_category`. A single cell gets one value — the highest-priority one.

**`mapped_category`** — the best matching client_base category for this outlet's category, drawn from the lookup dict built in Step 5b. Leave blank if the category had no match or if no category column exists.

**`mapped_category_confidence`** — the confidence of that mapping: High / Medium / Low. Leave blank if `mapped_category` is blank.

Sort the output by `excluding_suggestion` (non-blank first, then alphabetical), then by outlet name.

---

## Step 6: Market penetration benchmark

This step helps put the match rate in context: if the algorithm is labeling 70% of outlets as no_match, is that reasonable for this market or is it a red flag?

### 6a — Detect the market

Use `geopy.geocoders.Nominatim` to reverse-geocode a sample of coordinates (pick 5 spread across the dataset). Extract the country and, if consistent, the city or region. If the coordinates are spread across multiple countries, note that.

### 6b — Search for Coca-Cola market data

Use your web search tool to find:
- Coca-Cola volume share or outlet penetration in the detected country/region
- Industry reports, FMCG benchmarks, or news articles about Coca-Cola distribution in that market
- If exact penetration data isn't available, look for proxies: market share %, number of points of sale, distribution coverage

Search queries to try:
- `"Coca-Cola" penetration "[country]" outlets distribution site:coca-colacompany.com OR site:statista.com OR site:euromonitor.com`
- `"Coca-Cola" "[country]" market share FMCG distribution coverage`

### 6c — Compare and flag

Compute the **observed match rate** = matched outlets / total prospection_output outlets.

Compare it against what you found:
- If Coca-Cola has high penetration in the market (e.g. >60%) but the match rate is very low (e.g. <20%), flag this as a potential data quality issue — the algorithm may be under-matching or the prospection base may be incomplete.
- If the match rate is roughly consistent with known penetration levels, call it out as a positive signal.
- If no reliable data was found, state that clearly and skip the comparison.

Write a short paragraph (3–5 sentences) summarizing your finding. This goes into the final report.

---

## Step 7: Save outputs

Save all outputs to the same directory where the input files are located (or the current working directory if unclear).

1. **`map_overview.html`** — Full overview map (Map 1)
2. **`map_mistakes.html`** — Mistakes map (Map 2)
3. **`mistakes_report.csv`** — CSV with columns:
   - `prospection_outlet_name`, `prospection_outlet_id`, `prospection_category`
   - `client_base_outlet_name`, `client_base_outlet_id`, `client_base_category`
   - `distance_meters`, `name_similarity_pct`, `geo_score`, `name_score`, `combined_score`, `match_reason`
4. **`category_mapping.xlsx`** — Category mapping between the two bases (Step 5b)
5. **`category_issues.xlsx`** — Non-beverage category list (Step 5c)
6. **`no_match_enriched.xlsx`** — All no_match outlets with `excluding_suggestion`, `mapped_category`, `mapped_category_confidence` (Step 5d)
7. **`qa_report.html`** — Full QA report (Step 8)

---

## Step 8: Generate the QA report

Produce a self-contained `qa_report.html` file with inline CSS and JavaScript. The report should be clean, professional, and printable. Structure it as follows:

### Section 1 — Executive summary
- Dataset overview: total outlets per file, date range if available
- Match rate: X% matched, X% no_match (with a simple donut or bar chart)
- Mistakes detected: count and % of no_match points flagged as false negatives
- Market: detected country/city

### Section 2 — Base comparison table
A side-by-side table comparing key statistics between client_base and prospection_output:
- Total outlet count
- Geographic coverage (bounding box or city/region spread)
- Unique business categories (if available)
- Overlap (matched outlets as % of client_base)

### Section 3 — Category breakdown (only if categories available)
- Table: category, total outlets, match count, no_match count, no_match share % — sorted by no_match share descending
- Highlight rows where no_match_share > 50% in amber, > 75% in red
- Brief note on non-beverage categories flagged

### Section 4 — Mistakes analysis
- Total mistakes detected and breakdown by match_reason
- Top 10 mistake pairs table (by combined_score descending): outlet names, IDs, distance, name similarity, combined score
- Note that full list is in `mistakes_report.csv`

### Section 5 — Market penetration context
- Detected market (country / city)
- Coca-Cola penetration data found (with source links)
- Comparison paragraph written in Step 6c
- Verdict: consistent / potentially under-matched / data insufficient

### Style guidelines
- Use a clean sans-serif font (system-ui or Inter)
- Light background (#f8f9fa), white cards with subtle box-shadow
- Section headers in a dark navy (#1a2b4a)
- Keep charts simple — use inline SVG or Chart.js from CDN rather than heavy libraries
- Include a timestamp and the input filenames in the footer

---

## Step 9: Print a summary

After saving, print a clear summary:

```
=== Prospection QA Summary ===
client_base outlets:           X
prospection_output (match):    X
prospection_output (no_match): X
Match rate:                    X%

Mistakes detected:             X  (X% of no_match points)
  → Proximity dominant:  X
  → Name dominant:       X
  → Both strong:         X

Category analysis:
  → Categories in prospection_output: X
  → Non-beverage categories flagged:  X

Market: [country / city]
  → Observed match rate: X%
  → Coca-Cola penetration benchmark: [data found / not found]
  → Assessment: [consistent / potentially under-matched / insufficient data]

Outputs saved:
  → map_overview.html
  → map_mistakes.html
  → mistakes_report.csv
  → category_mapping.xlsx
  → category_issues.xlsx
  → no_match_enriched.xlsx
  → qa_report.html
```

Then provide the `computer://` links so the user can open the files directly.
