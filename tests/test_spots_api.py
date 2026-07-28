async def test_create_spot_requires_auth(client):
    resp = await client.post(
        "/api/v1/spots",
        json={"name": "x", "latitude": 1, "longitude": 1, "water_type": "river"},
    )
    assert resp.status_code == 401


async def test_create_and_get_spot(client, register_user):
    headers = await register_user(email="owner@example.com", username="owner")

    resp = await client.post(
        "/api/v1/spots",
        json={"name": "Etang Nord", "latitude": 48.1, "longitude": 2.5, "water_type": "pond"},
        headers=headers,
    )
    assert resp.status_code == 201
    spot = resp.json()
    assert spot["water_type"] == "pond"
    assert spot["created_by"] is not None

    resp = await client.get(f"/api/v1/spots/{spot['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Etang Nord"


async def test_get_missing_spot_returns_404(client):
    resp = await client.get("/api/v1/spots/999999")
    assert resp.status_code == 404


async def test_list_spots_filters_by_bbox(client, register_user):
    headers = await register_user(email="geo@example.com", username="geo")

    await client.post(
        "/api/v1/spots",
        json={"name": "In", "latitude": 45, "longitude": 5, "water_type": "river"},
        headers=headers,
    )
    await client.post(
        "/api/v1/spots",
        json={"name": "Out", "latitude": 10, "longitude": 10, "water_type": "river"},
        headers=headers,
    )

    resp = await client.get(
        "/api/v1/spots", params={"min_lat": 40, "max_lat": 50, "min_lon": 0, "max_lon": 10}
    )
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "In" in names
    assert "Out" not in names


async def test_update_spot_forbidden_for_non_owner(client, register_user):
    owner_headers = await register_user(email="owner2@example.com", username="owner2")
    resp = await client.post(
        "/api/v1/spots",
        json={"name": "S", "latitude": 1, "longitude": 1, "water_type": "river"},
        headers=owner_headers,
    )
    spot_id = resp.json()["id"]

    other_headers = await register_user(email="other@example.com", username="other")
    resp = await client.patch(
        f"/api/v1/spots/{spot_id}", json={"name": "Hacked"}, headers=other_headers
    )
    assert resp.status_code == 403


async def test_update_spot_by_owner_succeeds(client, register_user):
    headers = await register_user(email="editor@example.com", username="editorspot")
    resp = await client.post(
        "/api/v1/spots",
        json={"name": "Original", "latitude": 1, "longitude": 1, "water_type": "river"},
        headers=headers,
    )
    spot_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/spots/{spot_id}", json={"name": "Renomme"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renomme"


async def test_delete_spot_by_owner(client, register_user):
    headers = await register_user(email="deleter@example.com", username="deleter")
    resp = await client.post(
        "/api/v1/spots",
        json={"name": "ToDelete", "latitude": 1, "longitude": 1, "water_type": "river"},
        headers=headers,
    )
    spot_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/spots/{spot_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/spots/{spot_id}")
    assert resp.status_code == 404
