CATALOG = [
    {"id": "air_temp", "name": "Air temperature (2 m)", "units": "degC", "sources": ["power"],
     "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat, long-term warming"},
    {"id": "air_temp_max", "name": "Daily maximum air temperature (2 m), monthly mean", "units": "degC",
     "sources": ["power"], "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat extremes"},
    {"id": "precip", "name": "Precipitation", "units": "mm/day", "sources": ["power"],
     "start_year": 1981, "resolution": "~50 km grid", "good_for": "rainfall, drought, floods"},
    {"id": "sea_level", "name": "Sea level (monthly mean, relative to land)", "units": "mm", "sources": ["coops"],
     "start_year": 1900, "resolution": "tide gauge (US coasts)", "good_for": "sea level rise"},
]
