import numpy as np
import pandas as pd
from scipy import stats
from typing import List, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

def mann_kendall_test(data: np.ndarray) -> Tuple[float, float]:
    """
    Perform Mann-Kendall trend test.

    Args:
        data: 1D array of data points

    Returns:
        Tuple of (p-value, Sen's slope)
    """
    n = len(data)
    if n < 2:
        return 1.0, 0.0

    # Calculate Mann-Kendall statistic S
    s = 0
    for i in range(n-1):
        for j in range(i+1, n):
            if data[j] > data[i]:
                s += 1
            elif data[j] < data[i]:
                s -= 1

    # Calculate variance of S
    tie_dict = {}
    for val in data:
        tie_dict[val] = tie_dict.get(val, 0) + 1

    tie_values = np.array(list(tie_dict.values()))
    variance_s = (n*(n-1)*(2*n+5) - np.sum(tie_values*(tie_values-1)*(2*tie_values+5))) / 18

    if variance_s == 0:
        return 1.0, 0.0

    # Calculate standardized test statistic Z
    if s > 0:
        z = (s - 1) / np.sqrt(variance_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(variance_s)
    else:
        z = 0

    # Calculate p-value (two-tailed)
    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(abs(z)))

    # Calculate Sen's slope
    slopes = []
    for i in range(n-1):
        for j in range(i+1, n):
            if data[j] != data[i]:  # Avoid division by zero
                slope = (data[j] - data[i]) / (j - i)
                slopes.append(slope)

    if len(slopes) == 0:
        sen_slope = 0.0
    else:
        sen_slope = np.median(slopes)

    return p_value, sen_slope

def linear_regression_trend(years: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
    """
    Calculate linear regression trend (slope per decade).

    Args:
        years: Array of years
        values: Array of values

    Returns:
        Dictionary with slope, intercept, r_value, p_value, std_err
    """
    if len(years) < 2:
        return {'slope': 0.0, 'intercept': 0.0, 'r_value': 0.0, 'p_value': 1.0, 'std_err': 0.0}

    slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)
    slope_per_decade = slope * 10  # Convert to per decade

    return {
        'slope': slope,
        'slope_per_decade': slope_per_decade,
        'intercept': intercept,
        'r_value': r_value,
        'p_value': p_value,
        'std_err': std_err
    }

def compute_rolling_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Compute rolling average with specified window.

    Args:
        values: Array of values
        window: Window size for rolling average

    Returns:
        Array of rolling average values (same length as input, no NaN - uses min_periods=1)
    """
    if len(values) == 0:
        return np.array([], dtype=float)

    return pd.Series(values).rolling(window=window, min_periods=1).mean().values

def analyze_trends(
    years: List[int],
    heatwave_days: List[int],
    event_counts: List[int]
) -> Dict[str, Any]:
    """
    Analyze trends in heatwave metrics.

    Args:
        years: List of years
        heatwave_days: List of heatwave days per year
        event_counts: List of heatwave events per year

    Returns:
        Dictionary with trend analysis results
    """
    years_array = np.array(years)
    heatwave_days_array = np.array(heatwave_days, dtype=float)
    event_counts_array = np.array(event_counts, dtype=float)

    # Remove NaN values for trend analysis
    valid_mask = ~(np.isnan(heatwave_days_array) | np.isnan(event_counts_array))
    if np.sum(valid_mask) < 2:
        # Not enough valid data
        return {
            'heatwave_days': {
                'slope_per_decade': 0.0,
                'mk_p': 1.0,
                'sen_slope': 0.0,
                'significant': False
            },
            'event_count': {
                'slope_per_decade': 0.0,
                'mk_p': 1.0,
                'sen_slope': 0.0,
                'significant': False
            }
        }

    valid_years = years_array[valid_mask]
    valid_heatwave_days = heatwave_days_array[valid_mask]
    valid_event_counts = event_counts_array[valid_mask]

    # Analyze heatwave days trend
    lr_heatwave = linear_regression_trend(valid_years, valid_heatwave_days)
    mk_p_heatwave, sen_slope_heatwave = mann_kendall_test(valid_heatwave_days)
    significant_heatwave = mk_p_heatwave < 0.05

    # Analyze event count trend
    lr_event = linear_regression_trend(valid_years, valid_event_counts)
    mk_p_event, sen_slope_event = mann_kendall_test(valid_event_counts)
    significant_event = mk_p_event < 0.05

    # Compute rolling averages
    rolling_heatwave = compute_rolling_average(heatwave_days_array)
    rolling_event = compute_rolling_average(event_counts_array)

    return {
        'heatwave_days': {
            'slope_per_decade': lr_heatwave['slope_per_decade'],
            'mk_p': mk_p_heatwave,
            'sen_slope': sen_slope_heatwave,
            'significant': significant_heatwave
        },
        'event_count': {
            'slope_per_decade': lr_event['slope_per_decade'],
            'mk_p': mk_p_event,
            'sen_slope': sen_slope_event,
            'significant': significant_event
        },
        'rolling_averages': {
            'heatwave_days': rolling_heatwave.tolist(),
            'event_count': rolling_event.tolist()
        }
    }