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
from typing import Annotated, Any, Literal, Optional

import cost_per_kept_meeting as cpkm
import demarchage_consent as consent
import rgpd_offshore_check as rgpd
from least_cost_capable.select_model import select
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

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

_BOOL = {"type": "boolean"}
_ART28_CLAUSES = (
    "subject_matter_and_duration", "nature_and_purpose", "data_types_and_data_subject_categories",
    "documented_instructions", "personnel_confidentiality", "security_measures_art32",
    "subprocessor_prior_authorisation", "subprocessor_flowdown", "data_subject_rights_assistance",
    "art32_36_assistance", "deletion_or_return", "audit_and_inspection",
)
_SECURITY_CONTROLS = (
    "encryption_in_transit", "pseudonymisation", "role_based_access", "access_logging",
    "physical_access_control", "personal_devices_policy", "clean_desk",
)

# Documentation only: validation stays a plain JSON object, so that a value such as the
# string "true" reaches the checklist unchanged and is reported as "to_verify" (fail-closed)
# instead of being coerced to a boolean.
ANSWERS_SCHEMA_DOC = {
    "properties": {
        "label": {"type": "string", "description": "Free name for the set-up, echoed in the report."},
        "destination_country": {"type": "string", "description": "Destination of the transfer."},
        "adequacy_decision": {**_BOOL, "description": "An EU adequacy decision exists for the destination."},
        "adequacy_scope_verified": {**_BOOL, "description": "The decision's scope (Art. 45(3)) covers this transfer."},
        "safeguards": {
            "type": "array",
            "items": {"type": "string", "enum": [
                "scc", "bcr", "code_of_conduct", "certification", "ad_hoc_clauses",
                "public_authority_instrument", "art49_derogation"]},
            "description": "Art. 46 tools in place. art49_derogation is recognised but never accepted as a basis.",
        },
        "tia_documented": {**_BOOL, "description": "A transfer impact assessment is documented."},
        "art28_contract": {
            "type": "object",
            "properties": {
                "in_writing": {**_BOOL, "description": "A written processor contract exists."},
                "clauses": {"type": "object", "properties": {c: _BOOL for c in _ART28_CLAUSES},
                            "description": "Art. 28 clauses present in the contract."},
            },
        },
        "security_controls": {"type": "object", "properties": {c: _BOOL for c in _SECURITY_CONTROLS},
                              "description": "Art. 32 controls in place (not exhaustive)."},
        "breach_notification_procedure": {**_BOOL, "description": "Written procedure for the processor to notify the controller."},
        "data_subject_rights_process": {**_BOOL, "description": "Process and timelines agreed with the provider."},
        "iso27001_scope_verified": {**_BOOL, "description": "Certificate scope verified (informational only)."},
    },
    "additionalProperties": True,
}

CATALOGUE_SCHEMA_DOC = {
    "properties": {
        "required_capabilities": {"type": "array", "items": {"type": "string"},
                                  "description": "Capabilities the task needs, e.g. [\"python\", \"debugging\"]."},
        "models": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique model identifier."},
                    "available": _BOOL,
                    "authorized": _BOOL,
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                    "capabilities_complete": {**_BOOL, "description": "Only a complete list can exclude a model."},
                    "cost": {
                        "type": "object",
                        "description": "Ranks compare only when metric, unit, workload and window match.",
                        "properties": {
                            "metric": {"type": "string"}, "unit": {"type": "string"},
                            "workload": {"type": "string"}, "window": {"type": "string"},
                            "source": {"type": "string"}, "as_of": {"type": "string"},
                            "relative_rank": {"type": "number", "description": "Lower means cheaper."},
                        },
                    },
                },
            },
        },
    },
    "required": ["required_capabilities", "models"],
}


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


@mcp.tool(annotations=LOCAL_READ_ONLY)
def check_telemarketing_consent(
    collected_at: Annotated[str, Field(description="When the consent was collected, ISO 8601; a date without time zone is read as UTC.")],
    revoked_at: Annotated[Optional[str], Field(description="Revocation date or any sign of revocation; omit if none.")] = None,
    now: Annotated[Optional[str], Field(description="Reference instant, ISO 8601; defaults to the current UTC time.")] = None,
    max_age_days: Annotated[Optional[int], Field(description="Stricter internal ceiling in days; values above 365 or not positive fall back to the legal 365.")] = None,
) -> dict[str, Any]:
    """France only: is a consent to telephone canvassing still valid under décret 2026-662?

    Returns "valide", "expire" (older than the ceiling), "revoque" (any sign of
    revocation wins) or "preuve_manquante" (no readable collection date, or one in the
    future), with the expiry date and proof-retention date. Fail-closed. Use it for
    French telemarketing consent only; for transfers of customer-service data outside
    the EU use gdpr_offshore_gap_report. Not legal advice.
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
    csv_text: Annotated[str, Field(description=(
        "CSV content with a header row. Required: source, meetings_qualified_kept and at least "
        "one cost column (cost_media, cost_data, cost_tools, cost_human_time, cost_other). "
        "Optional: period, leads, meetings_booked, meetings_kept, deals_closed, gross_margin. "
        "Numbers use a dot as decimal separator."))],
    min_meetings: Annotated[int, Field(description="Results under this many qualified kept meetings are flagged as a small sample, never hidden.")] = cpkm.DEFAULT_MIN_MEETINGS,
) -> dict[str, Any]:
    """Rank B2B lead sources on cost per kept qualified meeting instead of cost per lead.

    Returns, per source and period, total cost, cost per lead, show rate, cost per kept
    meeting, cost per qualified kept meeting, and cost per deal and margin minus cost
    when provided. Invalid rows are reported as a tool error naming each row. Use it to
    compare acquisition channels; it does not check consent or GDPR. A low cost per
    meeting does not prove profitability.
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
def gdpr_offshore_gap_report(
    answers: Annotated[dict[str, Any], Field(
        description=(
            "Your set-up, as a JSON object. Every key is optional and a missing key is "
            "reported as to_verify; unknown keys are ignored with a warning."),
        json_schema_extra=ANSWERS_SCHEMA_DOC)],
    lang: Annotated[Literal["en", "fr"], Field(description="Language of the report text.")] = "en",
) -> dict[str, Any]:
    """GDPR gap report for customer-service processing outsourced outside the EU/EEA.

    Checks the transfer basis (adequacy or Art. 46 safeguards), the transfer impact
    assessment, the Art. 28 processor contract and its twelve clauses, Art. 32 security
    controls and breach notification. Only a JSON true satisfies a check; anything else
    is a gap or "to_verify". Use it for transfers outside the EU; for French
    telemarketing consent use check_telemarketing_consent. Not legal advice and not a
    certification: a report without blocking gap is not a finding of compliance.
    """
    return rgpd.evaluate(answers, lang=lang).to_dict()


@mcp.tool(annotations=LOCAL_READ_ONLY)
def select_least_cost_capable_model(
    catalogue: Annotated[dict[str, Any], Field(
        description="Required capabilities and candidate models with their declared cost evidence.",
        json_schema_extra=CATALOGUE_SCHEMA_DOC)],
) -> dict[str, Any]:
    """Pick, from a supplied catalogue, the model with the lowest declared cost rank
    among those that have every required capability and are available and authorised.

    Returns status "selected" with the comparison basis, "needs_information" naming the
    missing or non-comparable evidence, or "no_candidate_in_catalogue", plus exclusions. Use it to choose
    between AI models from facts you supply; it is unrelated to lead sources. Nothing
    is called, switched or launched; savings are not guaranteed.
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
