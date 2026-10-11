import pytest
import numpy as np
from app.trends import mann_kendall_test, linear_regression_trend, analyze_trends

def test_mann_kendall_test():
    """Test Mann-Kendall test with known data"""
    # Test with increasing data (should show positive trend)
    increasing_data = np.array([1, 2, 3, 4, 5])
    p_value, sen_slope = mann_kendall_test(increasing_data)
    assert p_value < 0.05  # Should be significant
    assert sen_slope > 0   # Should have positive slope

    # Test with decreasing data (should show negative trend)
    decreasing_data = np.array([5, 4, 3, 2, 1])
    p_value, sen_slope = mann_kendall_test(decreasing_data)
    assert p_value < 0.05  # Should be significant
    assert sen_slope < 0   # Should have negative slope

    # Test with constant data (should show no trend)
    constant_data = np.array([3, 3, 3, 3, 3])
    p_value, sen_slope = mann_kendall_test(constant_data)
    assert p_value >= 0.05  # Should not be significant
    assert sen_slope == 0   # Should have zero slope

def test_linear_regression_trend():
    """Test linear regression trend calculation"""
    years = np.array([2000, 2001, 2002, 2003, 2004])
    values = np.array([10, 12, 14, 16, 18])  # Increasing by 2 per year

    result = linear_regression_trend(years, values)
    assert abs(result['slope'] - 2.0) < 0.001  # Slope should be 2
    assert abs(result['slope_per_decade'] - 20.0) < 0.001  # Per decade should be 20
    assert result['p_value'] < 0.05  # Should be significant

def test_analyze_trends():
    """Test trend analysis function"""
    years = list(range(2000, 2010))
    heatwave_days = [2, 3, 5, 4, 6, 8, 7, 9, 10, 12]  # Generally increasing
    event_counts = [1, 1, 2, 1, 2, 3, 2, 3, 3, 4]    # Generally increasing

    result = analyze_trends(years, heatwave_days, event_counts)

    # Check structure
    assert 'heatwave_days' in result
    assert 'event_count' in result
    assert 'rolling_averages' in result

    # Check that we got reasonable values
    assert 'slope_per_decade' in result['heatwave_days']
    assert 'mk_p' in result['heatwave_days']
    assert 'sen_slope' in result['heatwave_days']
    assert 'significant' in result['heatwave_days']

    # With increasing data, we should see positive slope
    assert result['heatwave_days']['slope_per_decade'] > 0
    assert result['event_count']['slope_per_decade'] > 0

def test_compute_rolling_average():
    """Test rolling average computation"""
    from app.trends import compute_rolling_average

    values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    result = compute_rolling_average(values, window=3)

    # With min_periods=1 and trailing window (no center), no NaN values
    # Index 0: average of [1] -> 1.0
    # Index 1: average of [1, 2] -> 1.5
    # Index 2: average of [1, 2, 3] -> 2.0
    # Index 3: average of [2, 3, 4] -> 3.0
    # etc.
    assert not np.isnan(result[0])  # First value is not NaN
    assert not np.isnan(result[-1])  # Last value is not NaN

    # Values should be correct for trailing window with min_periods=1
    assert result[0] == 1.0  # average of [1]
    assert result[1] == 1.5  # average of [1, 2]
    assert result[2] == 2.0  # average of [1, 2, 3]
    assert result[3] == 3.0  # average of [2, 3, 4]
    assert result[5] == 5.0  # average of [4, 5, 6]
    assert result[9] == 9.0  # average of [8, 9, 10]