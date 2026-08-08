from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.deps import get_weather_provider
from app.main import app
from app.models.species import Species
from app.services import fishability_service
from app.services.weather_service import (
    ForecastOutOfRange,
    WeatherSnapshot,
    WeatherUnavailable,
    build_snapshot,
)

REFERENCE_DAY = datetime(2026, 8, 8, tzinfo=timezone.utc)


def make_snapshot(**overrides) -> WeatherSnapshot:
    """Conditions neutres, à surcharger facteur par facteur selon le test."""
    defaults = {
        "at": REFERENCE_DAY.replace(hour=12),
        "temperature_c": 18.0,
        "pressure_hpa": 1013.0,
        "pressure_trend_hpa": 0.0,
        "cloud_cover_pct": 50.0,
        "wind_speed_kmh": 10.0,
        "precipitation_mm": 0.0,
        "sunrise": REFERENCE_DAY.replace(hour=6),
        "sunset": REFERENCE_DAY.replace(hour=21),
    }
    return WeatherSnapshot(**{**defaults, **overrides})


def score_of(**overrides) -> int:
    return fishability_service.compute_fishability(make_snapshot(**overrides))["score"]


# --- Scoring : facteurs pris isolément -------------------------------------


def test_falling_pressure_beats_rising_pressure():
    assert score_of(pressure_trend_hpa=-1.5) > score_of(pressure_trend_hpa=3.0)


def test_sharp_pressure_drop_scores_below_gentle_drop():
    assert score_of(pressure_trend_hpa=-7.0) < score_of(pressure_trend_hpa=-1.5)


def test_dawn_beats_midday():
    dawn = make_snapshot(at=REFERENCE_DAY.replace(hour=6))
    midday = make_snapshot(at=REFERENCE_DAY.replace(hour=13))
    assert (
        fishability_service.compute_fishability(dawn)["score"]
        > fishability_service.compute_fishability(midday)["score"]
    )


def test_overcast_beats_clear_sky():
    assert score_of(cloud_cover_pct=70) > score_of(cloud_cover_pct=0)


def test_breeze_beats_dead_calm_and_gale():
    breeze = score_of(wind_speed_kmh=10)
    assert breeze > score_of(wind_speed_kmh=0)
    assert breeze > score_of(wind_speed_kmh=50)


def test_light_rain_beats_downpour():
    assert score_of(precipitation_mm=0.3) > score_of(precipitation_mm=12)


def test_temperate_water_beats_freezing_and_scorching():
    mild = score_of(temperature_c=18)
    assert mild > score_of(temperature_c=-4)
    assert mild > score_of(temperature_c=36)


def test_score_stays_within_bounds_across_extremes():
    extremes = [
        make_snapshot(
            pressure_trend_hpa=-20,
            temperature_c=-30,
            cloud_cover_pct=0,
            wind_speed_kmh=120,
            precipitation_mm=60,
        ),
        make_snapshot(
            pressure_trend_hpa=20,
            temperature_c=50,
            cloud_cover_pct=100,
            wind_speed_kmh=0,
            precipitation_mm=0,
        ),
    ]
    for snapshot in extremes:
        assert 0 <= fishability_service.compute_fishability(snapshot)["score"] <= 100


def test_factor_weights_sum_to_one_hundred():
    assert sum(fishability_service.FACTOR_WEIGHTS.values()) == 100


def test_factors_are_all_reported_with_their_contribution():
    result = fishability_service.compute_fishability(make_snapshot())
    factors = result["factors"]

    assert {f["name"] for f in factors} == set(fishability_service.FACTOR_WEIGHTS)
    for factor in factors:
        assert 0 <= factor["score"] <= 1
        assert factor["detail"]
        assert factor["contribution"] == pytest.approx(factor["weight"] * factor["score"], abs=0.01)


# --- Lune -------------------------------------------------------------------


def test_moon_illumination_completes_a_cycle_in_a_synodic_month():
    start = fishability_service.moon_illumination(REFERENCE_DAY)
    later = fishability_service.moon_illumination(
        REFERENCE_DAY + timedelta(days=fishability_service.SYNODIC_MONTH_DAYS)
    )
    assert later == pytest.approx(start, abs=0.01)


def test_moon_illumination_is_halfway_at_half_a_cycle():
    half = fishability_service.moon_illumination(
        REFERENCE_DAY + timedelta(days=fishability_service.SYNODIC_MONTH_DAYS / 2)
    )
    start = fishability_service.moon_illumination(REFERENCE_DAY)
    assert abs(half - start) == pytest.approx(0.5, abs=0.01)


# --- Saison -----------------------------------------------------------------


def test_species_without_season_returns_unknown():
    species = Species(name="X", common_name="X")
    assert fishability_service.is_species_in_season(species, date(2026, 8, 8)) is None


