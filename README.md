# Trend Detective (working name)

NASA Space Apps Challenge 2026 · challenge: *Be An Earth System Trend Detective!*

An AI agent and MCP server that answers "is this really changing here?" from NASA and NOAA Earth data: it picks the right variables for a place, pulls the time series, and tests whether the trend is statistically significant.

Flagship demo: coastal sea level (is the water really rising at my town?). Also heat and groundwater for dense cities. Audience: students and the public.

**Live:** https://trend-detective-six.vercel.app · health `/api/health` · MCP endpoint `/mcp/` (only a `ping` tool for now)

## Connect your agent

```bash
claude mcp add --transport http trend-detective https://trend-detective-six.vercel.app/mcp/
```

Any MCP client that speaks streamable HTTP works the same way. Keep the trailing slash.

## Team and workflow

| Who | Lane |
|---|---|
| Tarun (@Ttheegela) | integration, merges, deploys |
| Sairam (@sairam782) | data, stats, agent, UI + story |

Lanes: data, stats, agent, UI + story (see `CLAUDE.md`). Every change goes issue, then branch, then pull request; `main` only accepts PRs that pass the tests and the secrets scan. Shared data shapes live in `docs/CONTRACTS.md`.

## First-time setup (each teammate)

1. Install [uv](https://docs.astral.sh/uv/) and clone the repo.
2. Make your **own** capped dev keys (see `.env.example` for the list), then store them outside the repo:
   `bash ops/dev-secrets.sh` (hidden input, saves to `~/.config/trend-detective/dev.env`, chmod 600).
3. Read `CLAUDE.md` (team rules) and `docs/CONTRACTS.md` (shared data shapes).
4. Check your keys: `uv run --env-file ~/.config/trend-detective/dev.env python -c "from earthtrends.app import health_keys; print(health_keys())"` (prints true/false only, never values).

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
