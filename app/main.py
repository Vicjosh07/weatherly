# Entrypoint for FastAPI app
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.routers import weather
from app.routers import weather, crud
from app.database import Base, engine
from app.routers import export
from datetime import datetime, timedelta, date


# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Weather App")

app.include_router(weather.router)
app.include_router(crud.router)
app.include_router(export.router)


# Jinja2 for basic UI rendering
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    today = date.today()
    max_date = today + timedelta(days=4)   # allow up to 5 calendar days inclusive
    return templates.TemplateResponse("index.html", {
        "request": request,
        "message": "Hello Weather 🌦️",
        "today": today.isoformat(),        # "YYYY-MM-DD"
        "max_date": max_date.isoformat()
    })