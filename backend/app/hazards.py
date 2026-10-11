import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any
from scipy import stats
import logging

logger = logging.getLogger(__name__)

def compute_percentile_thresholds(
    tmax_series: pd.Series,
    baseline_start: int,
    baseline_end: int,
    percentile: float = 95.0,
    window_days: int = 7
) -> pd.Series:
    """
    Compute threshold for each day-of-year using baseline period with ±window_days.

    Args:
        tmax_series: Daily max temperature series with DatetimeIndex
        baseline_start: Start year for baseline period
        baseline_end: End year for baseline period
        percentile: Percentile to compute (default 95th)
        window_days: Window size around each day (default ±7 days)

    Returns:
        Series indexed by day-of-year (1-366) with threshold values
    """
    # Filter to baseline period
    baseline_mask = (tmax_series.index.year >= baseline_start) & (tmax_series.index.year <= baseline_end)
    baseline_tmax = tmax_series[baseline_mask]

    if len(baseline_tmax) == 0:
        logger.error("No baseline data available for 1991-2020 period; thresholds cannot be computed reliably")
        raise ValueError("Baseline period 1991-2020 has no data. Cannot compute percentile thresholds.")

    # Create day-of-year index
    doy_index = baseline_tmax.index.dayofyear

    # For each day-of-year, collect values from ±window_days window
    # Use 366-day circular window to properly handle leap years
    thresholds = pd.Series(index=range(1, 367), dtype=float)

    for target_doy in range(1, 367):
        # Calculate window around target day-of-year using circular 366-day wrap
        window_doy = []
        for offset in range(-window_days, window_days + 1):
            doy = target_doy + offset
            # Circular wrap over 366 days (handles leap day properly)
            if doy < 1:
                doy += 366
            elif doy > 366:
                doy -= 366
            window_doy.append(doy)

        # Extract values within window
        window_mask = doy_index.isin(window_doy)
        window_values = baseline_tmax[window_mask]

        if len(window_values) > 0:
            thresholds[target_doy] = np.percentile(window_values, percentile)
        else:
            # Fallback: use exact day-of-year if window has no data
            exact_doy_mask = doy_index == target_doy
            exact_values = baseline_tmax[exact_doy_mask]
            if len(exact_values) > 0:
                thresholds[target_doy] = np.percentile(exact_values, percentile)
            else:
                thresholds[target_doy] = np.nan

    return thresholds

def detect_heatwave_events(
    tmax_series: pd.Series,
    thresholds: pd.Series,
    min_consecutive_days: int = 3
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Detect heatwave events from temperature series and thresholds.

    Args:
        tmax_series: Daily max temperature series with DatetimeIndex
        thresholds: Threshold values indexed by day-of-year (1-366)
        min_consecutive_days: Minimum consecutive days for heatwave event

    Returns:
        Tuple of (events_list, yearly_stats_dict)
    """
    # Align thresholds with temperature series by day-of-year
    doy_series = tmax_series.index.dayofyear
    threshold_aligned = thresholds[doy_series].values

    # Identify days exceeding threshold
    exceedance = tmax_series.values > threshold_aligned

    # Find consecutive exceedance periods
    events = []
    i = 0
    n = len(exceedance)

    while i < n:
        if exceedance[i]:
            start_idx = i
            while i < n and exceedance[i]:
                i += 1
            end_idx = i - 1
            duration = end_idx - start_idx + 1

            if duration >= min_consecutive_days:
                # Calculate event statistics
                event_tmax = tmax_series.iloc[start_idx:end_idx+1]
                event_thresholds = threshold_aligned[start_idx:end_idx+1]
                exceedance_amounts = event_tmax.values - event_thresholds

                event = {
                    'start_date': tmax_series.index[start_idx],
                    'end_date': tmax_series.index[end_idx],
                    'duration_days': duration,
                    'max_intensity': float(np.max(exceedance_amounts)),
                    'mean_intensity': float(np.mean(exceedance_amounts)),
                    'temperature_values': event_tmax.values.tolist()
                }
                events.append(event)
        else:
            i += 1

    # Compute yearly statistics
    yearly_stats = {}
    years = tmax_series.index.year.unique()

    for year in years:
        year_mask = tmax_series.index.year == year
        year_tmax = tmax_series[year_mask]
        year_doy = year_tmax.index.dayofyear
        year_thresholds = thresholds[year_doy].values
        year_exceedance = year_tmax.values > year_thresholds

        # Count events and total heatwave days in this year
        year_events = []
        j = 0
        m = len(year_exceedance)

        while j < m:
            if year_exceedance[j]:
                start_j = j
                while j < m and year_exceedance[j]:
                    j += 1
                end_j = j - 1
                duration = end_j - start_j + 1

                if duration >= min_consecutive_days:
                    year_events.append({
                        'start_idx': start_j,
                        'end_idx': end_j,
                        'duration': duration
                    })
            else:
                j += 1

        yearly_stats[year] = {
            'events': len(year_events),
            'heatwave_days': np.sum(year_exceedance),
            'max_duration': max([e['duration'] for e in year_events]) if year_events else 0,
            'mean_duration': np.mean([e['duration'] for e in year_events]) if year_events else 0.0,
            'mean_intensity': np.mean([
                np.mean(year_tmax.iloc[e['start_idx']:e['end_idx']+1].values -
                       year_thresholds[e['start_idx']:e['end_idx']+1])
                for e in year_events
            ]) if year_events else 0.0
        }

    return events, yearly_stats

def compute_heatwave_metrics(
    tmax_series: pd.Series,
    baseline_start: int = 1991,
    baseline_end: int = 2020,
    percentile: float = 95.0,
    min_consecutive_days: int = 3
) -> Dict[str, Any]:
    """
    Compute all heatwave metrics for a temperature series.

    Returns:
        Dictionary with thresholds, events, and yearly statistics
    """
    # Compute thresholds using baseline period
    thresholds = compute_percentile_thresholds(
        tmax_series, baseline_start, baseline_end, percentile
    )

    # Detect events and compute yearly stats
    events, yearly_stats = detect_heatwave_events(
        tmax_series, thresholds, min_consecutive_days
    )

    return {
        'thresholds': thresholds,
        'events': events,
        'yearly_stats': yearly_stats
    }