import httpx
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class OpenMeteoDataSource:
    def __init__(self, base_url: str = "https://archive-api.open-meteo.com"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.max_retries = 3

    async def fetch_temperature_data(
        self,
        latitude: float,
        longitude: float,
        start_year: int,
        end_year: int,
        baseline_start: int = 1991,
        baseline_end: int = 2020
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Fetch temperature data from Open-Meteo Historical Archive API.

        Returns:
            Tuple of (DataFrame with temperature data, data_quality dict)
        """
        # We need data from start_year to end_year for analysis
        # Plus baseline period for threshold calculation if not already covered
        fetch_start_year = min(start_year, baseline_start)
        fetch_end_year = max(end_year, baseline_end)

        # Construct API parameters
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{fetch_start_year}-01-01",
            "end_date": f"{fetch_end_year}-12-31",
            "daily": "temperature_2m_max",
            "timezone": "auto"
        }

        # Fetch data with retries
        data_quality = {
            "missing_percentage": 0.0,
            "imputed_days": 0,
            "outliers_removed": 0
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(self.base_url + "/v1/archive", params=params)
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [429, 500, 502, 503, 504] and attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"HTTP {e.response.status_code}, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise
                except httpx.RequestError as e:
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request error, retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise
            else:
                # If we exhausted retries
                raise Exception("Failed to fetch data after maximum retries")

        # Parse response
        data = response.json()
        if "daily" not in data or "temperature_2m_max" not in data["daily"]:
            raise ValueError("Invalid response from Open-Meteo API")

        # Create DataFrame
        df = pd.DataFrame({
            "date": pd.to_datetime(data["daily"]["time"]),
            "tmax": data["daily"]["temperature_2m_max"]
        })
        df.set_index("date", inplace=True)

        # Data cleaning
        df, cleaning_stats = self._clean_temperature_data(df)
        data_quality.update(cleaning_stats)

        return df, data_quality

    def _clean_temperature_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Clean temperature data: handle missing values, remove outliers, ensure continuity.

        Returns:
            Tuple of (cleaned DataFrame, cleaning statistics)
        """
        initial_len = len(df)
        stats = {
            "missing_percentage": 0.0,
            "imputed_days": 0,
            "outliers_removed": 0
        }

        # Check for physically implausible values
        plausible_min = -90.0
        plausible_max = 60.0
        outlier_mask = (df["tmax"] < plausible_min) | (df["tmax"] > plausible_max)
        outliers_removed = outlier_mask.sum()
        df.loc[outlier_mask, "tmax"] = np.nan
        stats["outliers_removed"] = int(outliers_removed)

        # Check for missing values
        missing_mask = df["tmax"].isna()
        missing_count = missing_mask.sum()
        stats["missing_percentage"] = round((missing_count / initial_len) * 100, 2)

        # Interpolate gaps <= 2 days
        if missing_count > 0:
            # Mark consecutive missing values
            missing_groups = missing_mask.ne(missing_mask.shift()).cumsum()
            group_sizes = missing_mask.groupby(missing_groups).transform('sum')

            # Only interpolate gaps of size <= 2
            interpolate_mask = missing_mask & (group_sizes <= 2)
            df.loc[interpolate_mask, "tmax"] = df.loc[interpolate_mask, "tmax"].interpolate(method='linear')
            stats["imputed_days"] = int(interpolate_mask.sum())

            # For remaining missing values (>2 day gaps), leave as NaN but could mark as missing
            # For simplicity, we'll leave them as NaN and they'll affect analysis

        # Ensure daily continuity by checking for duplicate dates or large gaps
        # (Open-Meteo should return continuous daily data, but we'll verify)
        expected_dates = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq='D'
        )
        missing_dates = expected_dates.difference(df.index)

        if len(missing_dates) > 0:
            logger.warning(f"Found {len(missing_dates)} missing dates in timeline")
            # Add missing dates with NaN values
            missing_df = pd.DataFrame(index=missing_dates, columns=df.columns)
            missing_df.index.name = 'date'
            df = pd.concat([df, missing_df]).sort_index()

        final_len = len(df)
        if final_len != initial_len:
            logger.info(f"Data length changed from {initial_len} to {final_len} after cleaning")

        return df, stats

class CityGeocoder:
    def __init__(self, geocode_url: str = "https://geocoding-api.open-meteo.com/v1/search"):
        self.geocode_url = geocode_url
        self.timeout = httpx.Timeout(10.0)

    async def geocode_city(self, city_name: str) -> Optional[Dict[str, Any]]:
        """
        Geocode a city name using Open-Meteo geocoding API.

        Returns:
            Dictionary with latitude, longitude, name, etc. or None if not found
        """
        if len(city_name) < 2:
            return None

        params = {
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(self.geocode_url, params=params)
                response.raise_for_status()
                data = response.json()

                if "results" in data and len(data["results"]) > 0:
                    result = data["results"][0]
                    return {
                        "latitude": result["latitude"],
                        "longitude": result["longitude"],
                        "name": result["name"],
                        "country": result.get("country", ""),
                        "admin1": result.get("admin1", "")
                    }
                return None
            except Exception as e:
                logger.error(f"Geocoding error for '{city_name}': {e}")
                return None