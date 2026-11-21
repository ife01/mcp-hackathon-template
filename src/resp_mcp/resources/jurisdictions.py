"""Resource: resp://jurisdictions

Returns a machine-readable JSON list of all supported jurisdictions with
their codes, full names, HHS regions, and types.
"""

from __future__ import annotations

import json

from fastmcp import FastMCP

from resp_mcp.reference.jurisdictions import get_all_jurisdictions


def register(mcp: FastMCP) -> None:
    """Register resp://jurisdictions resource."""

    @mcp.resource(
        "resp://jurisdictions",
        name="supported_jurisdictions",
        description=(
            "JSON list of all supported jurisdictions: 50 states, DC, territories, "
            "and national (USA). Each entry includes code, name, HHS region (1–10), "
            "and type (state/district/territory/national). "
            "Use this to look up valid jurisdiction codes before calling tools."
        ),
        mime_type="application/json",
    )
    def supported_jurisdictions() -> str:
        jurs = get_all_jurisdictions()
        data = [
            {
                "code": j.code,
                "name": j.name,
                "hhs_region": j.hhs_region,
                "type": j.type,
                "fips": j.fips,
            }
            for j in jurs
        ]
        return json.dumps(data, indent=2)
