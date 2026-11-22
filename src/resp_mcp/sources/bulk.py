"""One paginated source query for a scan, grouped into jurisdiction series."""

from datetime import date

from resp_mcp.clients.socrata import query, soql_and, soql_eq, soql_gte, soql_lte
from resp_mcp.models.common import Pathogen, Signal
from resp_mcp.reference.jurisdictions import Jurisdiction, jurisdiction_full_name
from resp_mcp.sources import nhsn, nwss


async def fetch_many(
    jurisdictions: list[Jurisdiction],
    pathogen: Pathogen,
    signal: Signal,
    start: date,
    end: date,
) -> dict:
    """Return observations and individual provenance for each jurisdiction."""
    if signal == Signal.test_positivity:
        raise ValueError("National-only positivity cannot rank states.")
    adapter = nhsn if signal == Signal.hospital_admissions else nwss
    date_col = "weekendingdate" if adapter is nhsn else "week_end"
    geo_col = "jurisdiction" if adapter is nhsn else "state_territory"
    names = {
        j.code: j.code if adapter is nhsn else jurisdiction_full_name(j.code)
        for j in jurisdictions
    }
    where = soql_and(
        "(" + " OR ".join(soql_eq(geo_col, name) for name in names.values()) + ")",
        soql_gte(date_col, start.isoformat()),
        soql_lte(date_col, end.isoformat()),
        soql_eq("pathogen_target", nwss._PATHOGEN_MAP[pathogen])
        if adapter is nwss
        else "",
    )
    rows = await query(
        adapter.DATASET_ID,
        where=where,
        order=f"{date_col} ASC, {geo_col} ASC"
        + (", site ASC" if adapter is nwss else ""),
    )
    groups: dict[str, list[dict]] = {name: [] for name in names.values()}
    for row in rows:
        if row.get(geo_col) in groups:
            groups[row[geo_col]].append(row)
    return {
        j.code: adapter.parse_rows(groups[names[j.code]], j, pathogen)
        for j in jurisdictions
    }
