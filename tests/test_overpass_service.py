import pytest

from app.services.overpass_service import WaterTypeDetectionUnavailable, build_detection


def overpass_payload(*elements: dict) -> dict:
    return {"elements": list(elements)}


def way(tags: dict) -> dict:
    return {"type": "way", "tags": tags}


def test_detects_a_river_from_a_waterway_tag():
    detection = build_detection(overpass_payload(way({"waterway": "river"})))
    assert detection.water_types == frozenset({"river"})


def test_detects_a_stream_as_a_river():
    detection = build_detection(overpass_payload(way({"waterway": "stream"})))
    assert detection.water_types == frozenset({"river"})


def test_detects_a_canal():
    detection = build_detection(overpass_payload(way({"waterway": "canal"})))
    assert detection.water_types == frozenset({"canal"})


def test_detects_the_sea_from_a_coastline():
    detection = build_detection(overpass_payload(way({"natural": "coastline"})))
    assert detection.water_types == frozenset({"sea"})


def test_detects_a_lake_from_natural_water():
    detection = build_detection(overpass_payload(way({"natural": "water", "water": "lake"})))
    assert detection.water_types == frozenset({"lake"})


def test_detects_a_pond_from_natural_water():
    detection = build_detection(overpass_payload(way({"natural": "water", "water": "pond"})))
    assert detection.water_types == frozenset({"pond"})


def test_natural_water_without_a_water_tag_defaults_to_lake():
    detection = build_detection(overpass_payload(way({"natural": "water"})))
    assert detection.water_types == frozenset({"lake"})


def test_combines_every_type_found_around_the_point():
    """Caen : l'Orne (rivière) et le canal de Caen à la mer se croisent dans la même zone."""
    detection = build_detection(
        overpass_payload(
            way({"waterway": "river"}),
            way({"waterway": "canal"}),
        )
    )
    assert detection.water_types == frozenset({"river", "canal"})


def test_ignores_unrelated_tags():
    detection = build_detection(overpass_payload(way({"highway": "residential"})))
    assert detection.water_types == frozenset()


def test_ignores_an_element_without_tags():
    detection = build_detection(overpass_payload({"type": "way"}))
    assert detection.water_types == frozenset()


def test_rejects_a_payload_without_elements():
    with pytest.raises(WaterTypeDetectionUnavailable):
        build_detection({})
