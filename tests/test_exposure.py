from shapely.geometry import box, mapping

from floodbeacon.exposure import exposure_layers


def collection(geometries):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(g), "properties": {"reported_damage": "unknown"}}
        for g in geometries
    ]}


def test_missing_coverage_never_becomes_passable():
    assets = collection([box(7.01, 50.01, 7.02, 50.02)])
    outputs = exposure_layers(assets, collection([]), collection([]), "EPSG:32632")
    props = outputs["exposure"]["features"][0]["properties"]
    assert props["flood_exposure"] == "unknown"
    assert props["route_passability"] == "unknown"
    assert props["reported_damage"] == "unknown"


def test_exposure_is_not_damage_and_scenario_has_no_forecast_time():
    flood = collection([box(7.0, 50.0, 7.001, 50.001)])
    assets = collection([box(7.0002, 50.0002, 7.0003, 50.0003), box(7.0011, 50.0, 7.0012, 50.0001)])
    outputs = exposure_layers(assets, flood, collection([box(6.9,49.9,7.1,50.1)]), "EPSG:32632")
    assert outputs["exposure"]["features"][0]["properties"]["flood_exposure"] == "candidate"
    assert outputs["exposure"]["features"][0]["properties"]["reported_damage"] == "unknown"
    scenario = outputs["scenario_50m"]["features"][0]["properties"]
    assert scenario["forecast_horizon_hours"] is None
    assert scenario["evidence_type"] == "scenario_risk"


def test_agency_date_is_separate_from_exposure_and_scenario_basis():
    assets = collection([box(7.0011, 50.0, 7.0012, 50.0001)])
    assets["features"][0]["properties"]["observed_at"] = "2021-07-18T10:50:00Z"
    outputs = exposure_layers(
        assets, collection([box(7.0, 50.0, 7.001, 50.001)]),
        collection([box(6.9, 49.9, 7.1, 50.1)]), "EPSG:32632",
        exposure_observed_at="2021-07-15T05:50:52Z",
    )
    props = outputs["exposure"]["features"][0]["properties"]
    assert props["observed_at"] == "2021-07-18T10:50:00Z"
    assert props["exposure_observed_at"] == "2021-07-15T05:50:52Z"
    assert outputs["scenario_50m"]["features"][0]["properties"]["scenario_basis_observed_at"] == props["exposure_observed_at"]
