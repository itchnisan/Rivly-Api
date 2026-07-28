from app.models.species import Species


async def test_list_species_empty_by_default(client):
    resp = await client.get("/api/v1/species")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_and_get_species(client, db_session):
    species = Species(name="Esox lucius", common_name="Brochet", legal_size_cm=60)
    db_session.add(species)
    await db_session.commit()

    resp = await client.get("/api/v1/species")
    assert resp.status_code == 200
    assert any(s["common_name"] == "Brochet" for s in resp.json())

    resp = await client.get(f"/api/v1/species/{species.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Esox lucius"


async def test_get_missing_species_returns_404(client):
    resp = await client.get("/api/v1/species/999999")
    assert resp.status_code == 404
