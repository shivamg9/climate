import pytest
from pydantic import ValidationError
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DataQuality,
    YearlyResult,
    TrendResult,
    ExportRequest
)

def test_analyze_request_valid():
    """Test valid AnalyzeRequest"""
    request = AnalyzeRequest(
        lat=40.7128,
        lon=-74.0060,
        start_year=1990,
        end_year=2020,
        hazard="heatwave"
    )
    assert request.lat == 40.7128
    assert request.lon == -74.0060
    assert request.start_year == 1990
    assert request.end_year == 2020
    assert request.hazard == "heatwave"

def test_analyze_request_invalid_lat():
    """Test invalid latitude"""
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            lat=95.0,  # Invalid: > 90
            lon=-74.0060,
            start_year=1990,
            end_year=2020,
            hazard="heatwave"
        )

def test_analyze_request_invalid_lon():
    """Test invalid longitude"""
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            lat=40.7128,
            lon=185.0,  # Invalid: > 180
            start_year=1990,
            end_year=2020,
            hazard="heatwave"
        )

def test_analyze_request_invalid_years():
    """Test invalid year range"""
    # start_year >= end_year
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            lat=40.7128,
            lon=-74.0060,
            start_year=2020,
            end_year=2020,  # Equal to start_year
            hazard="heatwave"
        )

    # span less than 10 years
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            lat=40.7128,
            lon=-74.0060,
            start_year=2015,
            end_year=2020,  # Only 5 years
            hazard="heatwave"
        )

def test_analyze_request_invalid_hazard():
    """Test invalid hazard type"""
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            lat=40.7128,
            lon=-74.0060,
            start_year=1990,
            end_year=2020,
            hazard="flood"  # Not allowed
        )

def test_yearly_result():
    """Test YearlyResult model"""
    result = YearlyResult(
        year=2020,
        events=3,
        heatwave_days=15,
        max_duration=5,
        mean_intensity=2.5,
        rolling_avg=12.0
    )
    assert result.year == 2020
    assert result.events == 3
    assert result.heatwave_days == 15
    assert result.max_duration == 5
    assert result.mean_intensity == 2.5
    assert result.rolling_avg == 12.0

def test_trend_result():
    """Test TrendResult model"""
    result = TrendResult(
        slope_per_decade=0.5,
        mk_p=0.03,
        sen_slope=0.4,
        significant=True
    )
    assert result.slope_per_decade == 0.5
    assert result.mk_p == 0.03
    assert result.sen_slope == 0.4
    assert result.significant == True

def test_data_quality():
    """Test DataQuality model"""
    dq = DataQuality(
        missing_percentage=5.5,
        imputed_days=10,
        outliers_removed=2
    )
    assert dq.missing_percentage == 5.5
    assert dq.imputed_days == 10
    assert dq.outliers_removed == 2

def test_export_request():
    """Test ExportRequest model (same validation as AnalyzeRequest)"""
    request = ExportRequest(
        lat=40.7128,
        lon=-74.0060,
        start_year=1990,
        end_year=2020,
        hazard="heatwave"
    )
    assert request.lat == 40.7128
    assert request.lon == -74.0060
    assert request.start_year == 1990
    assert request.end_year == 2020
    assert request.hazard == "heatwave"