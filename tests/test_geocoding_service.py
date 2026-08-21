import pytest

from app.services.geocoding_service import GeocodingNotFound, GeocodingUnavailable, build_result


def ban_payload(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def feature(longitude: float, latitude: float, **properties) -> dict:
    return {
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {"label": "Caen 14000", **properties},
    }


def test_reads_the_best_ranked_result():
    payload = ban_payload(feature(-0.3707, 49.1829, postcode="14000", city="Caen"))
    result = build_result(payload)
    assert result.latitude == pytest.approx(49.1829)
    assert result.longitude == pytest.approx(-0.3707)
    assert result.label == "Caen 14000"
    assert result.postcode == "14000"
    assert result.city == "Caen"


def test_ignores_results_after_the_first():
    payload = ban_payload(
        feature(-0.3707, 49.1829, city="Caen"),
        feature(-0.2725, 49.2764, city="Ouistreham"),
    )
    result = build_result(payload)
    assert result.city == "Caen"


def test_missing_optional_properties_default_to_none():
    payload = ban_payload(feature(-0.3707, 49.1829))
    result = build_result(payload)
    assert result.postcode is None
    assert result.city is None


def test_rejects_an_empty_result_set():
    with pytest.raises(GeocodingNotFound):
        build_result(ban_payload())


def test_rejects_a_payload_without_features():
    with pytest.raises(GeocodingUnavailable):
        build_result({})


def test_rejects_a_malformed_feature():
    with pytest.raises(GeocodingUnavailable):
        build_result(ban_payload({"geometry": {}, "properties": {}}))
