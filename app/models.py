from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class WeatherQuery(Base):
    __tablename__ = "weather_queries"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(String, index=True)
    date_range = Column(String, nullable=True) 
    result = Column(String)  # store JSON/text response
    created_at = Column(DateTime, default=datetime.utcnow)
