import pandas as pd
import numpy as np
from app.hazards import compute_percentile_thresholds, detect_heatwave_events, compute_heatwave_metrics

# Debug the percentile thresholds test
print("=== Debugging compute_percentile_thresholds ===")
dates = pd.date_range('2000-01-01', '2002-12-31', freq='D')
tmax_values = np.sin(np.arange(len(dates)) * 2 * np.pi / 365.25) * 10 + 20
tmax_series = pd.Series(tmax_values, index=dates)

print(f"Date range: {tmax_series.index[0]} to {tmax_series.index[-1]}")
print(f"Temperature range: {tmax_series.min():.2f} to {tmax_series.max():.2f}")
print(f"Temperature mean: {tmax_series.mean():.2f}")

thresholds = compute_percentile_thresholds(
    tmax_series,
    baseline_start=2000,
    baseline_end=2001,
    percentile=95.0,
    window_days=5
)

print(f"Thresholds length: {len(thresholds)}")
print(f"Thresholds range: {thresholds.min():.2f} to {thresholds.max():.2f}")
print(f"Thresholds mean: {thresholds.mean():.2f}")
print(f"Thresholds nanmean: {np.nanmean(thresholds.dropna()):.2f}")

# Debug the heatwave metrics test
print("\n=== Debugging compute_heatwave_metrics ===")
dates = pd.date_range('2019-01-01', '2021-12-31', freq='D')
base_temp = 15 + 10 * np.sin(np.arange(len(dates)) * 2 * np.pi / 365.25)
heatwave_start = pd.Timestamp('2020-07-15')
heatwave_end = pd.Timestamp('2020-07-25')
heatwave_mask = (dates >= heatwave_start) & (dates <= heatwave_end)
tmax_values = base_temp.copy()
tmax_values[heatwave_mask] += 8
tmax_series = pd.Series(tmax_values, index=dates)

print(f"Date range: {tmax_series.index[0]} to {tmax_series.index[-1]}")
print(f"Temperature range: {tmax_series.min():.2f} to {tmax_series.max():.2f}")
print(f"Temperature mean: {tmax_series.mean():.2f}")

result = compute_heatwave_metrics(
    tmax_series,
    baseline_start=1991,
    baseline_end=2020,
    percentile=95.0,
    min_consecutive_days=3
)

print(f"Thresholds mean: {np.nanmean(result['thresholds'].dropna()):.2f}")
print(f"Number of events: {len(result['events'])}")
if result['events']:
    print(f"First event: {result['events'][0]}")
print(f"Yearly stats keys: {list(result['yearly_stats'].keys())}")
if 2020 in result['yearly_stats']:
    print(f"2020 stats: {result['yearly_stats'][2020]}")
else:
    print("2020 not in yearly stats")
    print(f"Available years: {sorted(result['yearly_stats'].keys())}")