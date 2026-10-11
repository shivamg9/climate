import pytest
import pandas as pd
from app.data_source import OpenMeteoDataSource, CityGeocoder

def test_open_meteo_data_source_init():
    """Test OpenMeteoDataSource initialization"""
    ds = OpenMeteoDataSource()
    assert ds.base_url == "https://archive-api.open-meteo.com"
    assert ds.timeout is not None
    assert ds.max_retries == 3

def test_city_geocoder_init():
    """Test CityGeocoder initialization"""
    geocoder = CityGeocoder()
    assert geocoder.geocode_url == "https://geocoding-api.open-meteo.com/v1/search"
    assert geocoder.timeout is not None

# We won't test the actual API calls since they require network access
# and we want to keep unit tests fast and independent of external services