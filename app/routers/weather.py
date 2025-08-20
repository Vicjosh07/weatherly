import requests
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Depends, Query, HTTPException, Request, Form
from collections import defaultdict
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db
from app import models
import re


# VALID_CITIES = ["London", "Paris", "New York", "Berlin", "Tokyo", "Lagos", "Nairobi"]  # extend later



router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# API_KEY = os.getenv("OPENWEATHER_API_KEY")  # keep secret in env var
API_KEY = "77ca9aad00aa633b92ced66abf518ef8" # my openweather api key


BASE_URL = "http://api.openweathermap.org/data/2.5/"

def validate_input(city: str = None, zip: str = None):
    if city:
        city = city.strip().title()
        # Allow alphabets + spaces + hyphens (e.g. "New York", "Rio-de-Janeiro")
        if not re.match(r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*$", city):
            return None, "City names should only contain letters, spaces, or hyphens."
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


@router.post("/queries/{query_id}/update", response_class=HTMLResponse)
def update_query_form(
    request: Request,
    query_id: int,
    location: str = Form(...),
    start_date: str = Form(None),
    end_date: str = Form(None),
    action: str = Form("update"),   # "update" or "view"
    db: Session = Depends(get_db)
):
    query = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    location_in = location.strip()

    # If either start_date or end_date provided, require both
    if (start_date and not end_date) or (end_date and not start_date):
        return templates.TemplateResponse("edit_query.html", {
            "request": request,
            "query": query,
            "error": "Please provide both start and end dates for a forecast range, or leave both blank."
        })

    # If both provided -> treat as range forecast
    if start_date and end_date:
        # parse dates safely
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": "Dates must be in YYYY-MM-DD format."
            })

        if e_dt < s_dt:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": "End date must be same as or after start date."
            })

        if (e_dt - s_dt).days > 4:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": "Maximum allowed range is 5 days (OpenWeatherMap limit)."
            })

        # fetch forecast and build payload (same logic you had)
        url = f"{BASE_URL}forecast?q={location_in}&appid={API_KEY}&units=metric"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
        except Exception as exc:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": f"Network/API error: {exc}"
            })

        if res.status_code != 200 or "list" not in data or "city" not in data:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": f"Could not fetch forecast for '{location_in}'."
            })

        # group entries by date
        grouped = defaultdict(list)
        for entry in data["list"]:
            date_str = entry["dt_txt"].split(" ")[0]
            grouped[date_str].append(entry)

        # build target dates and check availability
        target_dates = []
        cur = s_dt
        while cur <= e_dt:
            target_dates.append(cur.isoformat())
            cur += timedelta(days=1)

        missing = [d for d in target_dates if d not in grouped]
        if missing:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query,
                "error": f"Forecast not available for: {', '.join(missing)}. OpenWeatherMap provides 5 or less days of forecast, today Excluded."
            })

        # pick midday or nearest
        forecast = []
        for d in target_dates:
            entries = grouped[d]
            midday_entry = next((e for e in entries if "12:00:00" in e["dt_txt"]), None)
            if not midday_entry:
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

        payload = {
            "lat": data["city"]["coord"]["lat"],
            "lon": data["city"]["coord"]["lon"],
            "data": {
                "type": "forecast_range",
                "city": data["city"]["name"],
                "forecast": forecast
            }
        }

        # update record
        query.location = payload["data"]["city"]
        query.date_range = f"{s_dt.isoformat()} to {e_dt.isoformat()}"
        query.result = json.dumps(payload)

    else:
        # Neither start nor end provided -> treat as current weather refresh
        url = f"{BASE_URL}weather?q={location_in}&appid={API_KEY}&units=metric"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
        except Exception as exc:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": f"Network/API error: {exc}"
            })

        if res.status_code != 200 or "main" not in data:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": f"Could not fetch weather for '{location_in}'."
            })

        payload = {
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

        query.location = payload["data"]["city"]
        query.date_range = "current"
        query.result = json.dumps(payload)

    # commit and refresh
    db.commit()
    db.refresh(query)

    # Redirect behavior
    if action == "view":
        return RedirectResponse(url=f"/queries/{query_id}/view", status_code=303)
    return RedirectResponse(url="/queries/", status_code=303)

@router.get("/forecast/range", response_class=HTMLResponse)
async def get_forecast_range(
    request: Request,
    city: str = Query(..., min_length=2),
    start: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db)
):
    """
    Example: /forecast/range?city=London&start=2025-08-18&end=2025-08-20
    Uses OpenWeatherMap 5-day forecast and returns midday picks for each date in the range.
    """
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
            "error": f"Forecast for these dates not available: {', '.join(missing)}. OpenWeatherMap provides 5 or less days of forecast, today Excluded."
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
        "forecast": forecast_data})