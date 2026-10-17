"""End-to-end tests through the real analysis path with a fake DB and fake Open-Meteo."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db import get_database
from app.hazards import compute_heatwave_metrics


class FakeDB:
    """In-memory stand-in for ClimateDatabase that stores and returns data."""

    def __init__(self):
        self.weather = {}
        self.summaries = {}

    async def store_daily_weather(self, cell_key, start_year, end_year,
                                  temperature_data, data_quality=None, fetched_at=None):
        self.weather[(cell_key, start_year, end_year)] = (temperature_data, data_quality)

    async def get_daily_weather(self, cell_key, start_year, end_year):
        return self.weather.get((cell_key, start_year, end_year))

    async def store_hazard_summary(self, cell_key, start_year, end_year, hazard_type,
                                   yearly_results, trend_data, computed_at=None):
        self.summaries[(cell_key, start_year, end_year, hazard_type)] = {
            "yearly_results": yearly_results, "trend_data": trend_data}

    async def get_hazard_summary(self, cell_key, start_year, end_year, hazard_type):
        return self.summaries.get((cell_key, start_year, end_year, hazard_type))

    async def health_check(self):
        return True


def fake_series():
    rng = np.random.default_rng(0)
    idx = pd.date_range("1990-01-01", "2020-12-31", freq="D")
    seasonal = 25 + 8 * np.sin(2 * np.pi * (idx.dayofyear - 100) / 365)
    df = pd.DataFrame({"tmax": seasonal + rng.normal(0, 2, len(idx))}, index=idx)
    quality = {"missing_percentage": 0.0, "imputed_days": 0, "outliers_removed": 0}
    return df, quality


@pytest.fixture
def client():
    fake_db = FakeDB()
    app.dependency_overrides[get_database] = lambda: fake_db
    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main.close_db", new_callable=AsyncMock), \
         patch("app.main.OpenMeteoDataSource.fetch_temperature_data",
               new=AsyncMock(return_value=fake_series())):
        yield TestClient(app)
    app.dependency_overrides.clear()


PARAMS = {"lat": 12.97, "lon": 77.59, "start_year": 1990, "end_year": 2020, "hazard": "heatwave"}


def test_post_analyze(client):
    response = client.post("/api/analyze", json=PARAMS)
    assert response.status_code == 200, response.text
    assert len(response.json()["series"]) == 31


def test_analyze_twice_uses_cache(client):
    first = client.get("/api/analyze", params=PARAMS)
    second = client.get("/api/analyze", params=PARAMS)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["series"] == second.json()["series"]


def test_export_csv(client):
    assert client.get("/api/analyze", params=PARAMS).status_code == 200
    response = client.get("/api/export.csv", params=PARAMS)
    assert response.status_code == 200, response.text


def _series_with(values_by_date, base=20.0):
    idx = pd.date_range("1991-01-01", "2020-12-31", freq="D")
    s = pd.Series(base, index=idx)  # flat, so only the planted days exceed the threshold
    for date, value in values_by_date.items():
        s[date] = value
    return s


def test_heatwave_days_only_counts_event_days():
    # One 2-day hot spell (not an event) and one 3-day event
    hot = {d: 40.0 for d in ["2010-06-01", "2010-06-02",
                             "2010-07-01", "2010-07-02", "2010-07-03"]}
    stats = compute_heatwave_metrics(_series_with(hot))["yearly_stats"][2010]
    assert stats["events"] == 1
    assert stats["heatwave_days"] == 3


def test_gap_breaks_heatwave_run():
    # Two 2-day spells separated by a missing day must not join into one event
    s = _series_with({"2010-07-01": 40.0, "2010-07-02": 40.0,
                      "2010-07-04": 40.0, "2010-07-05": 40.0})
    s["2010-07-03"] = np.nan
    events = compute_heatwave_metrics(s)["events"]
    assert not any(pd.Timestamp("2010-07-01") <= e["start_date"] <= pd.Timestamp("2010-07-05")
                   for e in events)
