import importlib

import psycopg
import pytest
from fastapi.testclient import TestClient

from floodbeacon import api


client = TestClient(api.app)
RUN = {"id": "v1", "case_id": "ahr", "generated_at": "2026-10-03T12:00:00+00:00",
       "metadata": {"mode": "retrospective", "limitations": ["Exposure is not destruction"]}}


def feature(identifier, coordinates):
    return {"type": "Feature", "id": identifier,
            "properties": {"reported_damage": "unknown", "exposure": "inundated"},
            "geometry": {"type": "LineString", "coordinates": coordinates}}


def test_layers_bbox_pagination_preserve_evidence_and_run(monkeypatch):
    data = {"type": "FeatureCollection", "run_id": "v1", "case_id": "ahr",
            "generated_at": RUN["generated_at"], "features": [
                feature("crossing", [[6, 50], [8, 50]]),
                feature("nearby", [[7, 50], [7.1, 50.1]]),
                feature("distant", [[9, 51], [10, 52]])]}
    monkeypatch.setattr(api.db, "get_layer", lambda *args: data)
    response = client.get("/cases/ahr/layers/exposure?bbox=6.9,49.9,7.2,50.2&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "v1"
    assert body["features"][0]["id"] == "crossing"  # crosses bbox; no vertex inside it
    assert body["features"][0]["properties"]["reported_damage"] == "unknown"
    assert body["pagination"]["total"] == 2
    assert body["pagination"]["next_offset"] == 1
    assert len(data["features"]) == 3
    second = client.get("/cases/ahr/layers/exposure?bbox=6.9,49.9,7.2,50.2&limit=1&offset=1").json()
    assert second["features"][0]["id"] == "nearby"
    assert second["pagination"]["next_offset"] is None


@pytest.mark.parametrize("query", ["bbox=nan,0,1,1", "bbox=0,0,181,1", "bbox=2,0,1,1",
                                  "bbox=0,1,2", "limit=0", "limit=10001", "offset=-1"])
def test_invalid_spatial_query_does_not_read_storage(monkeypatch, query):
    def unexpected(*args):
        pytest.fail("Invalid queries should not read storage")
    monkeypatch.setattr(api.db, "get_layer", unexpected)
    assert client.get(f"/cases/ahr/layers/exposure?{query}").status_code == 422


def test_unknown_layer_is_404(monkeypatch):
    monkeypatch.setattr(api.db, "get_layer", lambda *args: None)
    assert client.get("/cases/missing/layers/exposure").status_code == 404


def test_database_failure_does_not_expose_connection_details(monkeypatch):
    def unavailable():
        raise psycopg.OperationalError("password=secret host=private")
    monkeypatch.setattr(api.db, "list_cases", unavailable)
    response = client.get("/cases")
    assert response.status_code == 503
    assert "secret" not in response.text and "private" not in response.text


def test_observations_pin_selected_run_and_keep_quality_times(monkeypatch):
    monkeypatch.setattr(api.db, "get_run", lambda *args: RUN)
    def observations(case_id, run_id):
        assert (case_id, run_id) == ("ahr", "v1")
        return [{"observed_at": "2021-07-14T00:00:00Z", "available_at": None,
                 "value": 239, "unit": "m3/s", "quality": "Estimated"}]
    monkeypatch.setattr(api.db, "get_observations", observations)
    response = client.get("/cases/ahr/observations")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "v1"
    assert body["observations"][0]["available_at"] is None
    assert body["observations"][0]["quality"] == "Estimated"


def test_run_and_case_not_found(monkeypatch):
    monkeypatch.setattr(api.db, "get_run", lambda *args: None)
    monkeypatch.setattr(api.db, "list_runs", lambda *args: [])
    monkeypatch.setattr(api.db, "list_cases", lambda: [])
    assert client.get("/cases/missing/runs").status_code == 404
    assert client.get("/cases/ahr/runs/missing").status_code == 404
    assert client.get("/cases/ahr/observations").status_code == 404


@pytest.mark.parametrize("origins,origin,allowed", [
    (None, "http://localhost:5173", "*"),
    ("http://localhost:3000, http://localhost:5173", "http://localhost:5173", "http://localhost:5173"),
    ("http://localhost:3000", "http://localhost:5173", None),
])
def test_frontend_cors_get_and_preflight(monkeypatch, origins, origin, allowed):
    try:
        with monkeypatch.context() as settings:
            if origins is None:
                settings.delenv("CORS_ORIGINS", raising=False)
            else:
                settings.setenv("CORS_ORIGINS", origins)
            configured = importlib.reload(api)
            settings.setattr(configured.db, "list_cases", lambda: [])
            with TestClient(configured.app) as browser:
                response = browser.get("/cases", headers={"Origin": origin})
                assert response.status_code == 200
                assert response.headers.get("access-control-allow-origin") == allowed
                assert "access-control-allow-credentials" not in response.headers
                preflight = browser.options("/cases", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Content-Type",
                })
                assert preflight.status_code == (200 if allowed else 400)
                assert preflight.headers.get("access-control-allow-origin") == allowed
    finally:
        importlib.reload(api)
