import React from 'react';

export const HazardAnalysisSummary = ({ data }) => {
  if (!data) return null;

  const { region, params, series, trend, insights, caveats, data_quality } = data;

  // Calculate some summary stats
  const totalEvents = series.reduce((sum, year) => sum + year.events, 0);
  const totalHeatwaveDays = series.reduce((sum, year) => sum + year.heatwave_days, 0);
  const avgEventsPerYear = totalEvents / series.length || 0;
  const avgHeatwaveDaysPerYear = totalHeatwaveDays / series.length || 0;

  // Get first and last decade averages for comparison
  const firstDecadeAvg = series.slice(0, Math.min(10, series.length))
    .reduce((sum, year) => sum + year.heatwave_days, 0) / Math.min(10, series.length) || 0;
  const lastDecadeAvg = series.slice(Math.max(0, series.length - 10))
    .reduce((sum, year) => sum + year.heatwave_days, 0) / Math.min(10, series.length) || 0;
  const pctChange = firstDecadeAvg > 0
    ? ((lastDecadeAvg - firstDecadeAvg) / firstDecadeAvg * 100).toFixed(1)
    : 'N/A';

  return (
    <div className="summary-panel">
      <div className="summary-section">
        <h2>Analysis Summary for {region}</h2>
        <p>
          Period: {params.start_year} - {params.end_year} ({params.end_year - params.start_year + 1} years)
        </p>
      </div>

      <div className="summary-section">
        <h3>Key Metrics</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <h4>Total Heatwave Events</h4>
            <p className="metric-value">{totalEvents}</p>
          </div>
          <div className="metric-card">
            <h4>Total Heatwave Days</h4>
            <p className="metric-value">{totalHeatwaveDays}</p>
          </div>
          <div className="metric-card">
            <h4>Avg Events/Year</h4>
            <p className="metric-value">{avgEventsPerYear.toFixed(1)}</p>
          </div>
          <div className="metric-card">
            <h4>Avg Days/Year</h4>
            <p className="metric-value">{avgHeatwaveDaysPerYear.toFixed(1)}</p>
          </div>
        </div>
      </div>

      <div className="summary-section">
        <h3>Trend Analysis</h3>
        <div className="trend-info">
          <p>
            <strong>Trend (per decade):</strong> {trend.slope_per_decade.toFixed(3)} days
          </p>
          <p>
            <strong>Mann-Kendall p-value:</strong> {trend.mk_p.toFixed(4)}
            <span className={trend.significant ? 'trend-significant' : 'trend-not-significant'}>
              {trend.significant ? '(Significant)' : '(Not Significant)'}
            </span>
          </p>
          <p>
            <strong>Sen's Slope:</strong> {trend.sen_slope.toFixed(3)}
          </p>
        </div>
      </div>

      <div className="summary-section">
        <h3>Insights</h3>
        <ul className="insights-list">
          {insights.map((insight, index) => (
            <li key={index}>{insight}</li>
          ))}
          {firstDecadeAvg > 0 && lastDecadeAvg > 0 && (
            <li>
              Heatwave days changed by {pctChange}% from first to last decade
            </li>
          )}
        </ul>
      </div>

      <div className="summary-section">
        <h3>Data Quality</h3>
        <p>
          Missing data: {data_quality.missing_percentage.toFixed(1)}%
        </p>
        <p>
          Days imputed (gaps ≤2 days): {data_quality.imputed_days}
        </p>
        <p>
          Outliers removed: {data_quality.outliers_removed}
        </p>
      </div>

      <div className="summary-section">
        <h3>Caveats & Limitations</h3>
        <ul className="caveats-list">
          {caveats.map((caveat, index) => (
            <li key={index}>{caveat}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};