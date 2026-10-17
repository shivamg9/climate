from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import csv
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from . import config
from .schemas import (
    AnalyzeRequest, AnalyzeResponse, ExportRequest,
    DataQuality, YearlyResult, TrendResult
)
from .data_source import OpenMeteoDataSource, CityGeocoder
from .db import init_db, close_db, get_database, ClimateDatabase
from .hazards import compute_heatwave_metrics
from .trends import analyze_trends

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Climate Hazard Trend Analyzer",
    description="Analyzes historical weather data for heatwave trends",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip middleware for response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global exception handler for safe error messages
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await init_db(config.settings.mongodb_uri, config.settings.database_name)

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        db = await get_database()
        is_healthy = await db.health_check()
        return {"status": "healthy" if is_healthy else "unhealthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "timestamp": datetime.utcnow().isoformat()}

# Helper functions
def normalize_lat_lon(lat: float, lon: float) -> Tuple[float, float]:
    """Round lat/lon to 0.25° for grid-cell normalization"""
    lat_rounded = round(lat * 4) / 4
    lon_rounded = round(lon * 4) / 4
    return lat_rounded, lon_rounded

def get_cell_key(lat: float, lon: float, start_year: int, end_year: int) -> str:
    """Generate a cache key for the cell and year range"""
    lat_norm, lon_norm = normalize_lat_lon(lat, lon)
    return f"{lat_norm:.2f}_{lon_norm:.2f}_{start_year}_{end_year}"

def sanitize_csv_value(value: Any) -> str:
    """Sanitize a value for CSV output to prevent injection attacks."""
    if value is None:
        return ""
    s = str(value)
    # Prefix with single quote if starts with formula characters
    if s and s[0] in ('=', '+', '-', '@'):
        return "'" + s
    return s

async def get_city_from_coords(lat: float, lon: float) -> str:
    """Get city name from coordinates using reverse geocoding (simplified)"""
    # For simplicity, we'll return coordinates as region name
    # In a full implementation, you'd use a reverse geocoding service
    return f"Location ({lat:.2f}, {lon:.2f})"

# API Endpoints
@app.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("30/minute")
async def analyze_climate_hazard_post(
    request: Request,  # slowapi requires a starlette Request named "request"
    body: AnalyzeRequest,
    db: ClimateDatabase = Depends(get_database)
):
    """Analyze climate hazard for given location and time range (POST)"""
    return await _analyze_climate_hazard(
        body.lat, body.lon, body.start_year, body.end_year, body.hazard, db
    )

@app.get("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("30/minute")
async def analyze_climate_hazard_get(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start_year: int = Query(..., ge=1950),
    end_year: int = Query(..., ge=1950),
    hazard: str = Query(..., pattern="^heatwave$"),
    db: ClimateDatabase = Depends(get_database)
):
    """Analyze climate hazard for given location and time range (GET)"""
    # Validate year range
    if end_year <= start_year:
        raise HTTPException(status_code=422, detail="end_year must be greater than start_year")
    if (end_year - start_year) < 10:
        raise HTTPException(status_code=422, detail="year span must be at least 10 years")
    current_year = datetime.utcnow().year
    if end_year > current_year - 1:
        raise HTTPException(status_code=422, detail=f"end_year must be <= {current_year - 1}")
    
    return await _analyze_climate_hazard(lat, lon, start_year, end_year, hazard, db)

async def _analyze_climate_hazard(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    hazard: str,
    db: ClimateDatabase
) -> AnalyzeResponse:
    """Core analysis logic shared by POST and GET endpoints"""
    try:
        # Normalize coordinates for cache key
        lat_norm, lon_norm = normalize_lat_lon(lat, lon)
        cell_key = get_cell_key(lat, lon, start_year, end_year)

        logger.info(f"Analyzing hazard for cell {cell_key}, {start_year}-{end_year}")

        # Check if we have cached hazard summary
        cached_summary = await db.get_hazard_summary(
            cell_key,
            start_year,
            end_year,
            hazard
        )

        if cached_summary:
            logger.info(f"Using cached hazard summary for {cell_key}")
            # Rebuild models: cached values are plain dicts
            yearly_results = [YearlyResult(**yr) for yr in cached_summary["yearly_results"]]
            trend_data = cached_summary["trend_data"]
            trend_result = TrendResult(**trend_data)

            # Get temperature data for data quality metrics (from cache or fetch)
            temperature_result = await db.get_daily_weather(
                cell_key,
                start_year,
                end_year
            )

            if temperature_result is None:
                # If no temperature data cached, we need to fetch it
                raise HTTPException(status_code=500, detail="Cached summary found but missing temperature data")

            temperature_data, cached_quality = temperature_result
            if cached_quality:
                data_quality = DataQuality(**cached_quality)
            else:
                # Calculate data quality from temperature data
                data_quality = await _calculate_data_quality(temperature_data)
        else:
            logger.info(f"No cached summary found for {cell_key}, fetching data")

            # Fetch temperature data (check cache first)
            temperature_result = await db.get_daily_weather(
                cell_key,
                start_year,
                end_year
            )

            if temperature_result is None:
                # Fetch from Open-Meteo
                data_source = OpenMeteoDataSource(config.settings.open_meteo_base_url)
                df, data_quality_dict = await data_source.fetch_temperature_data(
                    latitude=lat,
                    longitude=lon,
                    start_year=start_year,
                    end_year=end_year,
                    baseline_start=config.settings.baseline_start_year,
                    baseline_end=config.settings.baseline_end_year
                )

                # Convert DataFrame to list of dicts for storage
                temperature_data = []
                for date, row in df.iterrows():
                    temperature_data.append({
                        "date": date.isoformat(),
                        "tmax": row["tmax"] if not pd.isna(row["tmax"]) else None
                    })

                # Store in cache
                await db.store_daily_weather(
                    cell_key=cell_key,
                    start_year=start_year,
                    end_year=end_year,
                    temperature_data=temperature_data,
                    data_quality=data_quality_dict
                )

                data_quality = DataQuality(**data_quality_dict)
            else:
                temperature_data, cached_quality = temperature_result
                if cached_quality:
                    data_quality = DataQuality(**cached_quality)
                else:
                    # Calculate data quality from cached temperature data
                    data_quality = await _calculate_data_quality(temperature_data)

            # Convert temperature data back to DataFrame for analysis
            # Keep gaps as NaN so they break heatwave runs (NaN > threshold is False)
            df_data = [
                {"date": item["date"],
                 "tmax": item["tmax"] if item["tmax"] is not None else np.nan}
                for item in temperature_data
            ]

            if all(item["tmax"] is None for item in temperature_data):
                raise HTTPException(status_code=422, detail="No valid temperature data available after cleaning")

            df = pd.DataFrame(df_data)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

            # Compute heatwave metrics
            hazards_result = compute_heatwave_metrics(
                tmax_series=df["tmax"],
                baseline_start=config.settings.baseline_start_year,
                baseline_end=config.settings.baseline_end_year,
                percentile=config.settings.heatwave_threshold_percentile,
                min_consecutive_days=config.settings.heatwave_min_consecutive_days
            )

            # Extract yearly results
            yearly_stats = hazards_result["yearly_stats"]
            yearly_results = []
            for year in range(start_year, end_year + 1):
                if year in yearly_stats:
                    stats = yearly_stats[year]
                    yearly_results.append(YearlyResult(
                        year=year,
                        events=stats["events"],
                        heatwave_days=int(stats["heatwave_days"]),
                        max_duration=int(stats["max_duration"]),
                        mean_intensity=float(stats["mean_intensity"]),
                        rolling_avg=None  # Will be calculated in trend analysis
                    ))
                else:
                    yearly_results.append(YearlyResult(
                        year=year,
                        events=0,
                        heatwave_days=0,
                        max_duration=0,
                        mean_intensity=0.0,
                        rolling_avg=None
                    ))

            # Analyze trends
            years_list = list(range(start_year, end_year + 1))
            heatwave_days_list = [yr.heatwave_days for yr in yearly_results]
            event_counts_list = [yr.events for yr in yearly_results]

            trend_analysis = analyze_trends(years_list, heatwave_days_list, event_counts_list)

            # Calculate rolling averages for yearly results
            rolling_heatwave = trend_analysis["rolling_averages"]["heatwave_days"]
            for i, yearly_result in enumerate(yearly_results):
                if i < len(rolling_heatwave) and not np.isnan(rolling_heatwave[i]):
                    yearly_result.rolling_avg = float(rolling_heatwave[i])

            # Create trend result
            trend_result = TrendResult(
                slope_per_decade=trend_analysis["heatwave_days"]["slope_per_decade"],
                mk_p=trend_analysis["heatwave_days"]["mk_p"],
                sen_slope=trend_analysis["heatwave_days"]["sen_slope"],
                significant=trend_analysis["heatwave_days"]["significant"]
            )

            trend_data = {
                "slope_per_decade": trend_result.slope_per_decade,
                "mk_p": trend_result.mk_p,
                "sen_slope": trend_result.sen_slope,
                "significant": trend_result.significant
            }

            # Store hazard summary in cache
            await db.store_hazard_summary(
                cell_key=cell_key,
                start_year=start_year,
                end_year=end_year,
                hazard_type=hazard,
                yearly_results=[yr.dict() for yr in yearly_results],
                trend_data=trend_data
            )

        # Generate insights
        insights = _generate_insights(yearly_results, start_year, end_year)

        # Generate caveats
        caveats = _generate_caveats()

        # Get region name
        region = await get_city_from_coords(lat, lon)

        # Prepare response
        response = AnalyzeResponse(
            region=region,
            params={
                "lat": lat,
                "lon": lon,
                "start_year": start_year,
                "end_year": end_year,
                "hazard": hazard
            },
            series=yearly_results,
            trend=trend_result,
            insights=insights,
            caveats=caveats,
            data_quality=data_quality
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze_climate_hazard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/export.csv")
@limiter.limit("30/minute")
async def export_csv(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    start_year: int = Query(..., ge=1950),
    end_year: int = Query(..., ge=1950),
    hazard: str = Query(..., pattern="^heatwave$"),
    db: ClimateDatabase = Depends(get_database)
):
    """Export analysis results as CSV"""
    try:
        # Validate year span
        if end_year <= start_year:
            raise HTTPException(status_code=422, detail="end_year must be greater than start_year")
        if (end_year - start_year) < 10:
            raise HTTPException(status_code=422, detail="year span must be at least 10 years")

        # Normalize coordinates
        lat_norm, lon_norm = normalize_lat_lon(lat, lon)
        cell_key = get_cell_key(lat, lon, start_year, end_year)

        # Try to get cached summary
        cached_summary = await db.get_hazard_summary(
            cell_key,
            start_year,
            end_year,
            hazard
        )

        if cached_summary:
            yearly_results = cached_summary["yearly_results"]
        else:
            # We would need to run the analysis, but for CSV export we'll redirect to analyze endpoint
            # For simplicity, we'll raise an error suggesting to use the analyze endpoint first
            raise HTTPException(
                status_code=404,
                detail="No cached data found. Please run the analysis endpoint first to generate and cache the data."
            )

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Year",
            "Heatwave Events",
            "Heatwave Days",
            "Max Duration (days)",
            "Mean Intensity (°C)",
            "5-Year Rolling Avg Heatwave Days"
        ])

        # Write data rows
        for yearly_result in yearly_results:
            writer.writerow([
                sanitize_csv_value(yearly_result["year"]),
                sanitize_csv_value(yearly_result["events"]),
                sanitize_csv_value(yearly_result["heatwave_days"]),
                sanitize_csv_value(yearly_result["max_duration"]),
                sanitize_csv_value(yearly_result["mean_intensity"]),
                sanitize_csv_value(yearly_result.get("rolling_avg", "") or "")
            ])

        output.seek(0)

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=heatwave_analysis_{lat_norm:.2f}_{lon_norm:.2f}_{start_year}_{end_year}.csv"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in export_csv: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/geocode")
@limiter.limit("30/minute")
async def geocode_city(
    request: Request,
    q: str = Query(..., min_length=2)
):
    """Geocode a city name"""
    if len(q) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters")

    try:
        geocoder = CityGeocoder(config.settings.open_meteo_geocode_url)
        result = await geocoder.geocode_city(q)

        if result is None:
            raise HTTPException(status_code=404, detail="City not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in geocode_city: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper functions
async def _calculate_data_quality(temperature_data: List[Dict[str, Any]]) -> DataQuality:
    """Calculate data quality metrics from temperature data"""
    if not temperature_data:
        return DataQuality(
            missing_percentage=100.0,
            imputed_days=0,
            outliers_removed=0
        )

    total_days = len(temperature_data)
    missing_days = sum(1 for item in temperature_data if item["tmax"] is None)
    missing_percentage = round((missing_days / total_days) * 100, 2) if total_days > 0 else 0.0

    # For simplicity, we'll estimate imputed days and outliers removed
    # In a real implementation, these would come from the cleaning process
    imputed_days = 0  # Would be calculated during cleaning
    outliers_removed = 0  # Would be calculated during cleaning

    return DataQuality(
        missing_percentage=missing_percentage,
        imputed_days=imputed_days,
        outliers_removed=outliers_removed
    )

def _generate_insights(yearly_results: List[YearlyResult], start_year: int, end_year: int) -> List[str]:
    """Generate insights from the yearly results"""
    insights = []

    if len(yearly_results) < 2:
        return insights

    # Calculate first decade vs last decade comparison
    total_years = end_year - start_year + 1
    if total_years >= 20:
        split_point = start_year + total_years // 2
        first_half = [yr for yr in yearly_results if yr.year < split_point]
        second_half = [yr for yr in yearly_results if yr.year >= split_point]

        if first_half and second_half:
            first_half_avg = sum(yr.heatwave_days for yr in first_half) / len(first_half)
            second_half_avg = sum(yr.heatwave_days for yr in second_half) / len(second_half)

            if first_half_avg > 0:
                pct_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                insights.append(
                    f"Heatwave days changed by {pct_change:+.1f}% from "
                    f"{first_half_avg:.1f} days/year (first half) to "
                    f"{second_half_avg:.1f} days/year (second half)"
                )
            else:
                insights.append(
                    f"Heatwave days increased from {first_half_avg:.1f} to "
                    f"{second_half_avg:.1f} days/year (baseline was zero)"
                )

    # Overall trend insight
    total_events = sum(yr.events for yr in yearly_results)
    total_heatwave_days = sum(yr.heatwave_days for yr in yearly_results)
    avg_events_per_year = total_events / len(yearly_results) if yearly_results else 0
    avg_heatwave_days_per_year = total_heatwave_days / len(yearly_results) if yearly_results else 0

    insights.append(
        f"Average of {avg_events_per_year:.1f} heatwave events per year, "
        f"totaling {avg_heatwave_days_per_year:.1f} heatwave days per year"
    )

    # Find year with most events
    max_events_year = max(yearly_results, key=lambda x: x.events) if yearly_results else None
    if max_events_year and max_events_year.events > 0:
        insights.append(
            f"Year {max_events_year.year} had the most heatwave events: {max_events_year.events}"
        )

    return insights

def _generate_caveats() -> List[str]:
    """Generate caveats for the analysis"""
    return [
        "ERA5 reanalysis grid data may differ from local station measurements",
        "Heatwave threshold based on 95th percentile of daily maximum temperature",
        "Baseline period uses 1991-2020 with ±7-day window for seasonal smoothing",
        "Heatwave defined as ≥3 consecutive days exceeding daily threshold",
        "Short records (<30 years) may limit trend detection reliability",
        "Missing data gaps >2 days are not interpolated and may affect results"
    ]
