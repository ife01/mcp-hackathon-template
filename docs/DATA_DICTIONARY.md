# Data Dictionary

All column names, dataset IDs, and geography codes verified against live CDC Socrata
API on 2026-11-20 (Build 0.3). Every field referenced in source adapters appears here.

---

## Source 1 — NHSN Hospital Admissions

| Field | Value |
|---|---|
| **Dataset ID** | `vdzy-6i9v` |
| **Dataset name** | Weekly Hospital Respiratory Admission Levels and Rates by Jurisdiction, National Healthcare Safety Network (NHSN) |
| **URL** | https://data.cdc.gov/resource/vdzy-6i9v.json |
| **Cadence** | Weekly (Fridays); data through the prior Friday |
| **Last updated** | 2026-11-20 (rowsUpdatedAt confirmed live) |
| **Date column** | `weekendingdate` (ISO-8601 string, e.g. `"2026-11-14"`) |
| **Geography column** | `jurisdiction` (2-letter state code, `"USA"` for national, `"PR"` for Puerto Rico) |

### Columns used by adapters

| Column | Description | Unit |
|---|---|---|
| `jurisdiction` | State abbreviation or `USA` | — |
| `weekendingdate` | Week-ending date (Saturday) | ISO date string |
| `totalconfflunewadmper100k` | Influenza new admissions per 100k | rate |
| `totalconfc19newadmper100k` | COVID-19 new admissions per 100k | rate |
| `totalconfrsvnewadmper100k` | RSV new admissions per 100k | rate |
| `totalconfflunewadm` | Influenza new admissions count | count |
| `totalconfc19newadm` | COVID-19 new admissions count | count |
| `totalconfrsvnewadm` | RSV new admissions count | count |
| `totalconfflunewadmper100klevel` | Official CDC level for flu (Very Low/Low/Medium/High/Very High) | level |
| `totalconfc19newadmper100klevel` | Official CDC level for COVID-19 | level |
| `totalconfrsvnewadmper100klevel` | Official CDC level for RSV | level |
| `totalconfflunewadmhosprep` | Hospitals reporting flu (count) | count |
| `totalconfflunewadmperchosprep` | Hospitals reporting flu (%) | percent |

### Decisions
- **Use published rates and levels** (`per100k` + `per100klevel`) as the primary signal,
  not raw counts. Counts are retained for small-number guards in trend analytics.
- National jurisdiction code is `"USA"` (not `"US"` or `"National"`).
- Puerto Rico code is `"PR"`.
- Coverage column (`totalconfflunewadmhosprep`) reflects hospitals reporting that week.
- **NHSN reporting regime changed in 2024** (voluntary → mandatory reporting).
  Season comparisons must exclude pre-2024 seasons or note the regime change.

---

## Source 2 — NWSS Wastewater Viral Activity Level

| Field | Value |
|---|---|
| **Dataset ID** | `atcp-73re` |
| **Dataset name** | CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV |
| **URL** | https://data.cdc.gov/resource/atcp-73re.json |
| **Cadence** | Weekly (updated Thursdays) |
| **Last updated** | 2026-11-20 (confirmed live) |
| **Date column** | `week_end` (ISO date string, e.g. `"2026-11-14"`) |
| **Geography column** | `state_territory` (full state name, e.g. `"Georgia"`, `"Puerto Rico"`) |

### Columns used by adapters

| Column | Description | Unit |
|---|---|---|
| `state_territory` | Full state/territory name | — |
| `week_end` | Week-ending date | ISO date string |
| `site` | Site identifier (`"ID:NNN"`) | — |
| `population_served` | Population served by this site | count |
| `source` | Data source (e.g. `"State_Territory"`, `"WastewaterSCAN"`, `"CDC_Verily"`) | — |
| `site_wval` | Viral activity level value (1–5 scale equivalent) | wval |
| `site_wval_category` | Official CDC category (Very Low / Low / Medium / High / Very High) | level |
| `pathogen_target` | One of `"Influenza A virus"`, `"SARS-CoV-2"`, `"RSV"` | — |
| `date_included_in_wval` | Date site was included in WVAL calculation | ISO date |
| `date_updated` | Timestamp of last update for this record | datetime |

### Decisions
- **This dataset is site-level** (one row per site per pathogen per week). Adapters
  aggregate to state level by computing median `site_wval` across all sites with
  data for that week, with `coverage={"n_sites": k}`.
- **Influenza** = `pathogen_target='Influenza A virus'` (influenza A only; note in provenance).
- **COVID-19** = `pathogen_target='SARS-CoV-2'`
- **RSV** = `pathogen_target='RSV'`
- **Puerto Rico**: zero rows — no wastewater sites. Status → `"insufficient_coverage"`.
- **Low coverage guard**: fewer than 2 sites reporting → `value=None` + provenance note
  `"insufficient wastewater coverage"`.
- `geography_level` = `"site_aggregate"` (not `"state"` — it is an aggregation of sites).
- State names are full English names (title case), not abbreviations. The adapter must
  map state codes → full names using the jurisdictions reference module.

---

## Source 3 — NREVSS Test Positivity (National)

| Field | Value |
|---|---|
| **Dataset ID** | `seuz-s2cv` |
| **Dataset name** | Percent of Tests Positive for Viral Respiratory Pathogens |
| **URL** | https://data.cdc.gov/resource/seuz-s2cv.json |
| **Cadence** | Weekly |
| **Last updated** | 2026-11-20 (confirmed live) |
| **Date column** | `week_end` (ISO-8601 datetime string, e.g. `"2026-11-14T00:00:00.000"`) |
| **Geography column** | None — **national only** |

