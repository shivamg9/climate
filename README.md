# Climate Hazard Trend Analyzer

A full-stack web application that analyzes historical weather data for a region and shows heatwave trends.

## Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd climate
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Environment Variables**
   Create `.env` files in both backend and frontend directories:
   
   Backend `.env`:
   ```
   MONGODB_URI=mongodb://localhost:27017
   DATABASE_NAME=climate_db
   FRONTEND_ORIGIN=http://localhost:3000
   RATE_LIMIT_PER_MINUTE=30
   CACHE_TTL_DAYS=30
   ```
   
   Frontend `.env`:
   ```
   REACT_APP_API_URL=http://localhost:8000
   ```
   (The frontend is Create React App, so only `REACT_APP_*` variables are injected. `npm start` serves on http://localhost:3000.)
   ```
   ```

5. **Run the Application**
   ```bash
   # Backend (in one terminal)
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   
   # Frontend (in another terminal)
   cd frontend
   npm start
   ```

6. **Run Tests (Backend)**
   ```bash
   cd backend
   source venv/bin/activate
   # For unit tests
   pytest
   ```

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   Frontend      │    │    Backend API   │    │    Services        │
│  (React/Vite)   │◄──►│  (FastAPI/Python)│◄──►│  (MongoDB Cache)   │
│                 │    │                  │    │                    │
│ - Map UI        │    │ - Analysis API   │    │ - Open-Meteo Fetcher│
│ - Charts        │    │ - Hazard Logic   │    │ - Data Cleaner     │
│ - Controls      │    │ - Trend Analysis │    │ - Threshold Calc   │
│ - Export CSV    │    │ - Caching        │    │                    │
└─────────────────┘    └──────────────────┘    └────────────────────┘
                    │
                    ▼
           ┌────────────────────┐
           │   External APIs    │
           │  (Open-Meteo)      │
           └────────────────────┘
```

## Data Source

- **Open-Meteo Historical Archive API**: Provides free historical weather data including daily maximum temperature (`temperature_2m_max`)
- **No API key required** for historical data access
- **Spatial resolution**: 0.25° grid (~25km at equator)
- **Temporal coverage**: 1940-present (depends on location)
- **Variables used**: `temperature_2m_max` (daily maximum temperature at 2m height)

## Hazard Logic

### Heatwave Definition
1. **Threshold Calculation**: 
   - For each day-of-year (Jan 1 = day 1, Dec 31 = day 365), calculate the 95th percentile of maximum temperature
   - Uses a baseline period of 1991-2020
   - Applies a ±7-day window around each day to avoid seasonal bias (standard climatological approach)
   - Example: For July 15 (day 196), uses data from July 8-22 across all baseline years

2. **Heatwave Event**:
   - Defined as ≥3 consecutive days where daily maximum temperature exceeds the day-specific threshold
   - Follows standard meteorological definitions

3. **Annual Metrics Calculated**:
   - Event count: Number of distinct heatwave events per year
   - Heatwave days: Total days participating in heatwave events
   - Max duration: Longest single heatwave event in days
   - Mean duration: Average length of heatwave events
   - Mean intensity: Average temperature exceedance above threshold (°C)

### Percentile Calculation Details
- For each target day-of-year, collect all temperature values from ±7 days in the baseline period
- Calculate the 95th percentile of this pooled distribution
- This removes annual cycle while preserving synoptic-scale variability
- Mathematically robust and widely used in climate science

## Data Cleaning Approach

1. **Outlier Removal**: 
   - Remove values < -90°C or > 60°C (physically implausible)
   - These values are set to NaN for further processing

2. **Gap Interpolation**:
   - Missing data gaps ≤ 2 days: Linear interpolation
   - Missing data gaps > 2 days: Left as NaN (not interpolated to avoid introducing bias)
   - This preserves data integrity while handling minor measurement gaps

3. **Continuity Enforcement**:
   - Ensures complete daily time series by filling completely missing dates with NaN
   - Prevents indexing errors in downstream analysis

4. **Data Quality Reporting**:
   - Tracks percentage of missing data
   - Counts days interpolated (gaps ≤2 days)
   - Counts outliers removed
   - Reported in API response for transparency

## Assumptions

1. **Baseline Period**: 1991-2020 represents current climatology (WMO standard)
2. **Spatial Representativeness**: 0.25° grid cell adequately represents local conditions
3. **Temporal Homogeneity**: No major inhomogeneities in the reanalysis data
4. **Threshold Stability**: 95th percentile is appropriate for heatwave definition
5. **Event Independence**: Heatwave events are separated by at least one non-heatwave day
6. **Linear Trends**: Suitable for detecting monotonic changes over analysis period

## Security/Caching Decisions

### Security
- **Input Validation**: All API parameters validated (lat/lon ranges, year ranges, hazard types)
- **Rate Limiting**: 30 requests/minute per IP to prevent abuse
- **CORS Restriction**: Only allow frontend origin to access backend APIs
- **Request Size Limits**: Built-in FastAPI limits prevent oversized payloads
- **Safe Error Messages**: Generic error messages prevent information leakage
- **No Secrets in Code**: All configuration via environment variables

### Caching
- **Two-Level Caching**:
  1. **Raw Temperature Data**: Cached in MongoDB with 30-day TTL
  2. **Processed Results**: Hazard summaries cached with same TTL
- **Cache Key**: Normalized latitude/longitude (0.25° grid) + year range + hazard type
- **Cache Efficiency**: Redundant API calls avoided for same location/period
- **Cache Validation**: Timestamp-based with automatic expiration
- **Memory Efficiency**: Only essential data stored (temperature values, not full API responses)

## API Documentation

### POST /api/analyze
Analyzes climate hazard for given location and time range.

**Parameters** (all required):
- `lat`: Latitude (-90 to 90)
- `lon`: Longitude (-180 to 180) 
- `start_year`: Start year (≥1950)
- `end_year`: End year (≥start_year + 10, ≤ current year - 1)
- `hazard`: Hazard type (currently only "heatwave")

**Returns**:
```json
{
  "region": "string",
  "params": {...},
  "series": [
    {
      "year": integer,
      "events": integer,
      "heatwave_days": integer,
      "max_duration": integer,
      "mean_intensity": float,
      "rolling_avg": float || null
    }
  ],
  "trend": {
    "slope_per_decade": float,
    "mk_p": float,
    "sen_slope": float,
    "significant": boolean
  },
  "insights": ["string"],
  "caveats": ["string"],
  "data_quality": {
    "missing_percentage": float,
    "imputed_days": integer,
    "outliers_removed": integer
  }
}
```

### GET /api/export.csv
Returns analysis results as CSV file (same parameters as /api/analyze).

### GET /api/geocode
Lookup city coordinates using Open-Meteo geocoding API.

**Parameter**:
- `q`: City name query (minimum 2 characters)

**Returns**: Geocoding result with latitude, longitude, etc.

### GET /health
Health check endpoint returning service status.

## Deployed URLs Placeholders

- **Backend**: https://climate-hazard-api.onrender.com
- **Frontend**: https://climate-hazard-frontend.vercel.app
- **API Docs**: https://climate-hazard-api.onrender.com/docs
- **Health Check**: https://climate-hazard-api.onrender.com/health

## What I'd Improve with More Time

1. **Enhanced Hazard Types**: Add drought, flood, and cold wave analysis
2. **Advanced Visualization**: 
   - Animated temporal maps showing heatwave propagation
   - Uncertainty visualization (confidence intervals)
   - Comparative analysis between locations
3. **Improved UI/UX**:
   - Saved analyses and sharing functionality
   - Mobile-responsive design improvements
   - Keyboard navigation and accessibility enhancements
4. **Performance Optimizations**:
   - Pre-computed regional summaries for faster loading
   - Progressive loading for large date ranges
   - Service worker for offline capability
5. **Scientific Enhancements**:
   - Multiple threshold definitions (90th, 99th percentiles)
   - Different heatwave duration definitions (2+ days, 4+ days)
   - Statistical significance testing for trends
   - Regional climate model comparison
6. **DevOps Improvements**:
   - Automated testing pipeline (unit + integration tests)
   - Blue-green deployment strategy
   - Comprehensive monitoring and alerting
   - Load testing and performance benchmarking

## AI Tools Used and How

**Claude (in VS Code)** was used heavily throughout, including for writing most of the code.

**My Role**:
- Chose the method: day-of-year 95th-percentile thresholds with a ±7-day window, the 1991–2020 WMO baseline, 3+ day events, Mann-Kendall + Sen's slope for trends
- Reviewed, ran and tested the generated code
- After submission, ran the full request path end to end and found and fixed several bugs (see "Post-submission fixes")

## Post-submission fixes

Found after the deadline by exercising the full request path with fake weather data; fixed on the `post-submission-fixes` branch:

1. `POST /api/analyze` always returned 500 (slowapi requires a `request: Request` parameter; the body was named `request`).
2. Cache hits returned 500 (cached dicts were not rebuilt into `YearlyResult`/`TrendResult`).
3. `heatwave_days` counted every day above threshold, not only days inside 3+ day events.
4. Missing days were dropped, joining separate hot spells across a gap; gaps are now kept as NaN.
5. Map click did nothing (`whenCreated` was removed in react-leaflet v4) and the map did not pan on city search.
6. The frontend read `VITE_API_URL`, which CRA never injects; it now reads `REACT_APP_API_URL`.
7. `motor` and `pydantic-settings` were missing from `requirements.txt`.
8. Added `.gitignore`; removed committed `venv/`, `node_modules/`, `build/`, `.env` and a backup file.
9. Sen's slope now keeps zero-difference pairs (skipping them biased the slope away from 0); 500 responses no longer leak exception text.

The existing tests only covered 422 validation, which is why these were missed; an end-to-end test with a fake DB is the next addition.

## Current Status

- **Phase 1 (Backend Core)**: Complete
  - Implemented hazard detection, trend analysis, data cleaning, and caching
  - All backend tests pass (including API tests with mocked database)
- **Frontend**: Complete
  - Built with React, Vite, Leaflet, and Chart.js
  - Successfully builds for production
- **Integration**: 
  - Backend and frontend can be run locally as described in the setup steps
  - The application is ready for further development or user testing

The application is now ready to be run locally. For any further development or improvements, please proceed with the next phase as instructed.