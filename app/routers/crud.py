from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests, json
from fastapi.responses import RedirectResponse
from app.routers import weather as weather_mod
from datetime import datetime, timedelta, date
from collections import defaultdict

API_KEY = getattr(weather_mod, "API_KEY", None)
BASE_URL = getattr(weather_mod, "BASE_URL", "http://api.openweathermap.org/data/2.5/")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# CREATE
@router.post("/queries/", response_model=schemas.WeatherQueryOut)
def create_query(query: schemas.WeatherQueryCreate, db: Session = Depends(get_db)):
    db_query = models.WeatherQuery(**query.dict())
    db.add(db_query)
    db.commit()
    db.refresh(db_query)
    return db_query

# READ all
# READ all (parse JSON string -> attach as `parsed`)
@router.get("/queries/", response_class=HTMLResponse)
def read_queries(request: Request, db: Session = Depends(get_db)):
    queries = db.query(models.WeatherQuery).order_by(models.WeatherQuery.created_at.desc()).all()
    for q in queries:
        try:
            q.parsed = json.loads(q.result) if q.result else None
        except Exception:
            q.parsed = None
    return templates.TemplateResponse("queries.html", {"request": request, "queries": queries})

# UPDATE
@router.put("/queries/{query_id}", response_model=schemas.WeatherQueryOut)
def update_query(query_id: int, update: schemas.WeatherQueryUpdate, db: Session = Depends(get_db)):
    db_query = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not db_query:
        raise HTTPException(status_code=404, detail="Query not found")

    for key, value in update.dict(exclude_unset=True).items():
        setattr(db_query, key, value)

    db.commit()
    db.refresh(db_query)
    return db_query

# DELETE
@router.get("/queries/{query_id}/delete")
def delete_query(query_id: int, db: Session = Depends(get_db)):
    db_query = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not db_query:
        raise HTTPException(status_code=404, detail="Query not found")
    db.delete(db_query)
    db.commit()
    return RedirectResponse(url="/queries/", status_code=303)


# Edit form page (parse single query)
@router.get("/queries/{query_id}/edit", response_class=HTMLResponse)
def edit_query(request: Request, query_id: int, db: Session = Depends(get_db)):
    query = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    try:
        query.parsed = json.loads(query.result) if query.result else None
    except Exception:
        query.parsed = None
    return templates.TemplateResponse("edit_query.html", {"request": request, "query": query})


# Handle form submission -> re-fetch weather + update record
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
    """
    Update query. If start_date & end_date provided -> re-fetch forecast range.
    Otherwise -> re-fetch current weather.
    action == 'view' will redirect to the view page for this query after saving.
    """
    query = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Normalize location string
    location_in = location.strip()

    # If both dates provided -> validate and fetch forecast range
    if start_date and end_date:
        # parse dates
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
                "request": request, "query": query, "error": "Maximum range is 5 days (OpenWeatherMap limit)."
            })

        # fetch raw forecast
        url = f"{BASE_URL}forecast?q={location_in}&appid={API_KEY}&units=metric"
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": f"Could not fetch forecast for '{location_in}'."
            })
        data = res.json()
        if "list" not in data or "city" not in data:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query, "error": "Unexpected API response for forecast."
            })

        # group entries by date
        grouped = defaultdict(list)
        for entry in data["list"]:
            date_str = entry["dt_txt"].split(" ")[0]
            grouped[date_str].append(entry)

        # build target dates
        target_dates = []
        cur = s_dt
        while cur <= e_dt:
            target_dates.append(cur.isoformat())
            cur += timedelta(days=1)

        # ensure all requested dates available
        missing = [d for d in target_dates if d not in grouped]
        if missing:
            return templates.TemplateResponse("edit_query.html", {
                "request": request, "query": query,
                "error": f"Forecast not available for: {', '.join(missing)} (OpenWeatherMap covers ~5 days)."
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

        # unified payload
        payload = {
            "lat": data["city"]["coord"]["lat"],
            "lon": data["city"]["coord"]["lon"],
            "data": {
                "type": "forecast_range",
                "city": data["city"]["name"],
                "forecast": forecast
            }
        }

        # update db record
        query.location = payload["data"]["city"]
        query.date_range = f"{s_dt.isoformat()} to {e_dt.isoformat()}"
        query.result = json.dumps(payload)

    else:
        # No date range -> fetch current weather and save unified schema
        url = f"{BASE_URL}weather?q={location_in}&appid={API_KEY}&units=metric"
        res = requests.get(url, timeout=10)
        data = res.json()
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

@router.get("/queries/{query_id}/view", response_class=HTMLResponse)
def view_query(request: Request, query_id: int, db: Session = Depends(get_db)):
    q = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")
    try:
        parsed = json.loads(q.result) if q.result else None
    except Exception:
        parsed = None

    if not parsed:
        return templates.TemplateResponse("queries.html", {"request": request, "queries": db.query(models.WeatherQuery).all(), "error": "Query has no result to view."})

    typ = parsed.get("data", {}).get("type", "")
    if typ == "weather":
        # pass the unified dict as 'weather' to reuse weather.html
        return templates.TemplateResponse("weather.html", {"request": request, "weather": parsed})
    else:
        # forecast / forecast_range
        return templates.TemplateResponse("forecast.html", {"request": request, "forecast": parsed})

