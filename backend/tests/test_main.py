import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_database, ClimateDatabase
from unittest.mock import AsyncMock, patch

@pytest.fixture
def client():
    # Create a mock database
    mock_db = AsyncMock(spec=ClimateDatabase)
    mock_db.get_hazard_summary = AsyncMock(return_value=None)
    mock_db.get_daily_weather = AsyncMock(return_value=[])
    mock_db.store_daily_weather = AsyncMock()
    mock_db.store_hazard_summary = AsyncMock()
    mock_db.health_check = AsyncMock(return_value=True)

    # Override the dependency
    app.dependency_overrides[get_database] = lambda: mock_db

    # Patch the init_db and close_db functions to do nothing
    with patch('app.main.init_db', new_callable=AsyncMock), \
         patch('app.main.close_db', new_callable=AsyncMock):
        yield TestClient(app)
    app.dependency_overrides.clear()

def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data

def test_analyze_endpoint_validation(client):
    """Test validation of analyze endpoint"""
    # Test invalid latitude
    response = client.post("/api/analyze", json={
        "lat": 95.0,  # Invalid
        "lon": -74.0060,
        "start_year": 1990,
        "end_year": 2020,
        "hazard": "heatwave"
    })
    assert response.status_code == 422

    # Test invalid longitude
    response = client.post("/api/analyze", json={
        "lat": 40.7128,
        "lon": 185.0,  # Invalid
        "start_year": 1990,
        "end_year": 2020,
        "hazard": "heatwave"
    })
    assert response.status_code == 422

    # Test invalid year range (too short)
    response = client.post("/api/analyze", json={
        "lat": 40.7128,
        "lon": -74.0060,
        "start_year": 2015,
        "end_year": 2020,  # Only 5 years
        "hazard": "heatwave"
    })
    assert response.status_code == 422

    # Test invalid hazard
    response = client.post("/api/analyze", json={
        "lat": 40.7128,
        "lon": -74.0060,
        "start_year": 1990,
        "end_year": 2020,
        "hazard": "flood"  # Not allowed
    })
    assert response.status_code == 422

def test_geocode_endpoint_validation():
    """Test validation of geocode endpoint"""
    client = TestClient(app)

    # Test query too short
    response = client.get("/api/geocode?q=a")
    assert response.status_code == 422

    # Test valid query (will fail due to no network, but should validate)
    response = client.get("/api/geocode?q=london")
    # This might return 500 due to network issues, but not 422 (validation error)
    assert response.status_code != 422