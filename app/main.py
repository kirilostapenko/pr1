"""Веб-рівень застосунку: HTML-сторінка та JSON-ендпоінт."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from . import weather

app = FastAPI(title="Погода — ПР1")
INDEX_PAGE = Path(__file__).parent / "templates" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Віддати сторінку з формою вводу міста."""
    return INDEX_PAGE.read_text(encoding="utf-8")


@app.get("/api/weather")
def api_weather(city: str = Query(..., min_length=1, description="Назва міста")) -> dict:
    """Повернути поточну погоду або коректну HTTP-помилку."""
    if not city.strip():
        raise HTTPException(status_code=422, detail="Введіть назву міста.")

    try:
        return weather.get_current_weather(city)
    except weather.WeatherError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
