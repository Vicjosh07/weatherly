import requests
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from collections import defaultdict
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db
from app import models


# VALID_CITIES = ["London", "Paris", "New York", "Berlin", "Tokyo", "Lagos", "Nairobi"]  # extend later



router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# API_KEY = os.getenv("OPENWEATHER_API_KEY")  # keep secret in env var
API_KEY = "77ca9aad00aa633b92ced66abf518ef8" # my openweather api key


BASE_URL = "http://api.openweathermap.org/data/2.5/"

def validate_input(city: str = None, zip: str = None):
    if city:
        city = city.strip().title()
        if not city.isalpha():  # crude check (no numbers)
            return None, "City names should only contain letters."
        return city, None
    if zip:
        if not zip.isdigit() or len(zip) != 5:
            return None, "Zip code must be 5 digits (US only)."
        return zip, None
    return None, "Please enter either a city or a zip code."

@router.get("/weather", response_class=HTMLResponse)
async def get_weather(
    request: Request,
    city: str = Query(None),
    zip: str = Query(None),
    db: Session = Depends(get_db)
):
    user_input, error = validate_input(city, zip)
    if error:
        return templates.TemplateResponse("weather.html", {
            "request": request,
            "error": error,
            "weather": None
        })

    if city:
        url = f"{BASE_URL}weather?q={user_input}&appid={API_KEY}&units=metric"
    elif zip:
        url = f"{BASE_URL}weather?zip={user_input},us&appid={API_KEY}&units=metric"

    res = requests.get(url)
    data = res.json()

    if res.status_code != 200 or "main" not in data:
        return templates.TemplateResponse("weather.html", {
            "request": request,
            "error": f"Could not fetch weather for '{city or zip}'. Please Confirm your entry.",
            "weather": None
        })

    weather = {
        "lat": data["coord"]["lat"],
        "lon": data["coord"]["lon"],
        "data": {
            "type": "weather",
            "city": data["name"],
            "temp": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "icon": data["weather"][0]["icon"]
        }
    }

    db_query = models.WeatherQuery(
        location=weather["data"]["city"],
        date_range="current",
        result=json.dumps(weather)
    )

    db.add(db_query)
    db.commit()

    return templates.TemplateResponse("weather.html", {
        "request": request,
        "weather": weather
    })


@router.get("/forecast", response_class=HTMLResponse)
async def get_forecast(request: Request, city: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    url = f"{BASE_URL}forecast?q={city}&appid={API_KEY}&units=metric"
    res = requests.get(url)
    data = res.json()

    if res.status_code != 200 or "list" not in data:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": f"Could not fetch forecast for '{city}'"
        })

    grouped = defaultdict(list)
    for entry in data["list"]:
        date = entry["dt_txt"].split(" ")[0]
        grouped[date].append(entry)

    forecast = []
    for date, entries in list(grouped.items())[:5]:
        midday_entry = next((e for e in entries if "12:00:00" in e["dt_txt"]), entries[0])
        forecast.append({
            "date": date,
            "temp": midday_entry["main"]["temp"],
            "description": midday_entry["weather"][0]["description"],
            "icon": midday_entry["weather"][0]["icon"]
        })

    forecast_data = {
        "lat": data["city"]["coord"]["lat"],
        "lon": data["city"]["coord"]["lon"],
        "data": {
            "type": "forecast",
            "city": data["city"]["name"],
            "forecast": forecast
        }
    }

    db_query = models.WeatherQuery(
        location=forecast_data['data']['city'],
        date_range="5-day",
        result=json.dumps(forecast_data)
    )

    db.add(db_query)
    db.commit()

    return templates.TemplateResponse("forecast.html", {
    "request": request,
    "forecast": forecast_data
        })



