import io
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from backend.utils.audio_validator import (
    stream_and_validate_audio,
    validate_audio_metadata,
    verify_audio_signature,
)
from server.config import settings


@pytest.fixture
def mock_db():
    db = MagicMock()

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value={"role": "dm", "user_id": "123"})
    db.__getitem__.side_effect = lambda key: (
        mock_members if key == "campaign_members" else MagicMock()
    )

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    db.session_logs.find.return_value = mock_cursor
    db.campaign_entities.find.return_value = mock_cursor

    db.session_logs.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_session_id"))
    db.campaign_entities.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="mock_entity_id")
    )
    db.campaign_entities.insert_many = AsyncMock(
        return_value=MagicMock(inserted_ids=["mock_entity_id_1"])
    )
    return db


@pytest.fixture
def client(mock_db):
    from server.db_async import get_database
    from server.dependencies.auth import get_current_user
    from server.main import app

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"username": "testdm", "id": "123"}

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_database, None)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Fixture data: Valid audio byte samples
# ---------------------------------------------------------------------------
VALID_MP3_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x23" + b"\x00" * 64
VALID_MP3_MPEG_SYNC = b"\xff\xfb\x90\x64" + b"\x00" * 64  # MPEG-1 Layer 3, 128k, 44.1kHz
VALID_WAV_RIFF = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32
VALID_WAV_RIFX = b"RIFX\x00\x00\x00\x24WAVEfmt " + b"\x00" * 32
VALID_OGG = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 32
VALID_FLAC = b"fLaC\x00\x00\x00\x22" + b"\x00" * 32
VALID_FLAC_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x20fLaC" + b"\x00" * 32
VALID_M4A = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00" + b"\x00" * 32
VALID_WEBM = b"\x1a\x45\xdf\xa3\x01\x00\x00\x1f\x42\x82\x84webm" + b"\x00" * 32
VALID_AAC_ADTS = b"\xff\xf1\x50\x80" + b"\x00" * 32
VALID_AAC_ADIF = b"ADIF\x00\x00\x00\x00" + b"\x00" * 32
VALID_AAC_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x23" + b"\x00" * 32


def make_upload_file(
    content: bytes, filename: str | None = "audio.mp3", content_type: str | None = "audio/mpeg"
) -> UploadFile:
    buf = io.BytesIO(content)
    headers = {}
    if content_type is not None:
        headers["content-type"] = content_type
    return UploadFile(file=buf, filename=filename, headers=Headers(headers))


# ---------------------------------------------------------------------------
# 1. Unit Tests: validate_audio_metadata
# ---------------------------------------------------------------------------
class TestValidateAudioMetadata:
    @pytest.mark.parametrize(
        "filename,content_type,expected_ext",
        [
            ("session.mp3", "audio/mpeg", ".mp3"),
            ("SESSION.MP3", "audio/mp3", ".mp3"),
            ("session.wav", "audio/wav", ".wav"),
            ("session.wav", "audio/x-wav", ".wav"),
            ("session.m4a", "audio/mp4", ".m4a"),
            ("session.m4a", "audio/x-m4a", ".m4a"),
            ("session.ogg", "audio/ogg", ".ogg"),
            ("session.ogg", "application/ogg", ".ogg"),
            ("session.webm", "audio/webm", ".webm"),
            ("session.webm", "audio/webm; codecs=opus", ".webm"),
            ("session.flac", "audio/flac", ".flac"),
            ("session.aac", "audio/aac", ".aac"),
            ("session.aac", "audio/x-aac", ".aac"),
        ],
    )
    def test_valid_metadata(self, filename, content_type, expected_ext):
        uf = make_upload_file(b"dummy", filename=filename, content_type=content_type)
        ext = validate_audio_metadata(uf)
        assert ext == expected_ext

    @pytest.mark.parametrize("filename", [None, "", "   "])
    def test_missing_filename(self, filename):
        uf = make_upload_file(b"dummy", filename=filename, content_type="audio/mpeg")
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "Missing or empty filename" in exc_info.value.detail

    @pytest.mark.parametrize("filename", ["audio_without_extension", "recording."])
    def test_missing_extension(self, filename):
        uf = make_upload_file(b"dummy", filename=filename, content_type="audio/mpeg")
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "Invalid file extension" in exc_info.value.detail

    @pytest.mark.parametrize(
        "filename", ["malware.exe", "notes.txt", "doc.pdf", "clip.mp4", "pic.png"]
    )
    def test_invalid_extension(self, filename):
        uf = make_upload_file(b"dummy", filename=filename, content_type="audio/mpeg")
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "Invalid file extension" in exc_info.value.detail

    @pytest.mark.parametrize("content_type", [None, "", "   "])
    def test_missing_content_type(self, content_type):
        uf = make_upload_file(b"dummy", filename="session.mp3", content_type=content_type)
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "Missing Content-Type" in exc_info.value.detail

    @pytest.mark.parametrize(
        "content_type",
        ["text/plain", "application/octet-stream", "image/png", "application/x-msdownload"],
    )
    def test_invalid_content_type(self, content_type):
        uf = make_upload_file(b"dummy", filename="session.mp3", content_type=content_type)
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "Invalid content type" in exc_info.value.detail

    @pytest.mark.parametrize(
        "filename,content_type",
        [
            ("session.mp3", "audio/wav"),
            ("session.wav", "audio/mpeg"),
            ("session.ogg", "audio/mp4"),
            ("session.flac", "audio/ogg"),
        ],
    )
    def test_mismatched_extension_and_content_type(self, filename, content_type):
        uf = make_upload_file(b"dummy", filename=filename, content_type=content_type)
        with pytest.raises(HTTPException) as exc_info:
            validate_audio_metadata(uf)
        assert exc_info.value.status_code == 400
        assert "not compatible with extension" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 2. Unit Tests: verify_audio_signature
