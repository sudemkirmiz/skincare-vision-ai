# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Today's UV, temperature and humidity (Open-Meteo, no API key) turned into skincare tips.

Only coordinates rounded to one decimal (~10 km) leave the server, nothing about the user. Answers
are cached for 30 minutes per rounded location, so a page refresh never costs another request.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

from recommendation.profile import SkinProfile

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_SECONDS = 8
CACHE_SECONDS = 30 * 60
COORD_DECIMALS = 1

# WHO UV index bands.
UV_BANDS = [(3, "low", "Düşük"), (6, "moderate", "Orta"), (8, "high", "Yüksek"), (11, "very_high", "Çok yüksek"), (99, "extreme", "Aşırı")]
DRY_AIR = 35  # relative humidity %
HUMID_AIR = 70
COLD = 5  # °C
HOT = 30
WARM = 24
PHOTOSENSITISING = {"retinol": "Retinol", "aha": "AHA", "bha": "BHA (salisilik asit)"}


class WeatherError(RuntimeError):
    """Raised with a Turkish, user-facing message."""


def _get(url: str, params: dict[str, Any], trust_env: bool) -> dict[str, Any]:
    session = requests.Session()
    session.trust_env = trust_env
    try:
        response = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("Weather request failed: %s", type(error).__name__)
        raise WeatherError("Hava durumu şu an alınamadı; biraz sonra tekrar deneyin.") from None
    finally:
        session.close()


def round_coords(lat: float, lon: float) -> tuple[float, float]:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise WeatherError("Geçersiz konum.")
    return round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)


def uv_band(uv: float | None) -> dict[str, str] | None:
    if uv is None:
        return None
    key, label = next((key, label) for limit, key, label in UV_BANDS if uv < limit)
    return {"key": key, "label": label}


def skin_tips(weather: dict[str, Any], profile: SkinProfile, actives: list[str]) -> list[dict[str, str]]:
    """Ordered most important first. `actives` are ingredient ids in use (routine + current)."""
    tips: list[dict[str, str]] = []
    uv = weather.get("uv_max")
    temperature = weather.get("temperature")
    humidity = weather.get("humidity")
    if uv is not None:
        if uv >= 8:
            tips.append({"kind": "uv", "tone": "warn", "title": "UV çok yüksek",
                         "text": "SPF 50 güneş koruyucu sürün ve dışarıdaysanız 2 saatte bir yenileyin. 11:00–16:00 arası gölgede kalın; şapka ve güneş gözlüğü kullanın."})
        elif uv >= 6:
            tips.append({"kind": "uv", "tone": "warn", "title": "UV yüksek",
                         "text": "SPF 50 tercih edin, dışarıdaysanız 2 saatte bir yenileyin ve öğle saatlerinde gölgede kalın."})
        elif uv >= 3:
            tips.append({"kind": "uv", "tone": "info", "title": "UV orta",
                         "text": "Sabah SPF 30+ güneş koruyucu yeterli; uzun süre dışarıda kalacaksanız yenileyin."})
        else:
            tips.append({"kind": "uv", "tone": "good", "title": "UV düşük",
                         "text": "Bugün UV düşük; yine de güneş koruyucu alışkanlığınızı sürdürmek leke görünümünü önlemeye yardımcı olur."})
        sensitising = [PHOTOSENSITISING[active] for active in actives if active in PHOTOSENSITISING]
        if sensitising and uv >= 3:
            tips.append({"kind": "actives", "tone": "warn", "title": "Aktifleriniz güneşe duyarlılığı artırabilir",
                         "text": f"{', '.join(dict.fromkeys(sensitising))} kullandığınız için bugün güneş korumasını aksatmayın ve bu aktifleri akşam kullanın."})
    if humidity is not None and humidity < DRY_AIR:
        richer = profile.skin_type in {"dry", "combination"} or profile.is_sensitive
        tips.append({"kind": "humidity", "tone": "info", "title": "Hava kuru",
                     "text": "Nemlendiriciyi yüzünüz hafif nemliyken sürün" + ("; bugün daha zengin bir krem iyi gelebilir." if richer else ".")})
    elif humidity is not None and humidity > HUMID_AIR and temperature is not None and temperature >= WARM:
        oily = profile.skin_type in {"oily", "combination"}
        tips.append({"kind": "humidity", "tone": "info", "title": "Hava sıcak ve nemli",
                     "text": "Hafif jel dokular tercih edin" + ("; gün ortasında parlama için kâğıt mendil işinize yarar." if oily else ".")})
    if temperature is not None and temperature <= COLD:
        tips.append({"kind": "temperature", "tone": "info", "title": "Hava soğuk",
                     "text": "Soğuk ve rüzgâr cilt bariyerini zorlar: ılık suyla yıkayın, bariyer destekleyici (seramidli) bir nemlendirici kullanın."})
    elif temperature is not None and temperature >= HOT:
        tips.append({"kind": "temperature", "tone": "info", "title": "Hava çok sıcak",
                     "text": "Terledikten sonra yüzünüzü nazikçe yıkayın; ağır kremler yerine hafif dokular seçin."})
    return tips


class WeatherService:
    def __init__(self, trust_env: bool = False, clock=time.monotonic) -> None:
        self.trust_env = trust_env
        self._clock = clock
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def search(self, query: str) -> list[dict[str, Any]]:
        query = query.strip()
        if len(query) < 2:
            return []
        data = _get(GEOCODING_URL, {"name": query[:60], "count": 5, "language": "tr", "format": "json"}, self.trust_env)
        places = []
        for place in data.get("results") or []:
            lat, lon = round_coords(float(place["latitude"]), float(place["longitude"]))
            region = ", ".join(part for part in (place.get("admin1"), place.get("country")) if part)
            places.append({"name": place.get("name", ""), "region": region, "lat": lat, "lon": lon})
        return places

    def today(self, lat: float, lon: float) -> dict[str, Any]:
        key = round_coords(lat, lon)
        with self._lock:
            cached = self._cache.get(key)
            if cached and self._clock() - cached[0] < CACHE_SECONDS:
                return cached[1]
        data = _get(FORECAST_URL, {
            "latitude": key[0], "longitude": key[1], "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,relative_humidity_2m,uv_index",
            "daily": "uv_index_max,temperature_2m_max,temperature_2m_min",
        }, self.trust_env)
        try:
            current, daily = data["current"], data["daily"]
            weather = {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "uv_now": current.get("uv_index"),
                "uv_max": (daily.get("uv_index_max") or [None])[0],
                "temp_max": (daily.get("temperature_2m_max") or [None])[0],
                "temp_min": (daily.get("temperature_2m_min") or [None])[0],
                "time": current.get("time"),
            }
        except (KeyError, TypeError):
            raise WeatherError("Hava durumu yanıtı okunamadı.") from None
        with self._lock:
            self._cache[key] = (self._clock(), weather)
        return weather
