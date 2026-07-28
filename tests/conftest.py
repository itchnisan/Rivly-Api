import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://rivly:rivly@localhost:5432/rivly_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-0123456789")
os.environ["ENVIRONMENT"] = "test"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.models.base import Base


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    async with session_local() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)

    async def _override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def register_user(client):
    async def _register(
        email: str = "user@example.com", username: str = "user", password: str = "secret123"
    ) -> dict[str, str]:
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": password},
        )
        resp = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
