from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    start_year: int = Field(..., ge=1950)
    end_year: int = Field(..., ge=1950)
    hazard: str = Field(..., pattern="^heatwave$")

    @validator('end_year')
    def end_year_must_be_greater_than_start_year(cls, v, values):
        if 'start_year' in values and v <= values['start_year']:
            raise ValueError('end_year must be greater than start_year')
        return v

    @validator('end_year')
    def span_at_least_10_years(cls, v, values):
        if 'start_year' in values and (v - values['start_year']) < 10:
            raise ValueError('year span must be at least 10 years')
        return v

    @validator('end_year')
    def end_year_not_in_future(cls, v):
        current_year = datetime.utcnow().year
        if v > current_year - 1:
            raise ValueError(f'end_year must be <= {current_year - 1}')
        return v

    class Config:
        schema_extra = {
            "example": {
                "lat": 40.7128,
                "lon": -74.0060,
                "start_year": 1990,
                "end_year": 2020,
                "hazard": "heatwave"
            }
        }

class DataQuality(BaseModel):
    missing_percentage: float
    imputed_days: int
    outliers_removed: int

class YearlyResult(BaseModel):
    year: int
    events: int
    heatwave_days: int
    max_duration: int
    mean_intensity: float
    rolling_avg: Optional[float] = None

class TrendResult(BaseModel):
    slope_per_decade: float
    mk_p: float
    sen_slope: float
    significant: bool

class AnalyzeResponse(BaseModel):
    region: str
    params: dict
    series: List[YearlyResult]
    trend: TrendResult
    insights: List[str]
    caveats: List[str]
    data_quality: DataQuality

class ExportRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    start_year: int = Field(..., ge=1950)
    end_year: int = Field(..., ge=1950)
    hazard: str = Field(..., pattern="^heatwave$")

    @validator('end_year')
    def end_year_must_be_greater_than_start_year(cls, v, values):
        if 'start_year' in values and v <= values['start_year']:
            raise ValueError('end_year must be greater than start_year')
        return v

    @validator('end_year')
    def span_at_least_10_years(cls, v, values):
        if 'start_year' in values and (v - values['start_year']) < 10:
            raise ValueError('year span must be at least 10 years')
        return v

    @validator('end_year')
    def end_year_not_in_future(cls, v):
        current_year = datetime.utcnow().year
        if v > current_year - 1:
            raise ValueError(f'end_year must be <= {current_year - 1}')
        return v