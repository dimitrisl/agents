"""Verification tests for #267: Health probe, PWA config/icons, and Docker/Nginx stack."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.db_async import get_database
from server.main import app
from server.rate_limiter import limiter

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_ROOT = REPO_ROOT / "client"


@pytest.fixture(autouse=True)
def _reset_limiter_and_overrides():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    app.dependency_overrides.clear()


def test_health_endpoint_returns_healthy_when_mongo_ping_succeeds():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1.0})
    app.dependency_overrides[get_database] = lambda: mock_db

    with TestClient(app) as client:
        resp = client.get(f"{settings.API_V1_STR}/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "healthy",
        "database": "ok",
        "version": settings.VERSION,
    }
    mock_db.command.assert_awaited_once_with("ping")


def test_health_endpoint_returns_503_without_leaking_connection_details():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(
        side_effect=RuntimeError("mongodb://dbadmin:supersecret@10.0.0.5:27017 timeout")
    )
    app.dependency_overrides[get_database] = lambda: mock_db

    with TestClient(app) as client:
        resp = client.get(f"{settings.API_V1_STR}/health")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "unhealthy",
        "database": "unreachable",
        "version": settings.VERSION,
    }
    body_text = resp.text
    assert "supersecret" not in body_text
    assert "mongodb://" not in body_text
    assert "10.0.0.5" not in body_text


def test_health_endpoint_is_exempt_from_global_rate_limit():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1.0})
    app.dependency_overrides[get_database] = lambda: mock_db

    with TestClient(app) as client:
        # Exceed GLOBAL_RATE_LIMIT (100/minute) with container health probes
        for attempt in range(110):
            resp = client.get(
                f"{settings.API_V1_STR}/health",
                headers={"X-Forwarded-For": "10.99.0.10"},
            )
            assert resp.status_code == 200, (
                f"Probe {attempt + 1} was blocked with {resp.status_code}"
            )


def test_pwa_manifest_and_png_icons_exist_on_disk():
    manifest_path = CLIENT_ROOT / "public" / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["background_color"] == "#09090c"
    assert manifest["theme_color"] == "#09090c"

    seen_variants = set()
    for icon in manifest["icons"]:
        rel_src = icon["src"].lstrip("/")
        icon_file = CLIENT_ROOT / "public" / rel_src
        assert icon_file.is_file(), f"Missing manifest icon: {icon_file}"
        header = icon_file.read_bytes()[:8]
        assert header == b"\x89PNG\r\n\x1a\n", f"{icon_file} is not a valid PNG"
        seen_variants.add((icon["sizes"], icon["purpose"]))

    assert ("192x192", "any") in seen_variants
    assert ("512x512", "any") in seen_variants
    assert ("192x192", "maskable") in seen_variants
    assert ("512x512", "maskable") in seen_variants


def test_ngsw_config_caches_rules_without_caching_sensitive_or_user_apis():
    ngsw_path = CLIENT_ROOT / "ngsw-config.json"
    config = json.loads(ngsw_path.read_text(encoding="utf-8"))

    asset_group_names = {grp["name"] for grp in config.get("assetGroups", [])}
    assert {"app", "assets"}.issubset(asset_group_names)

    data_groups = {grp["name"]: grp for grp in config.get("dataGroups", [])}
    assert "rules-api" in data_groups
    assert data_groups["rules-api"]["cacheConfig"]["strategy"] == "freshness"
    assert "/api/v1/rules/**" in data_groups["rules-api"]["urls"]

    all_cached_urls = [url for grp in data_groups.values() for url in grp.get("urls", [])]
    for url in all_cached_urls:
        assert "/auth" not in url
        assert "/admin" not in url
        assert "/ws" not in url
        # Authenticated character vaults are cached owner-scoped in CharacterStateService, not shared SW HTTP cache
        assert "/characters" not in url

    angular_json = json.loads((CLIENT_ROOT / "angular.json").read_text(encoding="utf-8"))
    prod_cfg = angular_json["projects"]["client"]["architect"]["build"]["configurations"][
        "production"
    ]
    assert prod_cfg["serviceWorker"] == "ngsw-config.json"

    app_config = (CLIENT_ROOT / "src" / "app" / "app.config.ts").read_text(encoding="utf-8")
    assert "provideServiceWorker('ngsw-worker.js'" in app_config


def test_docker_and_nginx_production_configuration_invariants():
    dockerfile_backend = (REPO_ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
    assert "FROM python:3.13-slim" in dockerfile_backend
    assert "USER appuser" in dockerfile_backend
    assert "chown -R appuser:appuser /app" in dockerfile_backend
    assert "/api/v1/health" in dockerfile_backend
    assert "--proxy-headers" in dockerfile_backend

    dockerfile_frontend = (REPO_ROOT / "Dockerfile.frontend").read_text(encoding="utf-8")
    assert "FROM nginx:1.27-alpine" in dockerfile_frontend
    assert "client/nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile_frontend
    assert "dist/client/browser /usr/share/nginx/html" in dockerfile_frontend

    nginx_conf = (CLIENT_ROOT / "nginx.conf").read_text(encoding="utf-8")
    assert "location ^~ /api/" in nginx_conf
    assert "location ^~ /ws/" in nginx_conf
    assert "proxy_set_header Upgrade $http_upgrade;" in nginx_conf
    assert 'proxy_set_header Connection "upgrade";' in nginx_conf
    assert "proxy_set_header Host $http_host;" in nginx_conf
    assert "client_max_body_size 105M;" in nginx_conf
    assert "try_files $uri $uri/ /index.html;" in nginx_conf
    assert "ngsw-worker" in nginx_conf
    assert "ngsw" in nginx_conf

    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: mongo:7" in compose
    assert "portraits_data:/app/data/portraits" in compose
    assert "uploads_data:/app/data/uploads" in compose
    assert "module_pics_data:/app/data/module_pics" in compose
    assert "campaign_assets" not in compose
