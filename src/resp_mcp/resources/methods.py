"""Resource: resp://methods

Documents the analytic methods used by this server: trend classification,
season comparison, and concordance. All are server heuristics, not official
CDC classifications.
"""

# ruff: noqa: E501 -- embedded Markdown mirrors docs/METHODS.md

from __future__ import annotations

from fastmcp import FastMCP

_METHODS_TEXT = """\
# Respiratory MCP analytical methods

All trends, cross-signal patterns, ranks, and site aggregates are descriptive
server heuristics. They are not official CDC classifications, forecasts, or
validated outbreak alerts. `official_level` is populated only from a published
NHSN jurisdiction-level classification. Raw surveillance values retain their
source units; they are not themselves described as heuristics.

## Geography and coverage

NHSN supplies jurisdiction-level admission rates and counts. NREVSS `seuz-s2cv`
is national-only: every observation remains `jurisdiction="USA"`. A state
snapshot labels it `role="national_context"` and excludes it from local
concordance. State positivity scans are unsupported and return an actionable
error. A requested jurisdiction on the parent response is request context;
observation geography identifies the actual measured population.

NWSS values are server-derived medians of distinct sites with usable, finite,
nonnegative WVALs. Duplicate site/week records count once; conflicting records
are excluded. Fewer than two valid sites yields a missing value. The unique
modal source-site category is `derived_level`; ties and insufficient coverage
yield null. `aggregation_method` documents the calculation. This is not CDC's
official jurisdiction classification. A national request aggregates sites and
is also explicitly server-derived. Unknown population coverage remains unknown:
two sites do not establish population representativeness. Empty query results
do not prove that a jurisdiction has no surveillance sites. Changing site
participation may change an aggregate independently of disease activity.

CDC identifies less than 5% population coverage as limited coverage; this server
does not estimate that fraction from overlapping sewershed populations.
[CDC wastewater data](https://www.cdc.gov/wastewater/respiratory-viruses/national.html).
Wastewater influenza measures A only; positivity combines influenza A and B.

## Trend direction

The latest four observations must have usable values on four consecutive weekly
dates. They are sorted before comparison. Missing recent values are not stripped
to resurrect an older trend. Duplicate dates or gaps in this window produce
`insufficient_data`. `window_weeks` is the number of recent observation slots
inspected, at most four. Tools with a requested cutoff withhold trends whose
latest observation is more than 21 days old; this is a prototype freshness rule.

Compare the mean of the recent two weeks with the mean of the preceding two:

| Signal | Change required |
| --- | --- |
| Hospital admissions | At least 10% relative AND 0.1 admissions per 100,000 absolute |
| Test positivity | At least 1 percentage point absolute |
| Wastewater | At least 15% relative |

For admissions, if all four counts are known and BOTH two-week mean counts are
below 10, withhold the trend. Counts accompany published rates as `raw_count`.
Missing counts produce an explicit note that this guard could not be assessed.
When prior admissions equal zero, the absolute guard determines direction;
relative change remains null. Wastewater changing from a zero baseline returns
`insufficient_data`, not stable. Positivity uses its absolute guard. Thresholds
are prototype choices and have not been calibrated as public health alerts.

## Historical comparison

Seasons run from MMWR week 27 to week 26. Align by week within season. Clamp a
53-week season's extra week to the final week of a shorter comparison season.
Missing equivalent weeks may use a non-null observation within one week, within
the same season, trying the earlier week first. The actual selected date and
week index are returned with an alignment note.

`rank_vs_prior` compares only available aligned prior-week values. No usable
prior values means null rank, not rank 1. `n_prior_compared` gives the denominator;
rank 1 means highest among those comparisons, never an all-time record.
`pct_of_prior_peak` divides the current value by the highest peak among requested
eligible COMPLETE prior seasons, with every expected weekly value present.
Incomplete seasons cannot supply peaks. `prior_season_peaks` identifies included
seasons. A partial observed maximum is not called a season peak.

For NHSN, seasons starting before 2024 and aligned observations before the first
full reporting week ending November 9, 2024 are excluded. The 2024-25 season
straddles the transition and cannot provide a complete comparable season peak.
This conservative policy follows the November 1, 2024 reporting transition:
[CDC hospital reporting](https://www.cdc.gov/nhsn/psc/hospital-respiratory-reporting.html).
Tools fetch from the first requested season boundary, supporting up to five
prior seasons subject to source availability and query safety limits.

## Concordance and summaries

Concordance requires at least two distinct usable signals for the same requested
geographic scope. State-level snapshots exclude national positivity. With fewer
signals, return `insufficient_data`. With two or more signals: all increasing or
all decreasing yields the corresponding concordant pattern; all stable yields
stable; increasing plus stable yields `early_warning`; other mixtures yield
mixed. The `early_warning` identifier denotes a descriptive pattern only and is
not evidence of predictive lead time. Date spreads over 14 days are qualified.

Empty series are `insufficient_data`, a missing latest wastewater value is
`insufficient_coverage`, and upstream failure is `unavailable`. All-source
failure returns `upstream_unavailable` with dataset IDs. Scan outputs distinguish
assessed, insufficient, and unavailable jurisdictions, retain per-row provenance,
and report the rising total before limiting. No assessed jurisdictions yields
insufficient data; an outage never means no rising activity.

## Time, reproducibility, and performance

`as_of` filters week-ending dates using the data retrieved today. It does not
reconstruct what was available to an analyst at an earlier date. Later revisions
may be present. Only frozen, hash-verified snapshots support repeatable replay.
A two-week lag does not guarantee finalization. Sources can revise historical
data and change coverage or methods.

Requests use a six-second per-request timeout and a 20-second total query
deadline including retries, cache locking, and pagination. Snapshot pathogens
and sources are fetched concurrently. Scans use one logical paginated source
query and group locally. Reaching the 50,000-row safety cap produces an error;
partial data are not silently analyzed. Cache TTL defaults to one hour.
"""


def register(mcp: FastMCP) -> None:
    """Register resp://methods resource."""

    @mcp.resource(
        "resp://methods",
        name="analytic_methods",
        description=(
            "Documents the trend classification, season comparison, and "
            "concordance methods used by this server. All are server heuristics, "
            "not official CDC classifications. Read this before interpreting "
            "trend direction or concordance pattern fields in tool output."
        ),
        mime_type="text/markdown",
    )
    def analytic_methods() -> str:
        return _METHODS_TEXT
