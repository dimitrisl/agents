from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.utils.pdf_importer import PDFPageLimitExceededError
from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.rate_limiter import limiter
from server.routers.character_router import router


@pytest.fixture
def mock_db():
    db = MagicMock()
    db["characters"] = MagicMock()
    db["characters"].insert_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].update_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].replace_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].find_one = AsyncMock(return_value=None)
    db["campaigns"] = MagicMock()
    db["campaigns"].find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def test_client(mock_db):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_test_123",
        "username": "tester",
        "is_admin": False,
    }

    client = TestClient(app)
    return client


def test_import_pdf_rejects_non_pdf_extension(test_client):
    res = test_client.post(
        "/characters/import-pdf",
        files={"file": ("test.txt", b"plain text", "text/plain")},
    )
    assert res.status_code == 400
    assert "must be a PDF" in res.json()["detail"]


def test_import_pdf_rejects_missing_magic_bytes(test_client):
    res = test_client.post(
        "/characters/import-pdf",
        files={"file": ("fake.pdf", b"NOT_A_PDF_CONTENT_HERE", "application/pdf")},
    )
    assert res.status_code == 400
    assert "magic bytes" in res.json()["detail"]


def test_import_pdf_rejects_oversized_file(test_client):
    # Over 10MB chunked read
    large_pdf = b"%PDF-" + b"0" * (settings.MAX_PDF_IMPORT_BYTES + 1024)
    res = test_client.post(
        "/characters/import-pdf",
        files={"file": ("oversized.pdf", large_pdf, "application/pdf")},
    )
    assert res.status_code == 413
    assert "exceeds maximum limit" in res.json()["detail"]


@patch(
    "server.routers.character_router.extract_text_and_fields_from_pdf",
    side_effect=PDFPageLimitExceededError(
        "PDF exceeds maximum allowed page count of 10 pages (has 25)."
    ),
)
def test_import_pdf_rejects_too_many_pages(mock_extract, test_client):
    valid_header_pdf = b"%PDF-1.4\n" + b"dummy body"
    res = test_client.post(
        "/characters/import-pdf",
        files={"file": ("long.pdf", valid_header_pdf, "application/pdf")},
    )
    assert res.status_code == 422
    assert "PDF exceeds maximum allowed page count" in res.json()["detail"]


@patch(
    "server.routers.character_router.extract_text_and_fields_from_pdf",
    return_value="--- FORM FIELDS ---\nCharacterName: John Doe\nClassLevel: Fighter 1\n",
)
@patch(
    "server.routers.character_router.parse_character_from_text",
    return_value={
        "char_name": "John Doe",
        "char_class": "Fighter",
        "char_level": 1,
        "classes": [{"class_name": "Fighter", "level": 1, "subclass": None}],
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "hp_max": 12,
        "hp_current": 12,
        "armor_class": 16,
    },
)
def test_import_pdf_success_generates_fresh_char_id(mock_parse, mock_extract, test_client):
    valid_pdf = b"%PDF-1.4\n" + b"dummy body"
    res = test_client.post(
        "/characters/import-pdf",
        files={"file": ("valid.pdf", valid_pdf, "application/pdf")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["char_name"] == "John Doe"
    assert data["char_class"] == "Fighter"
    assert data["owner_id"] == "user_test_123"
    assert data["char_id"] is not None
    assert "warnings" in data
    assert isinstance(data["warnings"], list)