# ---------------------------------------------------------------------------
class TestVerifyAudioSignature:
    @pytest.mark.parametrize(
        "ext,header",
        [
            (".mp3", VALID_MP3_ID3),
            ("mp3", VALID_MP3_MPEG_SYNC),
            (".wav", VALID_WAV_RIFF),
            ("wav", VALID_WAV_RIFX),
            (".ogg", VALID_OGG),
            (".flac", VALID_FLAC),
            ("flac", VALID_FLAC_ID3),
            (".m4a", VALID_M4A),
            (".webm", VALID_WEBM),
            (".aac", VALID_AAC_ADTS),
            ("aac", VALID_AAC_ADIF),
            ("aac", VALID_AAC_ID3),
        ],
    )
    def test_valid_audio_signatures(self, ext, header):
        assert verify_audio_signature(header, ext) is True

    @pytest.mark.parametrize(
        "ext,disallowed_bytes",
        [
            (".mp3", b"MZ\x90\x00\x03\x00\x00\x00executable content"),
            (".wav", b"\x7fELF\x02\x01\x01\x00linux binary"),
            (".ogg", b"\xca\xfe\xba\xbejava or macho fat binary"),
            (".flac", b"#!/bin/bash\nrm -rf /"),
            (".m4a", b"%PDF-1.4\n1 0 obj<<>>"),
            (".webm", b"PK\x03\x04\x14\x00\x00\x00zip archive"),
            (".aac", b"<!DOCTYPE html><html><body>malware</body></html>"),
            (".mp3", b"<html xmlns='http://www.w3.org/1999/xhtml'>"),
            (".wav", b"<?xml version='1.0'?><evil/>"),
            (".ogg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
        ],
    )
    def test_disallowed_and_executable_signatures_rejected(self, ext, disallowed_bytes):
        assert verify_audio_signature(disallowed_bytes, ext) is False

    @pytest.mark.parametrize(
        "claimed_ext,content_from_other_format",
        [
            (".mp3", VALID_WAV_RIFF),
            (".wav", VALID_MP3_ID3),
            (".ogg", VALID_FLAC),
            (".flac", VALID_OGG),
            (".m4a", VALID_WEBM),
            (".webm", VALID_M4A),
        ],
    )
    def test_mismatched_magic_bytes_rejected(self, claimed_ext, content_from_other_format):
        assert verify_audio_signature(content_from_other_format, claimed_ext) is False

    @pytest.mark.parametrize("header", [b"", b"\x00", b"\xff", b"hello world random text"])
    def test_empty_and_garbage_headers_rejected(self, header):
        assert verify_audio_signature(header, ".mp3") is False


# ---------------------------------------------------------------------------
# 3. Unit Tests: stream_and_validate_audio
# ---------------------------------------------------------------------------
class TestStreamAndValidateAudio:
    @pytest.mark.anyio
    async def test_stream_valid_audio_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, "dest.mp3")
            content = VALID_MP3_ID3 + b"\x00" * 1024
            uf = make_upload_file(content, filename="test.mp3", content_type="audio/mpeg")

            written_bytes = await stream_and_validate_audio(uf, dest_file)
            assert written_bytes == len(content)
            assert os.path.exists(dest_file)
            with open(dest_file, "rb") as f:
                assert f.read() == content

    @pytest.mark.anyio
    async def test_stream_empty_file_raises_400_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, "dest.mp3")
            uf = make_upload_file(b"", filename="test.mp3", content_type="audio/mpeg")

            with pytest.raises(HTTPException) as exc_info:
                await stream_and_validate_audio(uf, dest_file)

            assert exc_info.value.status_code == 400
            assert "empty" in exc_info.value.detail
            assert not os.path.exists(dest_file)

    @pytest.mark.anyio
    async def test_stream_spoofed_magic_bytes_raises_400_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, "dest.mp3")
            # Disguised Windows EXE with .mp3 extension and audio/mpeg MIME
            fake_payload = b"MZ\x90\x00" + b"\x00" * 500
            uf = make_upload_file(fake_payload, filename="test.mp3", content_type="audio/mpeg")

            with pytest.raises(HTTPException) as exc_info:
                await stream_and_validate_audio(uf, dest_file)

            assert exc_info.value.status_code == 400
            assert "File signature verification failed" in exc_info.value.detail
            assert not os.path.exists(dest_file)

    @pytest.mark.anyio
    async def test_stream_size_cap_exceeded_raises_413_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, "dest.mp3")
            # 500 bytes with valid ID3 header, but set cap to 200 bytes
            content = VALID_MP3_ID3 + b"\x00" * 500
            uf = make_upload_file(content, filename="test.mp3", content_type="audio/mpeg")

            with pytest.raises(HTTPException) as exc_info:
                await stream_and_validate_audio(uf, dest_file, max_size_bytes=200, chunk_size=100)

            assert exc_info.value.status_code == 413
            assert "File size exceeds the maximum allowed limit" in exc_info.value.detail
            assert not os.path.exists(dest_file)


