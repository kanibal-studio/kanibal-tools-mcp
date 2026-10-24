"""MCP server exposing four local, read-only Kanibal Studio tools.

Every tool is a pure computation on the arguments it receives: no network call,
no file read or write, no state kept between calls. The underlying packages are
published separately on PyPI (demarchage-consent, cost-per-kept-meeting,
rgpd-offshore-check, least-cost-capable).
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Optional

import cost_per_kept_meeting as cpkm
import demarchage_consent as consent
import rgpd_offshore_check as rgpd
from least_cost_capable.select_model import select
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import __version__

LOCAL_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp = FastMCP(
    "kanibal-tools",
    instructions=(
        "Local, read-only tools from Kanibal Studio (ALTA VISTA360, S.L.U.). They compute "
        "from the arguments only and never contact a service. The consent and GDPR tools "
        "are checklists, not legal advice."
    ),
    website_url="https://github.com/kanibal-studio/kanibal-tools-mcp",
)
# FastMCP takes no version argument; without this the server reports the SDK version.
mcp._mcp_server.version = __version__


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


@mcp.tool(annotations=LOCAL_READ_ONLY)
def check_telemarketing_consent(
    collected_at: str,
    revoked_at: Optional[str] = None,
    now: Optional[str] = None,
    max_age_days: Optional[int] = None,
) -> dict[str, Any]:
    """France only: is a consent to telephone canvassing still valid under décret 2026-662?

    Dates are ISO 8601 (a date without time zone is read as UTC). Statuses:
    "valide", "expire" (older than the ceiling, 365 days at most), "revoque"
    (any sign of revocation wins), "preuve_manquante" (no readable collection
    date, or one in the future). Fail-closed. Not legal advice.
    """
    result = consent.assess_consent(
        collected_at, now=now, revoked_at=revoked_at, max_age_days=max_age_days
    )
    return {
        "status": str(result.status),
        "evaluated_at": _iso(result.evaluated_at),
        "collected_at": _iso(result.collected_at),
        "revoked_at": _iso(result.revoked_at),
        "max_age_days": result.max_age_days,
        "expires_at": _iso(result.expires_at),
        "proof_retention_until": _iso(result.proof_retention_until),
        "days_remaining": result.days_remaining,
        "decree": consent.DECREE_REFERENCE,
        "tool": f"demarchage-consent {consent.__version__}",
    }


@mcp.tool(annotations=LOCAL_READ_ONLY)
def rank_lead_sources_by_kept_meeting(
    csv_text: str, min_meetings: int = cpkm.DEFAULT_MIN_MEETINGS
) -> dict[str, Any]:
    """Rank B2B lead sources on cost per kept qualified meeting instead of cost per lead.

    csv_text is the CSV file content, with the columns documented at
    https://github.com/kanibal-studio/cost-per-kept-meeting#input-columns.
    Results under min_meetings qualified kept meetings are flagged as a small
    sample, never hidden. A low cost per meeting does not prove profitability.
    """
    try:
        table = cpkm.parse_csv(io.StringIO(csv_text))
    except cpkm.InputError as exc:
        raise ValueError("invalid CSV: " + "; ".join(exc.messages)) from exc
    results = cpkm.analyse(table, min_meetings=min_meetings)
    document = json.loads(cpkm.render_json(results, min_meetings))
    document["tool"] = f"cost-per-kept-meeting {cpkm.__version__}"
    return document


@mcp.tool(annotations=LOCAL_READ_ONLY)
def gdpr_offshore_gap_report(answers: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    """GDPR gap report for customer-service processing outsourced outside the EU/EEA.

    answers follows https://github.com/kanibal-studio/rgpd-offshore-check#input-format.
    Only a JSON true satisfies a check; anything else is reported as a gap or
    "to_verify". lang is "en" or "fr". Not legal advice and not a certification:
    a report without blocking gap is not a finding of compliance.
    """
    return rgpd.evaluate(answers, lang=lang).to_dict()


@mcp.tool(annotations=LOCAL_READ_ONLY)
def select_least_cost_capable_model(catalogue: dict[str, Any]) -> dict[str, Any]:
    """Pick, from a supplied catalogue, the model with the lowest declared cost rank
    among those that have every required capability and are available and authorised.

    catalogue follows https://github.com/kanibal-studio/least-cost-capable (fields
    required_capabilities and models). Unknown or non-comparable cost evidence stays
    unresolved. Nothing is called, switched or launched; savings are not guaranteed.
    """
    return select(catalogue)


def main() -> None:
    """Run the server over stdio (the transport used by desktop MCP clients)."""
    mcp.run()


__all__ = [
    "__version__",
    "check_telemarketing_consent",
    "gdpr_offshore_gap_report",
    "main",
    "mcp",
    "rank_lead_sources_by_kept_meeting",
    "select_least_cost_capable_model",
]
