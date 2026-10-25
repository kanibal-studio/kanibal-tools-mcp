"""The four tools, called through a real MCP client session held in memory."""

from __future__ import annotations

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

from kanibal_tools_mcp import __version__
from kanibal_tools_mcp.server import mcp

CSV = """source,period,cost_media,cost_data,cost_tools,cost_human_time,cost_other,leads,meetings_booked,meetings_kept,meetings_qualified_kept,deals_closed,gross_margin
Example Purchased Lists,2026-10,0,2400,300,1800,0,1500,60,33,9,1,2500
Example Partner Referrals,2026-10,0,0,150,900,1650,60,24,21,15,4,11000
"""

COST = {"metric": "API input-token cost", "unit": "USD per million input tokens",
        "workload": "same coding task mix", "window": "2026-10-01 to 2026-10-11",
        "source": "synthetic example", "as_of": "2026-10-11"}
CATALOGUE = {
    "required_capabilities": ["python", "debugging"],
    "models": [
        {"id": "economy-text", "available": True, "authorized": True,
         "capabilities": ["python"], "capabilities_complete": True,
         "cost": {**COST, "relative_rank": 1}},
        {"id": "standard-code", "available": True, "authorized": True,
         "capabilities": ["python", "debugging"], "capabilities_complete": True,
         "cost": {**COST, "relative_rank": 2}},
    ],
}


def _call(name: str, arguments: dict) -> tuple[bool, object]:
    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(name, arguments)
            text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
            payload = result.structuredContent
            if payload is None and not result.isError:
                payload = json.loads(text)
            return result.isError, (text if result.isError else payload)

    return asyncio.run(run())


def _unwrap(payload: object) -> dict:
    # FastMCP wraps non-object structured output as {"result": ...}.
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def test_lists_exactly_four_read_only_local_tools():
    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(run())
    assert sorted(t.name for t in tools) == [
        "check_telemarketing_consent",
        "gdpr_offshore_gap_report",
        "rank_lead_sources_by_kept_meeting",
        "select_least_cost_capable_model",
    ]
    for tool in tools:
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is False
        assert tool.annotations.destructiveHint is False
        assert tool.description and len(tool.description) > 40


def test_consent_statuses_are_fail_closed():
    error, valid = _call(
        "check_telemarketing_consent",
        {"collected_at": "2026-03-01", "now": "2026-10-01"},
    )
    assert not error and _unwrap(valid)["status"] == "valide"
    assert _unwrap(valid)["days_remaining"] > 0

    _, expired = _call(
        "check_telemarketing_consent",
        {"collected_at": "2025-01-01", "now": "2026-10-01"},
    )
    assert _unwrap(expired)["status"] == "expire"

    _, missing = _call("check_telemarketing_consent", {"collected_at": "not a date"})
    assert _unwrap(missing)["status"] == "preuve_manquante"

    _, revoked = _call(
        "check_telemarketing_consent",
        {"collected_at": "2026-09-01", "revoked_at": "oui", "now": "2026-10-01"},
    )
    assert _unwrap(revoked)["status"] == "revoque"


def test_ranking_puts_referrals_before_purchased_lists():
    error, payload = _call("rank_lead_sources_by_kept_meeting", {"csv_text": CSV})
    assert not error
    results = _unwrap(payload)["results"]
    assert [r["source"] for r in results][0] == "Example Partner Referrals"


def test_invalid_csv_is_a_named_tool_error_not_a_crash():
    error, text = _call("rank_lead_sources_by_kept_meeting", {"csv_text": "a,b\n1,2\n"})
    assert error and "invalid CSV" in text


def test_gdpr_report_keeps_disclaimer_and_flags_unanswered_items():
    error, payload = _call(
        "gdpr_offshore_gap_report",
        {"answers": {"destination_country": "Tunisia"}, "lang": "fr"},
    )
    report = _unwrap(payload)
    assert not error and report["lang"] == "fr"
    assert report["disclaimer"]
    # Unanswered items are "to_verify", never compliant, and still block (fail-closed).
    assert report["summary"]["result"] == "blocking_gap"
    assert len(report["summary"]["blocking_to_verify"]) > 0


def test_model_selection_uses_the_capability_filter():
    error, payload = _call("select_least_cost_capable_model", {"catalogue": CATALOGUE})
    assert not error and _unwrap(payload)["selected"] == "standard-code"


def test_version_is_exposed_to_clients():
    assert __version__ == "0.1.1"
    assert mcp._mcp_server.version == __version__


def _tools_by_name():
    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            return {t.name: t for t in (await client.list_tools()).tools}

    return asyncio.run(run())


def test_every_parameter_is_described_and_input_formats_are_in_the_schema():
    tools = _tools_by_name()
    for tool in tools.values():
        for name, prop in tool.inputSchema["properties"].items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"
    answers = tools["gdpr_offshore_gap_report"].inputSchema["properties"]["answers"]
    assert {"safeguards", "art28_contract", "security_controls", "tia_documented"} <= set(answers["properties"])
    assert len(answers["properties"]["art28_contract"]["properties"]["clauses"]["properties"]) == 12
    catalogue = tools["select_least_cost_capable_model"].inputSchema["properties"]["catalogue"]
    assert catalogue["required"] == ["required_capabilities", "models"]
    assert "meetings_qualified_kept" in tools["rank_lead_sources_by_kept_meeting"].inputSchema["properties"]["csv_text"]["description"]


def test_each_description_points_away_from_its_siblings():
    tools = _tools_by_name()
    assert "gdpr_offshore_gap_report" in tools["check_telemarketing_consent"].description
    assert "check_telemarketing_consent" in tools["gdpr_offshore_gap_report"].description
    assert "does not check consent or GDPR" in tools["rank_lead_sources_by_kept_meeting"].description
    assert "unrelated to lead sources" in tools["select_least_cost_capable_model"].description


def test_documented_schema_does_not_coerce_a_string_true_into_compliance():
    """The answers schema documents booleans but must not coerce "true" (fail-closed)."""
    def tia_status(value):
        error, payload = _call(
            "gdpr_offshore_gap_report",
            {"answers": {"destination_country": "Tunisia", "safeguards": ["scc"], "tia_documented": value}},
        )
        assert not error
        findings = _unwrap(payload)["findings"]
        return next(f for f in findings if f["id"] == "TRANSFER-TIA")["status"]

    assert tia_status(True) == "ok"
    assert tia_status("true") == "to_verify"
