# Contracts (frozen at hour 0, Sat 2026-11-14)

Every lane codes against these shapes, so nobody waits on anybody. To change one after the freeze: open a PR that edits only this file (plus the code that must follow), and tag every lane that uses the shape.

Numbers in the examples are illustrative, not real results.

## Source ids

One variable can come from several sources. Tools take an optional `source`; results say which one they used.

| id | Dataset | Covers |
|---|---|---|
| `power` | NASA POWER (MERRA-2), https://power.larc.nasa.gov/ | any point, 1981 on |
| `era5` | ERA5 reanalysis via Open-Meteo archive, https://open-meteo.com/ | any point, 1940 on |
| `ghcn` | NOAA NCEI GHCN-Daily, nearest station, https://www.ncei.noaa.gov/ | weather stations worldwide |
| `coops` | NOAA CO-OPS tide gauges, nearest station, https://tidesandcurrents.noaa.gov/ | US coasts |
| `grace` | GRACE/GRACE-FO JPL mascon CRI RL06.3 v4 (PO.DAAC), https://podaac.jpl.nasa.gov/ | land, 2002 on |

## TimeSeries — data lane produces, stats lane consumes

```json
{
  "variable": "air_temp",
  "units": "degC",
  "freq": "monthly",
  "place": {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22},
  "times": ["1981-01", "1981-02", "..."],
  "values": [24.1, 25.3, null],
  "source": {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"},
  "notes": ["Grid cell about 50 km wide, not a single station."]
}
```

- `freq`: `"daily"` | `"monthly"` | `"annual"`. `times` are ISO strings at that resolution.
- `values`: same length as `times`; `null` for missing.
- For a station source (`ghcn`, `coops`), `place.name` is the station name and `notes` says how far it is from the point asked for.

## TrendResult — stats lane produces, agent and UI lanes consume

```json
{
  "variable": "air_temp",
  "units": "degC",
  "place": {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22},
  "period": {"start": "1981-01", "end": "2025-12"},
  "n": 540,
  "deseasonalized": true,
  "method": "mann_kendall_sen",
  "slope_per_decade": 0.21,
  "ci_low": 0.12,
  "ci_high": 0.30,
  "p_value": 0.003,
  "autocorrelation_adjusted": true,
  "verdict": "rising",
  "source": {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"},
  "caveats": ["Grid cell about 50 km wide, not a single station."]
}
```

- `verdict`: `"rising"` | `"falling"` | `"no_clear_change"` (p ≥ 0.05 or CI crosses 0).
- `slope_per_decade` is in `units` per decade.

## Variable catalog entry — data lane maintains

```json
{"id": "air_temp", "name": "Air temperature (2 m)", "units": "degC", "sources": ["power", "era5", "ghcn"], "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat, long-term warming"}
```

- `sources`: source ids that have this variable. The first one is the default.

## MCP tools — agent lane exposes (names and inputs are the contract)

| Tool | Inputs | Returns |
|---|---|---|
| `list_variables` | none | list of catalog entries |
| `get_series` | `variable`, `lat`, `lon`, `start?`, `end?`, `source?` | `TimeSeries` |
| `detect_trend` | `variable`, `lat`, `lon`, `start?`, `end?`, `source?` | `TrendResult` |

- `source` left out: use the variable's default source. A source the variable doesn't have, an unknown variable, a bad lat/lon, or a point with no data gives a clear 4xx error, never a 500.

The UI calls the same functions through FastAPI routes under `/api/`, so the UI and outside agents see identical results.
