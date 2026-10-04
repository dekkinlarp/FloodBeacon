"""Frontend contract checks using synthetic records, without PostgreSQL writes."""

from copy import deepcopy

from fastapi.testclient import TestClient
import psycopg
import pytest

from floodbeacon import api


BOUNDS = [7.03, 50.51, 7.04, 50.52]
GENERATED_AT = "2026-10-04T12:00:00+00:00"


def catalog():
    feature = {
        "type": "Feature", "id": "rech-before", "geometry": {
            "type": "Polygon", "coordinates": [[[7.035, 50.513], [7.037, 50.513],
                [7.037, 50.515], [7.035, 50.515], [7.035, 50.513]]]},
        "properties": {"bridge_id": "rech-nepomuk", "name": "Nepomukbrücke",
            "observation_id": "before", "observed_date": "2021-02-11",
            "finding": "Complete crossing visible", "status": "visible_crossing",
            "assessment_method": "manual image review", "failure_time": None,
            "annotation": "Review square; not a surveyed damage boundary"},
    }
    image = {
        "id": "before", "url": "/static/imagery/rech-satellite/before.png",
        "bounds": BOUNDS, "image_coordinates": [[7.03, 50.52], [7.04, 50.52],
            [7.04, 50.51], [7.03, 50.51]],
        "width": 542, "height": 852, "sha256": "a" * 64, "bytes": 764912,
        "attribution": "Maxar; SpaceNet Partners", "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "provenance": {"source_crs": "EPSG:4326", "date_precision": "day",
            "availability_time": None, "fixture": "synthetic"},
    }
    before = {"id": "before", "acquired_date": "2021-02-11", "acquired_at": None,
        "label": "Before flood", "images": [image],
        "bridges": {"type": "FeatureCollection", "features": [feature]}}
    after = deepcopy(before)
    after.update(id="after", acquired_date="2021-07-18", label="After flood")
    after["images"][0].update(id="after", url="/static/imagery/rech-satellite/after.png")
    after["bridges"]["features"][0].update(id="rech-after")
    after["bridges"]["features"][0]["properties"].update(
        observation_id="after", observed_date="2021-07-18", status="missing_span",
        finding="Northern remnant visible; span missing")
    return {"case_id": "ahr-2021", "name": "Rech, Ahr Valley", "country": "Germany",
        "bounds": BOUNDS, "run_id": "imagery-v1", "generated_at": GENERATED_AT,
        "limitations": ["Observation date does not establish exact failure time"],
        "bridges": [{"id": "rech-nepomuk", "name": "Nepomukbrücke",
            "coordinate": [7.03622715, 50.5141039], "failure_time": None,
            "comparison_url": "/static/imagery/rech-satellite/comparison.png",
            "before_url": image["url"], "after_url": after["images"][0]["url"],
            "agency_evidence": {"source": "Copernicus EMSR517", "grade": "Destroyed",
                "observed_at": "2021-07-18T10:50:00Z"},
            "limitations": ["Manual image review"]}],
        "observations": [before, after]}


def test_catalog_preserves_dates_provenance_separate_evidence_and_static_urls(monkeypatch):
    calls = []
    def read(case_id, run_id):
        calls.append((case_id, run_id))
        return catalog()
    monkeypatch.setattr(api.db, "get_imagery", read)
    with TestClient(api.app) as browser:
        response = browser.get("/cases/ahr-2021/imagery", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        body = response.json()
        assert calls == [("ahr-2021", None)]
        assert body["observations"][0]["acquired_at"] is None
        assert body["observations"][0]["images"][0]["provenance"]["availability_time"] is None
        assert body["bridges"][0]["failure_time"] is None
        assert body["bridges"][0]["agency_evidence"]["grade"] == "Destroyed"
        finding = body["observations"][1]["bridges"]["features"][0]["properties"]
        assert finding["status"] == "missing_span"
        assert finding["observed_date"] == "2021-07-18"
        assert finding["assessment_method"] == "manual image review"
        for observation in body["observations"]:
            assert browser.get(observation["images"][0]["url"]).status_code == 200


def test_dated_bridges_pin_explicit_run_and_do_not_mix_dates(monkeypatch):
    calls = []
    def read(case_id, run_id):
        calls.append((case_id, run_id))
        return catalog()
    monkeypatch.setattr(api.db, "get_imagery", read)
    with TestClient(api.app) as browser:
        response = browser.get("/cases/ahr-2021/imagery/before/bridges?run_id=imagery-v1")
    assert response.status_code == 200
    body = response.json()
    assert calls == [("ahr-2021", "imagery-v1")]
    assert body["run_id"] == "imagery-v1"
    assert body["observation_id"] == "before"
    assert body["acquired_date"] == "2021-02-11"
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["status"] == "visible_crossing"


@pytest.mark.parametrize("path", [
    "/cases/missing/imagery", "/cases/ahr-2021/imagery?run_id=not-imagery",
    "/cases/ahr-2021/imagery/after/bridges?run_id=missing",
])
def test_missing_imagery_publication_is_404(monkeypatch, path):
    monkeypatch.setattr(api.db, "get_imagery", lambda *args: None)
    with TestClient(api.app) as browser:
        assert browser.get(path).status_code == 404


def test_missing_observation_is_404(monkeypatch):
    monkeypatch.setattr(api.db, "get_imagery", lambda *args: catalog())
    with TestClient(api.app) as browser:
        assert browser.get("/cases/ahr-2021/imagery/unknown/bridges").status_code == 404


def test_imagery_database_failure_is_sanitized(monkeypatch):
    def unavailable(*args):
        raise psycopg.OperationalError("host=private password=secret")
    monkeypatch.setattr(api.db, "get_imagery", unavailable)
    with TestClient(api.app) as browser:
        response = browser.get("/cases/ahr-2021/imagery")
    assert response.status_code == 503
    assert "secret" not in response.text and "private" not in response.text


def test_missing_database_configuration_returns_503_and_static_files_still_work(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(api.app) as browser:
        assert browser.get("/cases/ahr-2021/imagery").status_code == 503
        assert browser.get("/static/imagery/rech-satellite/before.png").status_code == 200


def test_imagery_contract_is_documented_in_openapi():
    with TestClient(api.app) as browser:
        schema = browser.get("/openapi.json").json()
    assert schema["paths"]["/cases/{case_id}/imagery"]["get"]["responses"]["200"]
    assert "image_coordinates" in schema["components"]["schemas"]["SatelliteImage"]["properties"]
    assert schema["components"]["schemas"]["BridgeFinding"]["properties"]["failure_time"]["type"] == "null"