@router.get("/weather/current", response_class=HTMLResponse)
async def current_location_weather(request: Request, db: Session = Depends(get_db)):
    try:
        ip_res = requests.get("https://ipinfo.io/json")
        ip_data = ip_res.json()
        city = ip_data.get("city", "London")  # fallback
    except:
        city = "London"

    url = f"{BASE_URL}weather?q={city}&appid={API_KEY}&units=metric"
    res = requests.get(url)
    data = res.json()

    if res.status_code != 200 or "main" not in data:
        return templates.TemplateResponse("weather.html", {
            "request": request,
            "error": f"Could not fetch weather for current location"
        })

    weather = {
    "lat": data["coord"]["lat"],
    "lon": data["coord"]["lon"],
    "data": {
        "type": "weather",
        "city": data["name"],
        "temp": data["main"]["temp"],
        "description": data["weather"][0]["description"],
        "icon": data["weather"][0]["icon"]
    }
}

    # --- Auto-save into DB ---
    db_query = models.WeatherQuery(
        location=weather['data']["city"],
        date_range="current",
        result=json.dumps(weather)
    )
    db.add(db_query)
    db.commit()

    return templates.TemplateResponse("weather.html", {
        "request": request,
        "weather": weather
    })


@router.get("/forecast/range", response_class=HTMLResponse)
async def get_forecast_range(
    request: Request,
    city: str = Query(..., min_length=2),
    start: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db)
):
    # validate city input (reuse validate_input but bypass the isalpha check for city param)
    user_input = city.strip().title()

    # parse dates
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": "Dates must be in YYYY-MM-DD format."
        })

    if end_dt < start_dt:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": "End date must be the same as or after start date."
        })

    # limit range to max 5 calendar days inclusive (OpenWeatherMap gives max ~5 days)
    if (end_dt - start_dt).days > 4:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": "Maximum allowed range is 5 days (OpenWeatherMap limit)."
        })

    # fetch forecast data
    url = f"{BASE_URL}forecast?q={user_input}&appid={API_KEY}&units=metric"
    res = requests.get(url, timeout=10)
    if res.status_code != 200:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": f"Could not fetch forecast for '{city}'."
        })
    data = res.json()
    if "list" not in data or "city" not in data:
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": "Unexpected API response."
        })

    # group entries by date
    grouped = defaultdict(list)
    for entry in data["list"]:
        date_str = entry["dt_txt"].split(" ")[0]  # YYYY-MM-DD
        grouped[date_str].append(entry)

    # build list of target dates (strings)
    target_dates = []
    cur = start_dt
    while cur <= end_dt:
        target_dates.append(cur.isoformat())
        cur += timedelta(days=1)

    # ensure requested dates available in forecast data (forecast covers limited window)
    available_dates = set(grouped.keys())
    missing = [d for d in target_dates if d not in available_dates]
    if missing:
        # Let user know which dates aren't available (outside forecast window)
        return templates.TemplateResponse("forecast.html", {
            "request": request,
            "error": f"Forecast for these dates not available: {', '.join(missing)}. OpenWeatherMap provides ~5 days of forecast only."
        })

    # pick midday or nearest
    forecast = []
    for d in target_dates:
        entries = grouped[d]
        # try exact midday
        midday_entry = next((e for e in entries if "12:00:00" in e["dt_txt"]), None)
        if not midday_entry:
            # pick the entry closest to 12:00
            def hour_diff(e):
                t = datetime.strptime(e["dt_txt"].split(" ")[1], "%H:%M:%S")
                return abs(t.hour - 12) * 60 + t.minute
            midday_entry = min(entries, key=hour_diff)
        forecast.append({
            "date": d,
            "temp": midday_entry["main"]["temp"],
            "description": midday_entry["weather"][0]["description"],
            "icon": midday_entry["weather"][0]["icon"]
        })

    # unified payload
    forecast_data = {
        "lat": data["city"]["coord"]["lat"],
        "lon": data["city"]["coord"]["lon"],
        "data": {
            "type": "forecast_range",
            "city": data["city"]["name"],
            "forecast": forecast
        }
    }

    # save to DB (store date range string)
    date_range_str = f"{start_dt.isoformat()} to {end_dt.isoformat()}"
    db_query = models.WeatherQuery(
        location=forecast_data["data"]["city"],
        date_range=date_range_str,
        result=json.dumps(forecast_data)
    )
    db.add(db_query)
    db.commit()

    # pass unified dict into template (forecast.html expects unified structure)
    return templates.TemplateResponse("forecast.html", {
        "request": request,
        "forecast": forecast_data
    })
