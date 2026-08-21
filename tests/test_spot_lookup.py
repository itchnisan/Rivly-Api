import pytest

from app.core.deps import get_geocoding_provider, get_water_type_provider
from app.main import app
from app.services.geocoding_service import GeocodingNotFound, GeocodingResult, GeocodingUnavailable
from app.services.overpass_service import WaterTypeDetection, WaterTypeDetectionUnavailable


class StubGeocodingProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.queries: list[str] = []

    async def geocode(self, query):
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.result or GeocodingResult(
            latitude=49.1829, longitude=-0.3707, label="Caen 14000", postcode="14000", city="Caen"
        )


class StubWaterTypeProvider:
    def __init__(self, water_types=frozenset(), error=None):
        self.water_types = water_types
        self.error = error
        self.calls: list[tuple[float, float]] = []

    async def get_water_types(self, latitude, longitude, radius_meters=5000):
        self.calls.append((latitude, longitude))
        if self.error is not None:
            raise self.error
        return WaterTypeDetection(water_types=self.water_types)


def use_geocoding(provider):
    app.dependency_overrides[get_geocoding_provider] = lambda: provider
    return provider


def use_water_types(provider):
    app.dependency_overrides[get_water_type_provider] = lambda: provider
    return provider


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_geocoding_provider, None)
    app.dependency_overrides.pop(get_water_type_provider, None)


async def test_lookup_by_postal_code_geocodes_then_detects_water_types(client):
    use_geocoding(StubGeocodingProvider())
    use_water_types(StubWaterTypeProvider(water_types=frozenset({"river", "canal"})))

    resp = await client.get("/api/v1/spots/lookup", params={"q": "14000"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["latitude"] == pytest.approx(49.1829)
    assert body["longitude"] == pytest.approx(-0.3707)
    assert body["label"] == "Caen 14000"
    assert set(body["available_water_types"]) == {"river", "canal"}


async def test_lookup_by_coordinates_skips_geocoding(client):
    geocoding = use_geocoding(StubGeocodingProvider())
    use_water_types(StubWaterTypeProvider(water_types=frozenset({"sea", "canal"})))

    resp = await client.get(
        "/api/v1/spots/lookup", params={"latitude": 49.2764, "longitude": -0.2725}
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["label"] is None
    assert set(body["available_water_types"]) == {"sea", "canal"}
    assert geocoding.queries == []


async def test_lookup_without_query_or_coordinates_is_rejected(client):
    use_geocoding(StubGeocodingProvider())
    use_water_types(StubWaterTypeProvider())

    resp = await client.get("/api/v1/spots/lookup")
    assert resp.status_code == 400


async def test_lookup_on_unknown_location_returns_404(client):
    use_geocoding(StubGeocodingProvider(error=GeocodingNotFound("introuvable")))
    use_water_types(StubWaterTypeProvider())

    resp = await client.get("/api/v1/spots/lookup", params={"q": "nimportequoi"})
    assert resp.status_code == 404


async def test_lookup_returns_503_when_geocoding_is_unavailable(client):
    use_geocoding(StubGeocodingProvider(error=GeocodingUnavailable("connexion refusée")))
    use_water_types(StubWaterTypeProvider())

    resp = await client.get("/api/v1/spots/lookup", params={"q": "14000"})
    assert resp.status_code == 503


async def test_lookup_returns_503_when_water_type_detection_is_unavailable(client):
    use_geocoding(StubGeocodingProvider())
    use_water_types(StubWaterTypeProvider(error=WaterTypeDetectionUnavailable("connexion refusée")))

    resp = await client.get("/api/v1/spots/lookup", params={"q": "14000"})
    assert resp.status_code == 503


async def test_lookup_is_public(client):
    use_geocoding(StubGeocodingProvider())
    use_water_types(StubWaterTypeProvider())

    resp = await client.get("/api/v1/spots/lookup", params={"q": "14000"})
    assert resp.status_code == 200