# ---------------------------------------------------------------------------
# 4. Integration Tests: POST /api/v1/campaigns/{name}/sessions/audio
# ---------------------------------------------------------------------------
class TestAudioSessionEndpointIntegration:
    @pytest.fixture(autouse=True)
    def setup_endpoint_deps(self, client):
        from server.dependencies.campaign import require_campaign_role
        from server.rate_limiter import limiter

        def override_dm_role():
            def _require(campaign_member: dict = None):
                return {"role": "dm"}

            return _require

        client.app.dependency_overrides[require_campaign_role] = override_dm_role()
        orig_limiter_state = limiter.enabled
        limiter.enabled = False
        yield
        limiter.enabled = orig_limiter_state
        client.app.dependency_overrides.pop(require_campaign_role, None)

    def test_post_audio_valid_mp3_success(self, client, mock_db):
        from server.routers.session_router import session_service

        original_provider = session_service.ai_provider
        mock_provider = MagicMock()
        mock_provider.client = True
        mock_provider.upload_file.return_value = "gemini_file_123"
        mock_provider.generate_json_from_files.return_value = {
            "title": "Valid Audio Session",
            "summary": "Audio processed successfully.",
            "extracted_entities": [
                {"name": "Eldrin", "type": "npc", "content": "Elf wizard", "tags": []}
            ],
        }
        session_service.ai_provider = mock_provider

        try:
            resp = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 1},
                files={"audio_file": ("session.mp3", VALID_MP3_ID3, "audio/mpeg")},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["title"] == "Valid Audio Session"
            assert len(body["extracted_entities"]) == 1
            assert body["extracted_entities"][0]["name"] == "Eldrin"
        finally:
            session_service.ai_provider = original_provider

    def test_post_audio_valid_wav_success(self, client, mock_db):
        from server.routers.session_router import session_service

        original_provider = session_service.ai_provider
        mock_provider = MagicMock()
        mock_provider.client = True
        mock_provider.upload_file.return_value = "gemini_file_wav"
        mock_provider.generate_json_from_files.return_value = {
            "title": "WAV Audio Session",
            "summary": "WAV processed.",
            "extracted_entities": [],
        }
        session_service.ai_provider = mock_provider

        try:
            resp = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 2},
                files={"audio_file": ("session.wav", VALID_WAV_RIFF, "audio/wav")},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["title"] == "WAV Audio Session"
        finally:
            session_service.ai_provider = original_provider

    def test_post_audio_invalid_extension_rejected_400(self, client):
        resp = client.post(
            "/api/v1/campaigns/TestCamp/sessions/audio",
            data={"session_number": 1},
            files={"audio_file": ("session.txt", b"some text", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Invalid file extension '.txt'" in resp.json()["detail"]

    def test_post_audio_invalid_mime_type_rejected_400(self, client):
        resp = client.post(
            "/api/v1/campaigns/TestCamp/sessions/audio",
            data={"session_number": 1},
            files={"audio_file": ("session.mp3", VALID_MP3_ID3, "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Invalid content type 'application/octet-stream'" in resp.json()["detail"]

    def test_post_audio_mismatched_mime_type_rejected_400(self, client):
        resp = client.post(
            "/api/v1/campaigns/TestCamp/sessions/audio",
            data={"session_number": 1},
            files={"audio_file": ("session.mp3", VALID_MP3_ID3, "audio/wav")},
        )
        assert resp.status_code == 400
        assert "not compatible with extension '.mp3'" in resp.json()["detail"]

    def test_post_audio_spoofed_magic_bytes_rejected_400(self, client, mock_db):
        from server.routers.session_router import session_service

        original_provider = session_service.ai_provider
        mock_provider = MagicMock()
        mock_provider.client = True
        session_service.ai_provider = mock_provider

        try:
            # Upload Windows PE executable disguised as MP3
            fake_payload = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
            resp = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 1},
                files={"audio_file": ("session.mp3", fake_payload, "audio/mpeg")},
            )
            assert resp.status_code == 400
            assert "File signature verification failed" in resp.json()["detail"]
        finally:
            session_service.ai_provider = original_provider

    def test_post_audio_empty_file_rejected_400(self, client, mock_db):
        from server.routers.session_router import session_service

        original_provider = session_service.ai_provider
        mock_provider = MagicMock()
        mock_provider.client = True
        session_service.ai_provider = mock_provider

        try:
            resp = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 1},
                files={"audio_file": ("empty.mp3", b"", "audio/mpeg")},
            )
            assert resp.status_code == 400
            assert "Uploaded audio file is empty" in resp.json()["detail"]
        finally:
            session_service.ai_provider = original_provider

    def test_post_audio_content_length_exceeded_rejected_413(self, client):
        # When Content-Length header claims > 100MB
        oversized = settings.MAX_AUDIO_FILE_SIZE_BYTES + 1
        resp = client.post(
            "/api/v1/campaigns/TestCamp/sessions/audio",
            data={"session_number": 1},
            files={"audio_file": ("session.mp3", VALID_MP3_ID3, "audio/mpeg")},
            headers={"Content-Length": str(oversized)},
        )
        assert resp.status_code == 413
        assert "File size exceeds the maximum allowed limit of 100MB." in resp.json()["detail"]

    def test_post_audio_streaming_size_cap_exceeded_rejected_413(self, client, monkeypatch):
        from server.routers.session_router import session_service

        original_provider = session_service.ai_provider
        mock_provider = MagicMock()
        mock_provider.client = True
        session_service.ai_provider = mock_provider

        # Temporarily set max audio size to 100 bytes to test streaming limit without generating 100MB
        monkeypatch.setattr(settings, "MAX_AUDIO_FILE_SIZE_BYTES", 100)

        try:
            oversized_payload = VALID_MP3_ID3 + b"\x00" * 200
            resp = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 1},
                files={"audio_file": ("session.mp3", oversized_payload, "audio/mpeg")},
            )
            assert resp.status_code == 413
            assert "File size exceeds the maximum allowed limit" in resp.json()["detail"]
        finally:
            session_service.ai_provider = original_provider