### Columns used by adapters

| Column | Description | Unit |
|---|---|---|
| `week_end` | Week-ending date (parse date portion only) | ISO datetime string |
| `pathogen` | One of `"Influenza"`, `"COVID-19"`, `"RSV"` | — |
| `percent_test_positivity` | Percent of tests positive | percent |

### Decisions
- **This dataset is national only** — no state or HHS region breakdown.
  `geography_level` = `"national"`.
- When a jurisdiction other than national is requested, adapter returns
  `status="unavailable"` with caveat `"Test positivity data is only available at the
  national level from this source"`.
- **Influenza** = `pathogen='Influenza'` (combined flu A+B; note in provenance).
- **COVID-19** = `pathogen='COVID-19'`
- **RSV** = `pathogen='RSV'`
- Most recent week may be incomplete; `>= 90%` complete two weeks back — note in provenance.

### Retired / superseded IDs
- `j8mb-3ugh` — returns HTTP 404 as of 2026-11-20. Replaced by `seuz-s2cv` (national)
  and `rgnm-fkqb` (HHS region, SARS-CoV-2 + RSV only, no influenza).

---

## Source 3b — NREVSS HHS Region (RSV + COVID-19 only)

| Field | Value |
|---|---|
| **Dataset ID** | `rgnm-fkqb` |
| **Dataset name** | Percent positivity of respiratory viruses by nucleic acid amplification tests (NAATs), NREVSS Dashboard |
| **URL** | https://data.cdc.gov/resource/rgnm-fkqb.json |
| **Cadence** | Weekly |
| **Last updated** | 2026-11-20 (confirmed live) |
| **Date column** | `mmwrweek_end` (ISO datetime string; some rows lack this column — filter with `mmwrweek_end IS NOT NULL`) |
| **Geography column** | `level` (e.g. `"Region 1"` … `"Region 10"`, `"National"`) |
| **State column** | `state` (full name when `level='State'`) |

### Columns used by adapters

| Column | Description | Unit |
|---|---|---|
| `mmwrweek_end` | MMWR week ending date | ISO datetime string |
| `level` | Geography level (`"National"`, `"Region 1"` … `"Region 10"`) | — |
| `state` | State name (only when level is state-level) | — |
| `pathogen` | `"SARS-COV-2"` or `"RSV"` (no influenza in this dataset) | — |
| `percent_pos` | Percent of NAATs positive | percent |
| `tests` | Number of tests (may be `"."` for missing) | count |
| `detections` | Number of detections (may be `"."` for missing) | count |

### Decisions
- No influenza data in this dataset. For influenza test positivity, use `seuz-s2cv` (national).
- State-level rows exist in the data (`level='State'`) but returned empty for GA/CA/OH/TX
  during Build 0.3 reconnaissance — HHS region fallback is the primary path.
- Missing values are encoded as `"."` — treat as `None`.
- `geography_level` = `"hhs_region"` when using regional rows.
- Note in provenance: `"Region X value applied to [state]; state-level not available"`.

---

## Geography Reference

NHSN jurisdiction codes verified from live data (Build 0.3):

| Code | Name | HHS Region |
|---|---|---|
| `USA` | United States (national) | — |
| `AL` | Alabama | 4 |
| `AK` | Alaska | 10 |
| `AZ` | Arizona | 9 |
| `AR` | Arkansas | 6 |
| `CA` | California | 9 |
| `CO` | Colorado | 8 |
| `CT` | Connecticut | 1 |
| `DE` | Delaware | 3 |
| `DC` | District of Columbia | 3 |
| `FL` | Florida | 4 |
| `GA` | Georgia | 4 |
| `HI` | Hawaii | 9 |
| `ID` | Idaho | 10 |
| `IL` | Illinois | 5 |
| `IN` | Indiana | 5 |
| `IA` | Iowa | 7 |
| `KS` | Kansas | 7 |
| `KY` | Kentucky | 4 |
| `LA` | Louisiana | 6 |
| `ME` | Maine | 1 |
| `MD` | Maryland | 3 |
| `MA` | Massachusetts | 1 |
| `MI` | Michigan | 5 |
| `MN` | Minnesota | 5 |
| `MS` | Mississippi | 4 |
| `MO` | Missouri | 7 |
| `MT` | Montana | 8 |
| `NE` | Nebraska | 7 |
| `NV` | Nevada | 9 |
| `NH` | New Hampshire | 1 |
| `NJ` | New Jersey | 2 |
| `NM` | New Mexico | 6 |
| `NY` | New York | 2 |
| `NC` | North Carolina | 4 |
| `ND` | North Dakota | 8 |
| `OH` | Ohio | 5 |
| `OK` | Oklahoma | 6 |
| `OR` | Oregon | 10 |
| `PA` | Pennsylvania | 3 |
| `RI` | Rhode Island | 1 |
| `SC` | South Carolina | 4 |
| `SD` | South Dakota | 8 |
| `TN` | Tennessee | 4 |
| `TX` | Texas | 6 |
| `UT` | Utah | 8 |
| `VT` | Vermont | 1 |
| `VA` | Virginia | 3 |
| `WA` | Washington | 10 |
| `WV` | West Virginia | 3 |
| `WI` | Wisconsin | 5 |
| `WY` | Wyoming | 8 |
| `PR` | Puerto Rico | 2 |
| `VI` | U.S. Virgin Islands | 2 |
| `GU` | Guam | — |

NWSS `state_territory` uses full English names (title case). NREVSS `rgnm-fkqb` uses
`"Region N"` format for HHS regions.
