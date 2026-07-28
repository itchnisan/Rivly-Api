async def test_register_creates_user(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "username": "newuser", "password": "secret123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["username"] == "newuser"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "username": "dup1", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=payload)

    resp = await client.post("/api/v1/auth/register", json={**payload, "username": "dup2"})
    assert resp.status_code == 400


async def test_login_success_returns_bearer_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "username": "a", "password": "secret123"},
    )

    resp = await client.post(
        "/api/v1/auth/login", data={"username": "a@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password_rejected(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "username": "b", "password": "secret123"},
    )

    resp = await client.post(
        "/api/v1/auth/login", data={"username": "b@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_rejected(client):
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "nobody@example.com", "password": "whatever"}
    )
    assert resp.status_code == 401
