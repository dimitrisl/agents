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

    client = TestClient(app)
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

    client = TestClient(app)
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

    client = TestClient(app)
    # Exceed GLOBAL_RATE_LIMIT (100/minute) with container health probes
    for attempt in range(110):
        resp = client.get(
            f"{settings.API_V1_STR}/health",
            headers={"X-Forwarded-For": "10.99.0.10"},
        )
        assert resp.status_code == 200, f"Probe {attempt + 1} was blocked with {resp.status_code}"


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

    nav_urls = config.get("navigationUrls", [])
    assert "!/api/**" in nav_urls
    assert "!/ws/**" in nav_urls

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
    assert "COPY data/rules ./data/rules" in dockerfile_backend
    assert "COPY data/pdf_mappings ./data/pdf_mappings" in dockerfile_backend
    assert "/api/v1/health" in dockerfile_backend
    assert "--proxy-headers" in dockerfile_backend
    assert "--forwarded-allow-ips=*" not in dockerfile_backend
    assert "192.168.0.0/16" not in dockerfile_backend
    assert "10.0.0.0/8" not in dockerfile_backend

    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "data/pdf_mappings" not in dockerignore

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
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in nginx_conf
    active_nginx = "\n".join(
        line for line in nginx_conf.splitlines() if not line.lstrip().startswith("#")
    )
    assert "$proxy_add_x_forwarded_for" not in active_nginx
    assert "client_max_body_size 105M;" in nginx_conf
    assert "try_files $uri $uri/ /index.html;" in nginx_conf
    assert "ngsw-worker" in nginx_conf
    assert "ngsw" in nginx_conf
    assert nginx_conf.count('add_header X-Content-Type-Options "nosniff" always;') >= 3

    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: mongo:7" in compose
    assert "portraits_data:/app/data/portraits" in compose
    assert "uploads_data:/app/data/uploads" in compose
    assert "module_pics_data:/app/data/module_pics" in compose
    assert '"127.0.0.1:${BACKEND_PORT:-8000}:8000"' in compose
    assert "192.168.0.0/16" not in compose
    assert "10.0.0.0/8" not in compose
    assert "campaign_assets" not in compose

    manifest = json.loads(
        (CLIENT_ROOT / "public" / "manifest.webmanifest").read_text(encoding="utf-8")
    )
    assert manifest["orientation"] == "any"


@pytest.mark.anyio
async def test_proxy_headers_does_not_trust_lan_clients_for_xff_spoofing(monkeypatch):
    from fastapi import FastAPI, Request
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    from server.config import settings
    from server.rate_limiter import get_real_ip

    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "127.0.0.1,::1,172.16.0.0/12")

    probe_app = FastAPI()

    @probe_app.get("/whoami")
    def _whoami(request: Request):
        return {
            "real_ip": get_real_ip(request),
            "client": request.client.host if request.client else None,
        }

    asgi = ProxyHeadersMiddleware(probe_app, trusted_hosts="127.0.0.1,::1,172.16.0.0/12")
    captured = {}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.body":
            captured["body"] = json.loads(message["body"].decode("utf-8"))

    # Simulate Docker Nginx (172.18.0.3) forwarding a LAN client (192.168.1.50) who forged an XFF header
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/whoami",
        "raw_path": b"/whoami",
        "query_string": b"",
        "headers": [
            (b"host", b"backend:8000"),
            (b"x-forwarded-for", b"198.51.100.77, 192.168.1.50"),
            (b"x-real-ip", b"192.168.1.50"),
        ],
        "client": ("172.18.0.3", 54321),
        "server": ("172.18.0.4", 8000),
    }
    await asgi(scope, receive, send)
    assert captured["body"]["client"] == "192.168.1.50"
    assert captured["body"]["real_ip"] == "192.168.1.50"
