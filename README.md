# Trend Detective (working name)

NASA Space Apps Challenge 2026 · challenge: *Be An Earth System Trend Detective!*

An AI agent and MCP server that answers "is this really changing here?" from NASA and NOAA Earth data: it picks the right variables for a place, pulls the time series, and tests whether the trend is statistically significant.

## First-time setup (each teammate)

1. Install [uv](https://docs.astral.sh/uv/) and clone the repo.
2. Make your **own** capped dev keys (see `.env.example` for the list), then store them outside the repo:
   `bash ops/dev-secrets.sh` (hidden input, saves to `~/.config/trend-detective/dev.env`, chmod 600).
3. Read `CLAUDE.md` (team rules) and `docs/CONTRACTS.md` (shared data shapes).

## Run locally

```bash
uv sync
uv run pytest -q
# add  --env-file ~/.config/trend-detective/dev.env  after `uv run` when your code needs keys
uv run uvicorn earthtrends.app:app --reload   # API: /api/health · remote MCP: /mcp
uv run trend-detective-mcp                    # MCP over stdio, for Claude Desktop / Claude Code
```

## Use of Super Intelligence (SI)

To be completed for the submission form. Record here where SI tools (e.g. Claude) were used for research, code, data and media, as the Space Apps rules require.
