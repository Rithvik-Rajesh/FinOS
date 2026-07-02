"""Smoke tests for the app boot + system endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health() -> None:
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready() -> None:
    resp = client.get("/v1/ready")
    assert resp.status_code == 200


def test_root() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "finos"


def test_me_with_dev_bypass() -> None:
    # auth_dev_bypass defaults on outside prod, so /me resolves the dev user.
    resp = client.get("/v1/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_dev"] is True
    assert body["base_currency"] == "INR"


def test_error_envelope_shape_on_unknown_route() -> None:
    resp = client.get("/v1/does-not-exist")
    assert resp.status_code == 404
