
# Weather App

## 📌 Summary

This project is a **Weather Web Application** built with **FastAPI, Jinja2, SQLAlchemy, and Bootstrap**.

It allows users to:
- 🌦️ Fetch **current weather** or a **5-day forecast** by city or ZIP code
- 💾 Save, edit, and delete queries with automatic map rendering via **Leaflet + OpenStreetMap**
- 📍 Detect **current location weather** automatically using IP geolocation
- 📊 Export all saved queries to **CSV** for offline use
- 🗺️ View weather results with an **interactive map, icons, and descriptive UI**
- 🛠️ Manage queries with an edit form, dynamic date range handling, and direct “view” of updated outputs

---

### 👨‍💻 What I Did
- Designed the app **from scratch**, including architecture and a feature roadmap (Phase 1 → Phase 3)
- Implemented **FastAPI routes**, database models, and CRUD operations
- Integrated **OpenWeatherMap API** for both weather and forecast data
- Added **map rendering** using Leaflet (instead of a paid Google API)
- Created a clean, responsive UI with **Bootstrap cards & modals**
- Implemented **CSV export**, **date range validation**, and **query management**
- Detect weather for your **current location** via **IP-based geolocation**  
- Manage **date ranges**, dynamically edit queries, and directly view refreshed results  
- Access **Product Manager Accelerator** info via a built-in modal  

## Features

- **Flexible Location Input:** Users can search weather by city, ZIP code, or current coordinates.
- **Real-Time Weather:** Fetches live weather data from external APIs.
- **5-Day Forecast:** Displays an extended weather outlook.
- **Current Location Support:** Option to get weather for the user’s current location.
- **CRUD Operations:** Users can create, read, update, and delete their weather queries and results.
- **Data Export:** Export weather data in CSV, JSON, and other formats.
- **API Integrations:** (Optional) OpenStreetMap integration for location-based content.

## Tech Stack

- **Backend:** Python (FastAPI)
- **Database:** SQLite (via SQLAlchemy)
- **Frontend:** Jinja2 templates (HTML)
- **APIs:** OpenWeatherMap and OpenStreetMap APIs

## Project Structure

```
weather_app/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── crud.py
│   │   ├── export.py
│   │   └── weather.py
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── weather.html
│       ├── forecast.html
│       ├── queries.html
│       └── edit_query.html
├── weather.db
├── requirements.txt
├── README.md
├── .gitignore
```

## Setup & Installation

1. **Clone the repository:**
   ```
   git clone <repo-url>
   cd weather_app
   ```

2. **Create and activate a virtual environment:**
   ```
   python -m venv pvenv
   pvenv\Scripts\activate
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```
   uvicorn app.main:app --reload
   ```

5. **Access the app:**
   Open your browser and go to `http://127.0.0.1:8000`

## Usage

- Enter a location to get current weather and forecast.
- View, update, or delete your previous queries.
- Export your weather data as needed.

## Notes

- Make sure to set up your API keys (e.g., for OpenWeatherMap) as environment variables or in a config file.
- The UI is functional but not styled; feel free to enhance it.
- Optional features (Open Street maps) are included for demonstration and can be extended.

## Assessment Coverage

- [x] Tech Assessment 1: Weather App (core requirements)
- [x] Tech Assessment 2: CRUD, API integration, data export (core and optional features)
