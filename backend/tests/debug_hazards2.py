import pandas as pd
import numpy as np
from app.hazards import compute_percentile_thresholds, detect_heatwave_events

# Debug the heatwave detection more thoroughly
print("=== Detailed Heatwave Detection Debug ===")
dates = pd.date_range('2019-01-01', '2021-12-31', freq='D')
base_temp = 15 + 10 * np.sin(np.arange(len(dates)) * 2 * np.pi / 365.25)
heatwave_start = pd.Timestamp('2020-07-15')
heatwave_end = pd.Timestamp('2020-07-25')
heatwave_mask = (dates >= heatwave_start) & (dates <= heatwave_end)
tmax_values = base_temp.copy()
tmax_values[heatwave_mask] += 8  # 8°C heatwave
tmax_series = pd.Series(tmax_values, index=dates)

print(f"Date range: {tmax_series.index[0]} to {tmax_series.index[-1]}")
print(f"Temperature range: {tmax_series.min():.2f} to {tmax_series.max():.2f}")

# Compute thresholds using 1991-2020 baseline (but our data is 2019-2021)
# This means we'll have partial baseline coverage
thresholds = compute_percentile_thresholds(
    tmax_series,
    baseline_start=1991,
    baseline_end=2020,
    percentile=95.0,
    window_days=5
)

print(f"Thresholds range: {thresholds.min():.2f} to {thresholds.max():.2f}")

# Look specifically at July-August period for 2020
jul_aug_2020 = tmax_series[
    (tmax_series.index >= '2020-07-01') &
    (tmax_series.index <= '2020-08-31')
]
jul_aug_thresholds = thresholds[
    jul_aug_2020.index.dayofyear.values
]

print(f"\nJuly-August 2020:")
print(f"  Temperature range: {jul_aug_2020.min():.2f} to {jul_aug_2020.max():.2f}")
print(f"  Threshold range: {jul_aug_thresholds.min():.2f} to {jul_aug_thresholds.max():.2f}")
print(f"  Exceedance range: {(jul_aug_2020.values - jul_aug_thresholds).min():.2f} to {(jul_aug_2020.values - jul_aug_thresholds).max():.2f}")

# Check for consecutive exceedances
exceedance = jul_aug_2020.values > jul_aug_thresholds
print(f"  Exceedance days: {np.sum(exceedance)} out of {len(exceedance)}")

# Find consecutive periods
consecutive_count = 0
max_consecutive = 0
for i, val in enumerate(exceedance):
    if val:
        consecutive_count += 1
        max_consecutive = max(max_consecutive, consecutive_count)
    else:
        consecutive_count = 0

print(f"  Max consecutive exceedance days: {max_consecutive}")

# Show some specific values around the heatwave period
heatwave_period = tmax_series[
    (tmax_series.index >= '2020-07-10') &
    (tmax_series.index <= '2020-07-30')
]
heatwave_period_thresholds = thresholds[
    heatwave_period.index.dayofyear.values
]

print(f"\nHeatwave period (Jul 10-30, 2020):")
for i, (date, temp, thresh) in enumerate(zip(
    heatwave_period.index,
    heatwave_period.values,
    heatwave_period_thresholds
)):
    exceed = temp > thresh
    print(f"  {date.strftime('%Y-%m-%d')}: temp={temp:.1f}, threshold={thresh:.1f}, exceed={exceed}")

# Now test the detection function
print(f"\n=== Testing detect_heatwave_events ===")
events, yearly_stats = detect_heatwave_events(
    tmax_series,
    thresholds,
    min_consecutive_days=3
)

print(f"Number of events: {len(events)}")
if events:
    for i, event in enumerate(events):
        print(f"  Event {i+1}: {event}")
else:
    print("  No events detected")

print(f"\nYearly stats for 2020:")
if 2020 in yearly_stats:
    print(f"  {yearly_stats[2020]}")
else:
    print("  2020 not in yearly stats")