import React, { useState, useCallback, useRef, useEffect } from 'react';
import './HazardAnalysisControls.css';

export const HazardAnalysisControls = ({
  location,
  onCitySearch,
  onAnalyzeClick,
  onExportClick,
  loading,
  error
}) => {
  const [citySearch, setCitySearch] = useState('');
  const [hazard, setHazard] = useState('heatwave');
  const [startYear, setStartYear] = useState(1990);
  const [endYear, setEndYear] = useState(2020);

  // Debounce ref for analyze click
  const debounceTimerRef = useRef(null);
  const debouncedAnalyzeClick = useCallback((params) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      onAnalyzeClick(params);
    }, 300); // 300ms debounce
  }, [onAnalyzeClick]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleAnalyzeClick = useCallback(() => {
    const params = {
      lat: location.lat,
      lon: location.lng,
      start_year: startYear,
      end_year: endYear,
      hazard
    };
    debouncedAnalyzeClick(params);
  }, [location.lat, location.lng, startYear, endYear, hazard, debouncedAnalyzeClick]);

  const handleExportClick = useCallback(() => {
    const params = {
      lat: location.lat,
      lon: location.lng,
      start_year: startYear,
      end_year: endYear,
      hazard
    };
    onExportClick(params);
  }, [location.lat, location.lng, startYear, endYear, hazard, onExportClick]);

  return (
    <div className="controls-panel">
      <div className="controls-section">
        <h3>Location Selection</h3>
        <div className="city-search">
          <form onSubmit={(e) => {
            e.preventDefault();
            onCitySearch(citySearch);
          }}>
            <input
              type="text"
              value={citySearch}
              onChange={(e) => setCitySearch(e.target.value)}
              placeholder="Enter city name (e.g., 'New York')"
              disabled={loading}
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Searching...' : 'Search City'}
            </button>
          </form>
        </div>
        <p>Current location: {location.lat.toFixed(4)}, {location.lng.toFixed(4)}</p>
      </div>

      <div className="controls-section">
        <h3>Analysis Parameters</h3>
        <div className="parameter-group">
          <label>Hazard Type:</label>
          <select
            value={hazard}
            onChange={(e) => setHazard(e.target.value)}
            disabled={loading}
          >
            <option value="heatwave">Heatwave</option>
            <option value="drought" disabled>Drought (Coming Soon)</option>
            <option value="flood" disabled>Flood (Coming Soon)</option>
          </select>
        </div>

        <div className="parameter-group">
          <label>Start Year:</label>
          <input
            type="number"
            value={startYear}
            onChange={(e) => setStartYear(Math.max(1950, parseInt(e.target.value) || 1950))}
            min="1950"
            max={new Date().getFullYear() - 1}
            disabled={loading}
          />
        </div>

        <div className="parameter-group">
          <label>End Year:</label>
          <input
            type="number"
            value={endYear}
            onChange={(e) => setEndYear(Math.max(parseInt(e.target.value) || startYear + 10, startYear + 10))}
            min={startYear + 10}
            max={new Date().getFullYear() - 1}
            disabled={loading}
          />
          <small>Minimum 10-year span required</small>
        </div>
      </div>

      <div className="controls-section">
        <h3>Actions</h3>
        <button
          onClick={handleAnalyzeClick}
          disabled={loading}
          className="primary-button"
        >
          {loading ? 'Analyzing...' : 'Analyze Climate Hazard'}
        </button>

        <button
          onClick={handleExportClick}
          disabled={loading}
          className="secondary-button"
        >
          {loading ? 'Exporting...' : 'Download CSV'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
};