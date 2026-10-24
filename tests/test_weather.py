import pytest

import weather
from recommendation.profile import SkinProfile
from weather import WeatherError, WeatherService, round_coords, skin_tips, uv_band

FORECAST = {
    "current": {"temperature_2m": 27.5, "relative_humidity_2m": 78, "uv_index": 5.1, "time": "2026-10-25T12:00"},
    "daily": {"uv_index_max": [7.2], "temperature_2m_max": [29.0], "temperature_2m_min": [19.0]},
}


@pytest.fixture
def calls(monkeypatch):
    log = []

    def fake_get(url, params, trust_env):
        log.append((url, params))
        if url == weather.GEOCODING_URL:
            return {"results": [{"name": "İstanbul", "admin1": "İstanbul", "country": "Türkiye", "latitude": 41.01384, "longitude": 28.94966}]}
        return FORECAST

    monkeypatch.setattr(weather, "_get", fake_get)
    return log


def test_only_rounded_coordinates_leave_the_server_and_answers_are_cached(calls):
    clock = [0.0]
    service = WeatherService(clock=lambda: clock[0])
    result = service.today(41.013841, 28.949661)
    assert result["uv_max"] == 7.2 and result["humidity"] == 78
    assert calls[0][1]["latitude"] == 41.0 and calls[0][1]["longitude"] == 28.9
    service.today(41.04, 28.92)  # same rounded cell
    assert len(calls) == 1
    clock[0] = weather.CACHE_SECONDS + 1
    service.today(41.0, 28.9)
    assert len(calls) == 2


def test_search_returns_rounded_places(calls):
    places = WeatherService().search("ist")
    assert places == [{"name": "İstanbul", "region": "İstanbul, Türkiye", "lat": 41.0, "lon": 28.9}]
    assert WeatherService().search("i") == []


def test_invalid_coordinates_and_network_errors(monkeypatch):
    with pytest.raises(WeatherError):
        round_coords(95, 10)

    class Broken:
        trust_env = False

        def get(self, *args, **kwargs):
            raise weather.requests.ConnectionError

        def close(self):
            pass

    monkeypatch.setattr(weather.requests, "Session", Broken)
    with pytest.raises(WeatherError, match="alınamadı"):
        WeatherService().today(41, 29)


def test_uv_bands():
    assert uv_band(None) is None
    assert [uv_band(value)["key"] for value in (0, 2.9, 3, 6, 8, 11)] == ["low", "low", "moderate", "high", "very_high", "extreme"]


def test_tips_follow_weather_profile_and_actives():
    hot_humid = {"uv_max": 7.2, "temperature": 27.5, "humidity": 78}
    tips = skin_tips(hot_humid, SkinProfile(skin_type="oily"), ["retinol"])
    kinds = [tip["kind"] for tip in tips]
    assert kinds[0] == "uv" and "2 saatte bir" in tips[0]["text"]
    assert "actives" in kinds and "Retinol" in tips[kinds.index("actives")]["text"]
    assert "parlama" in tips[kinds.index("humidity")]["text"]
    cold_dry = skin_tips({"uv_max": 1, "temperature": 2, "humidity": 25}, SkinProfile(skin_type="dry"), ["retinol"])
    assert [tip["kind"] for tip in cold_dry] == ["uv", "humidity", "temperature"]
    assert "zengin" in cold_dry[1]["text"] and cold_dry[0]["tone"] == "good"
