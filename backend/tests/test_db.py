import pytest
from app.db import ClimateDatabase

def test_climate_database_init():
    """Test ClimateDatabase initialization"""
    # Test with dummy values
    db = ClimateDatabase("mongodb://localhost:27017", "test_db")
    assert db.mongodb_uri == "mongodb://localhost:27017"
    assert db.database_name == "test_db"
    assert db.client is None
    assert db.db is None

# We won't test actual database operations since they require a running MongoDB instance