# kanibal-tools-mcp

[![PyPI](https://img.shields.io/pypi/v/kanibal-tools-mcp)](https://pypi.org/project/kanibal-tools-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/kanibal-tools-mcp)](https://pypi.org/project/kanibal-tools-mcp/)
[![CI](https://github.com/kanibal-studio/kanibal-tools-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/kanibal-studio/kanibal-tools-mcp/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/kanibal-studio/kanibal-tools-mcp/blob/main/LICENSE)

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants four local,
read-only tools from Kanibal Studio (ALTA VISTA360, S.L.U.):

| Tool | What it does |
|---|---|
| `check_telemarketing_consent` | France only: tells whether a consent to telephone canvassing is still valid under décret 2026-662. Fail-closed. |
| `rank_lead_sources_by_kept_meeting` | Ranks B2B lead sources, from CSV text, on cost per kept qualified meeting instead of cost per lead. |
| `gdpr_offshore_gap_report` | GDPR gap report for customer service outsourced outside the EU/EEA. Not legal advice. |
| `select_least_cost_capable_model` | Picks the lowest declared cost rank among the capable, available and authorised models of a supplied catalogue. |

Each tool computes from its arguments only: no network call, no file access, no state
kept between calls. All four are marked read-only and closed-world for MCP clients. They
wrap the published packages [demarchage-consent](https://github.com/kanibal-studio/demarchage-consent),
[cost-per-kept-meeting](https://github.com/kanibal-studio/cost-per-kept-meeting),
[rgpd-offshore-check](https://github.com/kanibal-studio/rgpd-offshore-check) and
[least-cost-capable](https://github.com/kanibal-studio/least-cost-capable).

## Use with Claude Code

```sh
claude mcp add kanibal-tools -- uvx kanibal-tools-mcp
```

## Use with Claude Desktop, Cursor or another MCP client

Add this server to the client's MCP configuration:

```json
{
  "mcpServers": {
    "kanibal-tools": {
      "command": "uvx",
      "args": ["kanibal-tools-mcp"]
    }
  }
}
```

Without `uv`, install it with `pip install kanibal-tools-mcp` and use `kanibal-tools-mcp` as
the command. The server speaks MCP over stdio and needs Python 3.10 or newer.

## Example requests

- "Is a telemarketing consent collected on 2025-11-02 still valid today?"
- "Here is my CSV of lead sources for October: rank them by cost per kept meeting."
- "Prepare a GDPR gap report for our customer service in Tunisia: we have SCCs but no transfer impact assessment."
- "From this model catalogue, which is the cheapest one that can do Python and debugging?"

## Limits

- The consent tool applies French rules only (décret 2026-662). It is a check, not legal advice.
- The GDPR report is a checklist: a report without blocking gap is not a finding of compliance.
- A low cost per kept meeting does not prove profitability.
- The model selection uses only the facts in the catalogue you supply; it does not switch
  models, call providers or guarantee savings.

## Development

```sh
pip install -e ".[dev]"
pytest
```

The tests call every tool through an in-memory MCP client session.

## Project context and license

Prepared by [Kanibal Studio](https://github.com/kanibal-studio), associated with
ALTA VISTA360, S.L.U. Our public sites are [Altavista360](https://altavista360.com),
[Altavista Conseil](https://altavista-conseil.com) and [K-Pulse](https://infos.kanibal-studio.com/).

Licensed under the [MIT License](LICENSE).

<!-- mcp-name: io.github.kanibal-studio/kanibal-tools-mcp -->
