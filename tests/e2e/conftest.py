"""Shared fixtures and setup for Phyrexian Forge E2E test suites."""

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.services.class_resources_service import _load_rules
from server.db_async import get_database
from server.main import app
from server.rate_limiter import limiter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLIENT_ROOT = PROJECT_ROOT / "client"
CLIENT_APP_ROOT = CLIENT_ROOT / "src" / "app"


class _AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def __iter__(self):
        return iter(self._cursor)

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Any]:
        docs = list(self._cursor)
        if length is not None:
            docs = docs[:length]
        return docs


class _AsyncColWrapper:
    def __init__(self, col):
        self._col = col

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self._col.insert_many(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> _AsyncColWrapper:
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name: str) -> _AsyncColWrapper:
        return _AsyncColWrapper(getattr(self._db, name))


@pytest.fixture
def mock_db() -> _AsyncDBWrapper:
    """Provides an isolated in-memory Mongo database mock."""
    mongo = mongomock.MongoClient()
    return _AsyncDBWrapper(mongo["phyrexian_forge_e2e"])


@pytest.fixture
def e2e_client(mock_db: _AsyncDBWrapper) -> Generator[TestClient, None, None]:
    """Provides a TestClient connected to the isolated in-memory DB."""
    limiter.reset()
    _load_rules.cache_clear()
    app.dependency_overrides[get_database] = lambda: mock_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_database, None)
    limiter.reset()


class E2EAuthHelper:
    """Helper to register and login users for E2E testing."""

    def __init__(self, client: TestClient):
        self.client = client

    def register_and_login(
        self, username: str, email: str, role: str = "player", is_admin: bool = False
    ) -> Dict[str, str]:
        limiter.reset()
        res = self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": "Password123!"},
        )
        assert res.status_code in (200, 201), f"Register failed: {res.text}"

        login_res = self.client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": "Password123!"},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_helper(e2e_client: TestClient) -> E2EAuthHelper:
    return E2EAuthHelper(e2e_client)
