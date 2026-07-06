import logging
from typing import Any

import httpx
from sqlmodel import Session, col, select

from app.config import settings
from app.models.log_entry import LogEntry

logger = logging.getLogger(__name__)


def _fetch_openweather(
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None,
) -> dict | None:
    """
    Fetch current weather from OpenWeatherMap.
    Uses coordinates when provided, then city name when provided, otherwise falls back
    to the configured default city.
    """
    if not settings.openweather_api_key:
        return None
    try:
        params: dict[str, Any]
        if lat is not None and lon is not None:
            params = {"lat": lat, "lon": lon}
        elif city:
            params = {"q": city}
        else:
            params = {"q": f"{settings.openweather_city},{settings.openweather_country_code}"}

        r = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={**params, "appid": settings.openweather_api_key, "units": "imperial"},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        main = data.get("main", {})
        sys = data.get("sys", {})
        return {
            "barometric_pressure_hpa": main.get("pressure"),
            "temperature_f": main.get("temp"),
            "humidity_pct": main.get("humidity"),
            "city_name": data.get("name"),
            "country_code": sys.get("country"),
        }
    except Exception as e:
        logger.warning("OpenWeatherMap fetch failed: %s", e)
        return None


def _fetch_airnow() -> dict | None:
    if not settings.airnow_api_key:
        return None
    try:
        r = httpx.get(
            "https://www.airnowapi.org/aq/observation/zipCode/current/",
            params={
                "format": "application/json",
                "zipCode": settings.airnow_zip,
                "distance": 25,
                "API_KEY": settings.airnow_api_key,
            },
            timeout=5,
        )
        r.raise_for_status()
        observations = r.json()
        if not observations:
            return None
        best = max(observations, key=lambda o: o.get("AQI", 0))
        return {
            "aqi": best.get("AQI"),
            "dominant_pollutant": best.get("ParameterName"),
        }
    except Exception as e:
        logger.warning("AirNow fetch failed: %s", e)
        return None


def _pressure_delta(session: Session, current_hpa: float, current_id: int) -> float | None:
    """
    Compute delta vs. the most recent prior log entry that has a barometric reading.
    Excludes the current entry since its pressure is being set for the first time.
    """
    prev = session.exec(
        select(LogEntry)
        .where(
            col(LogEntry.barometric_pressure_hpa).is_not(None),
            LogEntry.id != current_id,
        )
        .order_by(col(LogEntry.created_at).desc())
    ).first()
    if prev is None or prev.barometric_pressure_hpa is None:
        return None
    return round(current_hpa - prev.barometric_pressure_hpa, 2)


def append_weather(
    session: Session,
    entry: LogEntry,
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None,
) -> None:
    """
    Fetch current weather using the provided city (or coordinates if given), otherwise the
    configured default city. Writes all weather fields plus location_city onto the
    already-persisted entry. Silently no-ops if API keys are absent or calls fail.
    """
    weather = _fetch_openweather(lat=lat, lon=lon, city=city)
    if not weather:
        return

    pressure = weather.get("barometric_pressure_hpa")
    entry.barometric_pressure_hpa = pressure
    entry.temperature_f = weather.get("temperature_f")
    entry.humidity_pct = weather.get("humidity_pct")

    city = weather.get("city_name")
    country = weather.get("country_code")
    if city:
        entry.location_city = f"{city}, {country}" if country else city

    if pressure is not None:
        assert entry.id is not None
        entry.pressure_delta_24h = _pressure_delta(session, pressure, entry.id)

    aqi_data = _fetch_airnow()
    if aqi_data:
        entry.aqi = aqi_data.get("aqi")
        entry.dominant_pollutant = aqi_data.get("dominant_pollutant")

    session.add(entry)
    session.commit()
    session.refresh(entry)
