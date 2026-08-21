async def test_me_returns_the_authenticated_user(client, register_user):
    headers = await register_user(email="me@example.com", username="meuser")
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert body["username"] == "meuser"


async def test_me_without_a_token_returns_401(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
