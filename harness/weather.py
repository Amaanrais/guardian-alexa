"""Current weather for the top bar, from Open-Meteo (no API key; only the coordinates are sent)."""
import os
import time

import httpx

LAT = float(os.getenv("WEATHER_LAT", "51.5072"))   # default: London
LON = float(os.getenv("WEATHER_LON", "-0.1276"))
CACHE_S = 15 * 60
_cache: tuple[float, dict | None] = (0.0, None)

# WMO weather codes -> (icon, words)
_KINDS = [
    ((0,), "sun", "Clear"), ((1, 2), "partly", "Partly cloudy"), ((3,), "cloud", "Cloudy"),
    ((45, 48), "fog", "Foggy"), (tuple(range(51, 68)) + (80, 81, 82), "rain", "Rain"),
    (tuple(range(71, 78)) + (85, 86), "snow", "Snow"), ((95, 96, 99), "storm", "Thunderstorms"),
]


async def current() -> dict | None:
    """{temp, icon, words}, or None if the lookup fails. Cached for 15 minutes."""
    global _cache
    if time.time() - _cache[0] < CACHE_S:
        return _cache[1]
    result = None
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": LAT, "longitude": LON, "current": "temperature_2m,weather_code,is_day"})
            cur = resp.raise_for_status().json()["current"]
        icon, words = next(((i, w) for codes, i, w in _KINDS if cur["weather_code"] in codes), ("cloud", "Cloudy"))
        if icon == "sun" and not cur.get("is_day", 1):
            icon = "moon"
        result = {"temp": round(cur["temperature_2m"]), "icon": icon, "words": words}
    except Exception:
        pass
    _cache = (time.time(), result)
    return result
