import React, { useState } from 'react';
import './App.css';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { HazardAnalysisControls } from './components/HazardAnalysisControls';
import { HazardAnalysisChart } from './components/HazardAnalysisChart';
import { HazardAnalysisSummary } from './components/HazardAnalysisSummary';
import './styles/map.css';

// Custom icon for the marker
const markerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
  shadowSize: [41, 41]
});

function App() {
  const [location, setLocation] = useState({ lat: 40.7128, lng: -74.0060 });
  const [analysisData, setAnalysisData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const VITE_API_URL = process.env.VITE_API_URL || 'http://localhost:8000';

  const handleMapClick = (e) => {
    setLocation({ lat: e.latlng.lat, lng: e.latlng.lng });
  };

  const handleCitySearch = async (city) => {
    try {
      const response = await fetch(`${VITE_API_URL}/api/geocode?q=${encodeURIComponent(city)}`);
      if (!response.ok) {
        throw new Error('City not found');
      }
      const data = await response.json();
      setLocation({ lat: data.latitude, lng: data.longitude });
    } catch (err) {
      alert('Error finding city: ' + err.message);
    }
  };

  const handleAnalyzeClick = async (params) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${VITE_API_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnalysisData(data);
    } catch (err) {
      setError(err.message);
      setAnalysisData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async (params) => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams({
        lat: params.lat.toString(),
        lon: params.lon.toString(),
        start_year: params.start_year.toString(),
        end_year: params.end_year.toString(),
        hazard: params.hazard
      });
      const response = await fetch(`${VITE_API_URL}/api/export.csv?${queryParams}`, {
        method: 'GET',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      const filename = `heatwave_analysis_${params.lat}_${params.lon}_${params.start_year}_${params.end_year}.csv`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(`Export failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Climate Hazard Trend Analyzer</h1>
        <p>Analyzing historical weather data for heatwave trends</p>
      </header>

      <div className="main-content">
        <div className="sidebar">
          <HazardAnalysisControls
            location={location}
            onCitySearch={handleCitySearch}
            onAnalyzeClick={handleAnalyzeClick}
            onExportClick={handleExportCSV}
            loading={loading}
            error={error}
          />
        </div>

        <div className="map-panel">
          <MapContainer
            center={[location.lat, location.lng]}
            zoom={10}
            style={{ height: '100%', width: '100%' }}
            whenCreated={{
              click: handleMapClick
            }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Marker
              position={[location.lat, location.lng]}
              icon={markerIcon}
            >
              <Popup>
                Selected Location:<br/>
                {location.lat.toFixed(4)}, {location.lng.toFixed(4)}
              </Popup>
            </Marker>
          </MapContainer>
        </div>

        <div className="analysis-panel">
          {!loading && !error && analysisData ? (
            <>
              <HazardAnalysisChart data={analysisData} />
              <HazardAnalysisSummary data={analysisData} />
            </>
          ) : loading ? (
            <div className="loading">Analyzing data...</div>
          ) : error ? (
            <div className="error">Error: {error}</div>
          ) : (
            <div className="placeholder">
              Click "Analyze" to see results
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;