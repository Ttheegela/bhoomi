CATALOG = [
    {"id": "air_temp", "name": "Air temperature (2 m)", "units": "degC", "sources": ["power", "era5", "ghcn"],
     "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat, long-term warming"},
    {"id": "air_temp_max", "name": "Hottest day of the month (2 m air temperature)", "units": "degC",
     "sources": ["power", "era5", "ghcn"], "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat extremes"},
    {"id": "precip", "name": "Precipitation", "units": "mm/day", "sources": ["power", "era5", "ghcn"],
     "start_year": 1981, "resolution": "~50 km grid", "good_for": "rainfall, drought, floods"},
    {"id": "sea_level", "name": "Sea level (monthly mean, relative to land)", "units": "mm", "sources": ["coops"],
     "start_year": 1900, "resolution": "tide gauge (US coasts)", "good_for": "sea level rise"},
]
