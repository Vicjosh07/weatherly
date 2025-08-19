from pydantic import BaseModel
from datetime import datetime

class WeatherQueryBase(BaseModel):
    location: str
    date_range: str | None = None
    result: str

class WeatherQueryCreate(WeatherQueryBase):
    pass

class WeatherQueryUpdate(BaseModel):
    location: str | None = None
    date_range: str | None = None
    result: str | None = None

class WeatherQueryOut(WeatherQueryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
