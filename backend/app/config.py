import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "climate_db")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    cache_ttl_days: int = int(os.getenv("CACHE_TTL_DAYS", "30"))
    baseline_start_year: int = 1991
    baseline_end_year: int = 2020
    heatwave_threshold_percentile: float = 95.0
    heatwave_min_consecutive_days: int = 3
    temperature_plausible_min: float = -90.0
    temperature_plausible_max: float = 60.0
    max_gap_interpolation_days: int = 2
    open_meteo_base_url: str = "https://archive-api.open-meteo.com"
    open_meteo_geocode_url: str = "https://geocoding-api.open-meteo.com/v1/search"

    class Config:
        env_file = ".env"

settings = Settings()