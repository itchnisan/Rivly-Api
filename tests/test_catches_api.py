from app.models.species import Species


async def _setup_spot_and_species(client, db_session, headers, spot_name: str = "Spot") -> tuple[int, int]:
    resp = await client.post(
        "/api/v1/spots",
        json={"name": spot_name, "latitude": 1, "longitude": 1, "water_type": "river"},
        headers=headers,
    )
    spot_id = resp.json()["id"]

    species = Species(name="Esox lucius", common_name="Brochet")
    db_session.add(species)
    await db_session.commit()

    return spot_id, species.id


async def test_create_catch_requires_auth(client):
    resp = await client.post(
        "/api/v1/catches",
        json={"spot_id": 1, "species_id": 1, "caught_at": "2026-01-01T10:00:00Z"},
    )
    assert resp.status_code == 401


async def test_create_and_list_own_catch(client, db_session, register_user):
    headers = await register_user(email="angler@example.com", username="angler")
    spot_id, species_id = await _setup_spot_and_species(client, db_session, headers)

    resp = await client.post(
        "/api/v1/catches",
        json={
            "spot_id": spot_id,
            "species_id": species_id,
            "weight_g": 1200,
            "length_cm": 45.5,
            "caught_at": "2026-06-01T08:30:00Z",
            "conditions": {"weather": "sunny", "water_temp_c": 19, "moon_phase": "full"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    catch = resp.json()
    assert catch["conditions"]["weather"] == "sunny"

    resp = await client.get("/api/v1/catches", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_catches_are_scoped_to_user(client, db_session, register_user):
    headers_a = await register_user(email="a2@example.com", username="a2")
    spot_id, species_id = await _setup_spot_and_species(client, db_session, headers_a)

    await client.post(
        "/api/v1/catches",
        json={"spot_id": spot_id, "species_id": species_id, "caught_at": "2026-06-01T08:30:00Z"},
        headers=headers_a,
    )

    headers_b = await register_user(email="b2@example.com", username="b2")
    resp = await client.get("/api/v1/catches", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_update_and_delete_catch(client, db_session, register_user):
    headers = await register_user(email="editor2@example.com", username="editorcatch")
    spot_id, species_id = await _setup_spot_and_species(client, db_session, headers)

    resp = await client.post(
        "/api/v1/catches",
        json={"spot_id": spot_id, "species_id": species_id, "caught_at": "2026-06-01T08:30:00Z"},
        headers=headers,
    )
    catch_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/catches/{catch_id}", json={"notes": "belle prise"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "belle prise"

    resp = await client.delete(f"/api/v1/catches/{catch_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/catches/{catch_id}", headers=headers)
    assert resp.status_code == 404