def test_simple_season_covers_its_own_months_only():
    species = Species(
        name="X",
        common_name="X",
        open_season_start=date(2026, 5, 1),
        open_season_end=date(2026, 9, 30),
    )
    assert fishability_service.is_species_in_season(species, date(2027, 6, 15)) is True
    assert fishability_service.is_species_in_season(species, date(2027, 3, 1)) is False


def test_season_wrapping_new_year_is_handled():
    """Le brochet ouvre au printemps et ferme fin janvier : la saison enjambe l'année."""
    species = Species(
        name="Esox lucius",
        common_name="Brochet",
        open_season_start=date(2026, 5, 1),
        open_season_end=date(2027, 1, 31),
    )
    assert fishability_service.is_species_in_season(species, date(2026, 12, 20)) is True
    assert fishability_service.is_species_in_season(species, date(2027, 1, 15)) is True
    assert fishability_service.is_species_in_season(species, date(2027, 3, 10)) is False


def test_out_of_season_species_forces_score_to_zero():
    species = Species(
        name="Esox lucius",
        common_name="Brochet",
        open_season_start=date(2026, 5, 1),
        open_season_end=date(2026, 6, 30),
    )
    # Conditions par ailleurs excellentes.
    snapshot = make_snapshot(pressure_trend_hpa=-1.5, at=REFERENCE_DAY.replace(hour=6))
    assert fishability_service.compute_fishability(snapshot)["score"] > 0

    blocked = fishability_service.compute_fishability(snapshot, species)
    assert blocked["score"] == 0
    assert any(a["level"] == "blocking" for a in blocked["advisories"])


def test_legal_size_is_reported_as_an_advisory():
    species = Species(name="X", common_name="Brochet", legal_size_cm=60)
    result = fishability_service.compute_fishability(make_snapshot(), species)
    assert any("60 cm" in a["message"] for a in result["advisories"])


# --- Lecture de la réponse Open-Meteo ---------------------------------------


def open_meteo_payload(hours: int = 12) -> dict:
    times = [REFERENCE_DAY + timedelta(hours=h) for h in range(hours)]
    return {
        "hourly": {
            "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
            "temperature_2m": [15.0 + h * 0.5 for h in range(hours)],
            # Pression décroissante : 1 hPa par heure.
            "surface_pressure": [1020.0 - h for h in range(hours)],
            "cloud_cover": [40.0] * hours,
            "wind_speed_10m": [12.0] * hours,
            "precipitation": [0.0] * hours,
        },
        "daily": {
            "time": [REFERENCE_DAY.strftime("%Y-%m-%d")],
            "sunrise": [REFERENCE_DAY.replace(hour=6).strftime("%Y-%m-%dT%H:%M")],
            "sunset": [REFERENCE_DAY.replace(hour=21).strftime("%Y-%m-%dT%H:%M")],
        },
    }


def test_build_snapshot_reads_the_matching_hour():
    snapshot = build_snapshot(open_meteo_payload(), REFERENCE_DAY.replace(hour=5))
    assert snapshot.at == REFERENCE_DAY.replace(hour=5)
    assert snapshot.temperature_c == pytest.approx(17.5)
    assert snapshot.pressure_hpa == pytest.approx(1015.0)


def test_build_snapshot_computes_pressure_trend_over_three_hours():
    snapshot = build_snapshot(open_meteo_payload(), REFERENCE_DAY.replace(hour=6))
    assert snapshot.pressure_trend_hpa == pytest.approx(-3.0)


def test_build_snapshot_reports_no_trend_when_history_is_missing():
    """En tout début de série la tendance n'est pas mesurable : elle vaut 0, pas une valeur inventée."""
    snapshot = build_snapshot(open_meteo_payload(), REFERENCE_DAY.replace(hour=1))
    assert snapshot.pressure_trend_hpa == 0.0


def test_build_snapshot_rejects_a_date_outside_the_forecast_window():
    with pytest.raises(ForecastOutOfRange):
        build_snapshot(open_meteo_payload(), REFERENCE_DAY + timedelta(days=30))


def test_build_snapshot_rejects_an_unusable_payload():
    with pytest.raises(WeatherUnavailable):
        build_snapshot({"hourly": {}}, REFERENCE_DAY)


def test_build_snapshot_rejects_an_incomplete_series():
    payload = open_meteo_payload()
    payload["hourly"]["cloud_cover"] = [40.0]
    with pytest.raises(WeatherUnavailable):
        build_snapshot(payload, REFERENCE_DAY.replace(hour=5))


# --- Endpoint ---------------------------------------------------------------


class StubWeatherProvider:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls: list[tuple[float, float, datetime]] = []

    async def get_snapshot(self, latitude, longitude, at):
        self.calls.append((latitude, longitude, at))
        if self.error is not None:
            raise self.error
        return self.snapshot or make_snapshot()


def use_weather(provider):
    app.dependency_overrides[get_weather_provider] = lambda: provider
    return provider


