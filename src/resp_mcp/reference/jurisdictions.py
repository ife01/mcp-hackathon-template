"""Jurisdiction reference data for the Respiratory MCP server.

Covers all 50 states, DC, USA (national), and territories confirmed in
Build 0.3 data reconnaissance. All codes verified against live NHSN data.

Design:
- Jurisdiction is a plain dataclass (not a Pydantic model) — it's internal
  reference data, not tool I/O.
- resolve_jurisdiction() performs case-insensitive fuzzy matching with an
  input guard (empty / >64 chars / control characters rejected up front).
- On failure, raises UnknownJurisdiction with up to 3 difflib suggestions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Literal

# ── Types ─────────────────────────────────────────────────────────────────────

JurisdictionType = Literal["national", "state", "district", "territory"]

_MAX_INPUT_LEN = 64
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


@dataclass(frozen=True)
class Jurisdiction:
    """A single geographic jurisdiction supported by the server."""

    code: str           # 2-letter code (e.g. "GA", "USA", "PR")
    name: str           # Full display name (e.g. "Georgia")
    fips: str | None    # 2-digit FIPS code for states (None for USA/territories)
    hhs_region: int | None  # HHS region 1–10 (None for national)
    type: JurisdictionType


class UnknownJurisdiction(ValueError):
    """Raised when resolve_jurisdiction() cannot match the input."""

    def __init__(self, text: str, suggestions: list[str]) -> None:
        self.text = text
        self.suggestions = suggestions
        hint = (
            f" Did you mean: {', '.join(suggestions)}?"
            if suggestions
            else " No close matches found."
        )
        super().__init__(
            f"Unknown jurisdiction {text!r}.{hint} "
            "Use a 2-letter state code (e.g. 'GA'), 'USA' for national, "
            "or a full state name."
        )


# ── Jurisdiction registry ─────────────────────────────────────────────────────

_JURISDICTIONS: list[Jurisdiction] = [
    # National
    Jurisdiction("USA", "United States", None, None, "national"),
    # States
    Jurisdiction("AL", "Alabama",        "01", 4,  "state"),
    Jurisdiction("AK", "Alaska",         "02", 10, "state"),
    Jurisdiction("AZ", "Arizona",        "04", 9,  "state"),
    Jurisdiction("AR", "Arkansas",       "05", 6,  "state"),
    Jurisdiction("CA", "California",     "06", 9,  "state"),
    Jurisdiction("CO", "Colorado",       "08", 8,  "state"),
    Jurisdiction("CT", "Connecticut",    "09", 1,  "state"),
    Jurisdiction("DE", "Delaware",       "10", 3,  "state"),
    Jurisdiction("FL", "Florida",        "12", 4,  "state"),
    Jurisdiction("GA", "Georgia",        "13", 4,  "state"),
    Jurisdiction("HI", "Hawaii",         "15", 9,  "state"),
    Jurisdiction("ID", "Idaho",          "16", 10, "state"),
    Jurisdiction("IL", "Illinois",       "17", 5,  "state"),
    Jurisdiction("IN", "Indiana",        "18", 5,  "state"),
    Jurisdiction("IA", "Iowa",           "19", 7,  "state"),
    Jurisdiction("KS", "Kansas",         "20", 7,  "state"),
    Jurisdiction("KY", "Kentucky",       "21", 4,  "state"),
    Jurisdiction("LA", "Louisiana",      "22", 6,  "state"),
    Jurisdiction("ME", "Maine",          "23", 1,  "state"),
    Jurisdiction("MD", "Maryland",       "24", 3,  "state"),
    Jurisdiction("MA", "Massachusetts",  "25", 1,  "state"),
    Jurisdiction("MI", "Michigan",       "26", 5,  "state"),
    Jurisdiction("MN", "Minnesota",      "27", 5,  "state"),
    Jurisdiction("MS", "Mississippi",    "28", 4,  "state"),
    Jurisdiction("MO", "Missouri",       "29", 7,  "state"),
    Jurisdiction("MT", "Montana",        "30", 8,  "state"),
    Jurisdiction("NE", "Nebraska",       "31", 7,  "state"),
    Jurisdiction("NV", "Nevada",         "32", 9,  "state"),
    Jurisdiction("NH", "New Hampshire",  "33", 1,  "state"),
    Jurisdiction("NJ", "New Jersey",     "34", 2,  "state"),
    Jurisdiction("NM", "New Mexico",     "35", 6,  "state"),
    Jurisdiction("NY", "New York",       "36", 2,  "state"),
    Jurisdiction("NC", "North Carolina", "37", 4,  "state"),
    Jurisdiction("ND", "North Dakota",   "38", 8,  "state"),
    Jurisdiction("OH", "Ohio",           "39", 5,  "state"),
    Jurisdiction("OK", "Oklahoma",       "40", 6,  "state"),
    Jurisdiction("OR", "Oregon",         "41", 10, "state"),
    Jurisdiction("PA", "Pennsylvania",   "42", 3,  "state"),
    Jurisdiction("RI", "Rhode Island",   "44", 1,  "state"),
    Jurisdiction("SC", "South Carolina", "45", 4,  "state"),
    Jurisdiction("SD", "South Dakota",   "46", 8,  "state"),
    Jurisdiction("TN", "Tennessee",      "47", 4,  "state"),
    Jurisdiction("TX", "Texas",          "48", 6,  "state"),
    Jurisdiction("UT", "Utah",           "49", 8,  "state"),
    Jurisdiction("VT", "Vermont",        "50", 1,  "state"),
    Jurisdiction("VA", "Virginia",       "51", 3,  "state"),
    Jurisdiction("WA", "Washington",     "53", 10, "state"),
    Jurisdiction("WV", "West Virginia",  "54", 3,  "state"),
    Jurisdiction("WI", "Wisconsin",      "55", 5,  "state"),
    Jurisdiction("WY", "Wyoming",        "56", 8,  "state"),
    # District
    Jurisdiction("DC", "District of Columbia", "11", 3, "district"),
    # Territories
    Jurisdiction("PR", "Puerto Rico",          "72", 2, "territory"),
    Jurisdiction("VI", "U.S. Virgin Islands",  "78", 2, "territory"),
    Jurisdiction("GU", "Guam",                 "66", 9, "territory"),
    Jurisdiction("AS", "American Samoa",       "60", 9, "territory"),
    Jurisdiction("MP", "Northern Mariana Islands", "69", 9, "territory"),
]

# Fast lookup by code
_BY_CODE: dict[str, Jurisdiction] = {j.code.upper(): j for j in _JURISDICTIONS}

# Alias map → canonical code (case-insensitive keys stored lowercase)
_ALIASES: dict[str, str] = {
    # National aliases
    "us":           "USA",
    "usa":          "USA",
    "national":     "USA",
    "united states": "USA",
    "u.s.":         "USA",
    "u.s.a.":       "USA",
    # DC aliases
    "dc":           "DC",
    "washington dc": "DC",
    "washington d.c.": "DC",
    "d.c.":         "DC",
    # Territory aliases
    "puerto rico":  "PR",
    "virgin islands": "VI",
    "us virgin islands": "VI",
    "u.s. virgin islands": "VI",
    "guam":         "GU",
    "american samoa": "AS",
    "northern mariana islands": "MP",
    "mariana islands": "MP",
}

# Build lookup tables: lowercase name → code, lowercase code → code
_NAME_TO_CODE: dict[str, str] = {j.name.lower(): j.code for j in _JURISDICTIONS}
_CODE_TO_CODE: dict[str, str] = {j.code.lower(): j.code for j in _JURISDICTIONS}

# All candidate strings for difflib matching (lowercase)
_ALL_CANDIDATES: list[str] = (
    [j.code.lower() for j in _JURISDICTIONS]
    + [j.name.lower() for j in _JURISDICTIONS]
    + list(_ALIASES.keys())
)


def _strip_control(text: str) -> str:
    """Remove Unicode control characters from text."""
    return _CONTROL_CHAR_RE.sub("", text)


def resolve_jurisdiction(text: str) -> Jurisdiction:
    """Resolve a free-text jurisdiction string to a Jurisdiction object.

    Matching order:
      1. Input guard: reject empty, >64 chars, or control-character-only strings.
      2. Alias map (e.g. "US" → USA, "national" → USA).
      3. Exact code match (case-insensitive, e.g. "ga" → GA).
      4. Exact name match (case-insensitive, e.g. "georgia" → GA).
      5. difflib suggestions on failure.

    Args:
        text: Free-text jurisdiction name or code from tool input.

    Returns:
        Jurisdiction dataclass for the matched jurisdiction.

    Raises:
        UnknownJurisdiction: If no match found, with up to 3 difflib suggestions.
        ValueError: If input fails the length or character guard.
    """
    # ── Input guard ───────────────────────────────────────────────────────
    if not text or not text.strip():
        raise ValueError("Jurisdiction must not be empty.")
    if len(text) > _MAX_INPUT_LEN:
        raise ValueError(
            f"Jurisdiction input too long ({len(text)} chars; max {_MAX_INPUT_LEN})."
        )
    cleaned = _strip_control(text).strip()
    if not cleaned:
        raise ValueError("Jurisdiction contains only control characters.")

    normalized = cleaned.lower()

    # ── Alias map ─────────────────────────────────────────────────────────
    if normalized in _ALIASES:
        return _BY_CODE[_ALIASES[normalized]]

    # ── Exact code match ──────────────────────────────────────────────────
    if normalized in _CODE_TO_CODE:
        return _BY_CODE[_CODE_TO_CODE[normalized]]

    # ── Exact name match ──────────────────────────────────────────────────
    if normalized in _NAME_TO_CODE:
        return _BY_CODE[_NAME_TO_CODE[normalized]]

    # ── difflib suggestions ───────────────────────────────────────────────
    close = get_close_matches(normalized, _ALL_CANDIDATES, n=3, cutoff=0.6)
    # Deduplicate: map suggestions back to display names
    seen: set[str] = set()
    suggestions: list[str] = []
    for c in close:
        code = (
            _ALIASES.get(c)
            or _CODE_TO_CODE.get(c)
            or _NAME_TO_CODE.get(c)
        )
        if code and code not in seen:
            seen.add(code)
            suggestions.append(f"{code} ({_BY_CODE[code].name})")

    raise UnknownJurisdiction(cleaned, suggestions)


def get_all_jurisdictions() -> list[Jurisdiction]:
    """Return all registered jurisdictions."""
    return list(_JURISDICTIONS)


def get_by_hhs_region(region: int) -> list[Jurisdiction]:
    """Return all state/territory jurisdictions in a given HHS region (1–10)."""
    return [j for j in _JURISDICTIONS if j.hhs_region == region]


def jurisdiction_full_name(code: str) -> str:
    """Return the full name for a jurisdiction code (e.g. 'GA' → 'Georgia').

    Used by NWSS adapter to map 2-letter codes to full state names.
    Returns the code itself if not found (safe fallback).
    """
    j = _BY_CODE.get(code.upper())
    return j.name if j else code
