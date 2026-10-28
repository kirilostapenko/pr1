"""Інтеграція із зовнішнім API Open-Meteo.

Цей модуль відповідає за HTTP-запити, параметри та перевірку відповіді.
Веб-рівень отримує готові дані або WeatherError і не працює з requests.
"""

from typing import Any

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 8


class WeatherError(Exception):
    """Помилка отримання погоди з HTTP-статусом для веб-рівня."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Виконує GET-запит і перевіряє статус та формат відповіді."""
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise WeatherError("Сервіс погоди не відповів вчасно. Спробуйте ще раз.", 504) from exc
    except requests.HTTPError as exc:
        # Помилка зовнішнього сервісу не є помилкою запиту до нашого застосунку.
        status = exc.response.status_code if exc.response is not None else None
        if status is not None and status >= 500:
            raise WeatherError("Зовнішній сервіс погоди тимчасово недоступний.", 503) from exc
        raise WeatherError("Зовнішній сервіс не зміг обробити запит.", 502) from exc
    except requests.RequestException as exc:
        raise WeatherError("Не вдалося з'єднатися із сервісом погоди.", 503) from exc

    try:
        data = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError) as exc:
        raise WeatherError("Сервіс погоди повернув некоректні дані.", 502) from exc

    if not isinstance(data, dict):
        raise WeatherError("Сервіс погоди повернув дані неочікуваного формату.", 502)
    return data


def find_city(name: str) -> dict[str, Any]:
    """Знаходить місто та повертає його назву, країну й координати."""
    city_name = name.strip()
    if not city_name:
        raise WeatherError("Введіть назву міста.", 422)

    data = _get_json(
        GEOCODING_URL,
        {"name": city_name, "count": 1, "language": "uk", "format": "json"},
    )
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise WeatherError(f"Місто «{city_name}» не знайдено. Перевірте назву.", 404)

    city = results[0]
    if not isinstance(city, dict):
        raise WeatherError("Сервіс пошуку міст повернув некоректні дані.", 502)

    try:
        latitude = float(city["latitude"])
        longitude = float(city["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("У відповіді пошуку міста немає коректних координат.", 502) from exc

    return {
        "name": str(city.get("name", city_name)),
        "country": str(city.get("country", "")),
        "latitude": latitude,
        "longitude": longitude,
    }


def get_current_weather(city: str) -> dict[str, Any]:
    """Повертає поточну температуру та швидкість вітру для міста."""
    location = find_city(city)
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "temperature_2m,wind_speed_10m",
        },
    )

    current = data.get("current")
    units = data.get("current_units", {})
    if not isinstance(current, dict) or not isinstance(units, dict):
        raise WeatherError("У відповіді прогнозу немає даних про поточну погоду.", 502)

    try:
        temperature = float(current["temperature_2m"])
        wind_speed = float(current["wind_speed_10m"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("Сервіс не повернув температуру або швидкість вітру.", 502) from exc

    return {
        "city": location["name"],
        "country": location["country"],
        "temperature": temperature,
        "temperature_unit": str(units.get("temperature_2m", "°C")),
        "wind_speed": wind_speed,
        "wind_speed_unit": str(units.get("wind_speed_10m", "km/h")),
    }