@pytest.fixture(autouse=True)
def clear_weather_override():
    yield
    app.dependency_overrides.pop(get_weather_provider, None)


async def create_spot(client, register_user, email="fish@example.com", username="fisher"):
    headers = await register_user(email=email, username=username)
    resp = await client.post(
        "/api/v1/spots",
        json={"name": "Etang test", "latitude": 48.85, "longitude": 2.35, "water_type": "pond"},
        headers=headers,
    )
    return resp.json()["id"]


async def test_fishability_returns_a_scored_breakdown(client, register_user):
    spot_id = await create_spot(client, register_user)
    use_weather(StubWeatherProvider(make_snapshot(pressure_trend_hpa=-1.5)))

    resp = await client.get(f"/api/v1/spots/{spot_id}/fishability")
    assert resp.status_code == 200

    body = resp.json()
    assert body["spot_id"] == spot_id
    assert 0 <= body["score"] <= 100
    assert body["rating"] in {"poor", "fair", "good", "excellent"}
    assert len(body["factors"]) == len(fishability_service.FACTOR_WEIGHTS)
    assert body["weather"]["pressure_trend_hpa"] == -1.5


async def test_fishability_uses_the_spot_coordinates(client, register_user):
    spot_id = await create_spot(client, register_user, "coord@example.com", "coord")
    provider = use_weather(StubWeatherProvider())

    await client.get(f"/api/v1/spots/{spot_id}/fishability")

    latitude, longitude, _ = provider.calls[0]
    assert (latitude, longitude) == (48.85, 2.35)


async def test_fishability_honours_the_requested_datetime(client, register_user):
    spot_id = await create_spot(client, register_user, "when@example.com", "whenuser")
    provider = use_weather(StubWeatherProvider())

    await client.get(
        f"/api/v1/spots/{spot_id}/fishability", params={"at": "2026-08-09T06:00:00Z"}
    )

    _, _, requested = provider.calls[0]
    assert requested == datetime(2026, 8, 9, 6, tzinfo=timezone.utc)


async def test_fishability_defaults_to_now_when_no_date_is_given(client, register_user):
    spot_id = await create_spot(client, register_user, "now@example.com", "nowuser")
    provider = use_weather(StubWeatherProvider())

    await client.get(f"/api/v1/spots/{spot_id}/fishability")

    _, _, requested = provider.calls[0]
    assert abs((requested - datetime.now(timezone.utc)).total_seconds()) < 60


async def test_fishability_is_public(client, register_user):
    """Consulter les conditions ne demande pas de compte, contrairement à la création de spot."""
    spot_id = await create_spot(client, register_user, "anon@example.com", "anonuser")
    use_weather(StubWeatherProvider())

    resp = await client.get(f"/api/v1/spots/{spot_id}/fishability")
    assert resp.status_code == 200


async def test_fishability_on_missing_spot_returns_404(client):
    use_weather(StubWeatherProvider())
    resp = await client.get("/api/v1/spots/999999/fishability")
    assert resp.status_code == 404


async def test_fishability_with_missing_species_returns_404(client, register_user):
    spot_id = await create_spot(client, register_user, "sp404@example.com", "sp404")
    use_weather(StubWeatherProvider())

    resp = await client.get(
        f"/api/v1/spots/{spot_id}/fishability", params={"species_id": 999999}
    )
    assert resp.status_code == 404


async def test_fishability_blocks_an_out_of_season_species(client, register_user, db_session):
    spot_id = await create_spot(client, register_user, "season@example.com", "seasonuser")
    species = Species(
        name="Esox lucius",
        common_name="Brochet",
        open_season_start=date(2026, 1, 1),
        open_season_end=date(2026, 2, 28),
    )
    db_session.add(species)
    await db_session.commit()

    use_weather(StubWeatherProvider(make_snapshot(at=REFERENCE_DAY.replace(hour=6))))

    resp = await client.get(
        f"/api/v1/spots/{spot_id}/fishability", params={"species_id": species.id}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 0
    assert body["species_id"] == species.id
    assert any(a["level"] == "blocking" for a in body["advisories"])


async def test_fishability_returns_503_when_weather_is_unavailable(client, register_user):
    spot_id = await create_spot(client, register_user, "down@example.com", "downuser")
    use_weather(StubWeatherProvider(error=WeatherUnavailable("connexion refusée")))

    resp = await client.get(f"/api/v1/spots/{spot_id}/fishability")
    assert resp.status_code == 503


async def test_fishability_returns_422_when_date_is_out_of_range(client, register_user):
    spot_id = await create_spot(client, register_user, "range@example.com", "rangeuser")
    use_weather(StubWeatherProvider(error=ForecastOutOfRange("hors fenêtre")))

    resp = await client.get(
        f"/api/v1/spots/{spot_id}/fishability", params={"at": "2030-01-01T12:00:00Z"}
    )
    assert resp.status_code == 422
