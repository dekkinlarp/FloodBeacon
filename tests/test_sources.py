from __future__ import annotations

import io
import zipfile

import pytest
import shapefile
from pyproj import CRS

from floodbeacon.cases import CASES
from floodbeacon.sources import (
    _read_cems_layer,
    _positive_damage_layer,
    normalize_bc_inventory,
    normalize_climate_feature,
    normalize_hydrometric_feature,
)


def test_approved_cases_have_bounded_wgs84_boxes() -> None:
    assert set(CASES) == {"ahr-2021", "bc-2021"}
    for case in CASES.values():
        west, south, east, north = case["bbox"]
        assert -180 <= west < east <= 180
        assert -90 <= south < north <= 90


def test_cems_import_transforms_prj_and_keeps_reported_grade() -> None:
    with io.BytesIO() as shp, io.BytesIO() as shx, io.BytesIO() as dbf:
        writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYLINE)
        writer.field("damage_gra", "C", size=40)
        writer.field("obj_type", "C", size=40)
        writer.line([[[111319.490793, 0], [222638.981586, 0]]])
        writer.record("No visible damage", "211-roads")
        writer.close()
        members = {
            "fixture_transportationL.shp": shp.getvalue(),
            "fixture_transportationL.shx": shx.getvalue(),
            "fixture_transportationL.dbf": dbf.getvalue(),
            "fixture_transportationL.prj": CRS.from_epsg(3857).to_wkt().encode(),
        }

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, mode="w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    with zipfile.ZipFile(archive_buffer) as archive:
        collection = _read_cems_layer(
            archive,
            layer_token="transportationL",
            source_name="fixture",
            source_crs_hint=None,
            product_id="fixture-product",
            observed_at="2021-07-18T10:50:00Z",
            available_at=None,
            product_metadata_date="2021-07-19",
            timestamp_note="fixture timestamp",
            damage_field=True,
        )

    feature = collection["features"][0]
    assert feature["geometry"]["coordinates"][0][0] == pytest.approx(1.0, abs=1e-5)
    assert feature["geometry"]["coordinates"][1][0] == pytest.approx(2.0, abs=1e-5)
    assert feature["properties"]["damage_gra"] == "No visible damage"
    assert feature["properties"]["reported_damage"] == "No visible damage"
    assert feature["properties"]["damage_label_is_model_output"] is False
    assert feature["properties"]["available_at"] is None
    assert feature["properties"]["product_metadata_date"] == "2021-07-19"


def test_positive_damage_layer_excludes_no_damage_and_unexamined_grades() -> None:
    grades = ["Destroyed", "Damaged", "Possibly Damaged", "No visible damage", "Not Analysed", None]
    assets = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": str(index), "geometry": None, "properties": {"reported_damage": grade, "damage_gra": grade}}
            for index, grade in enumerate(grades)
        ],
    }
    damaged = _positive_damage_layer(assets)
    assert [feature["properties"]["reported_damage"] for feature in damaged["features"]] == grades[:3]
    assert all(feature["properties"]["damage_gra"] == feature["properties"]["reported_damage"] for feature in damaged["features"])
    assert all(feature["properties"]["damage_evidence_filter"] == "positive agency grade" for feature in damaged["features"])


def test_hydrometric_missing_and_estimated_values_keep_quality_semantics() -> None:
    feature = {
        "type": "Feature",
        "id": "08LG010.2021-11-15",
        "geometry": {"type": "Point", "coordinates": [-120.8, 50.1]},
        "properties": {
            "IDENTIFIER": "08LG010.2021-11-15",
            "STATION_NUMBER": "08LG010",
            "STATION_NAME": "Coldwater River at Merritt",
            "DATE": "2021-11-15",
            "LEVEL": None,
            "LEVEL_SYMBOL_EN": None,
            "DISCHARGE": 239.0,
            "DISCHARGE_SYMBOL_EN": "Estimated",
        },
    }
    level, flow = normalize_hydrometric_feature(feature)
    assert level["value"] is None
    assert level["quality_status"] == "missing"
    assert flow["value"] == 239.0
    assert flow["quality_flag"] == "Estimated"
    assert flow["quality_status"] == "flagged"
    assert flow["unit"] == "m3/s"
    assert flow["observed_at"] == "2021-11-15"
    assert flow["parameter"] == "discharge"
    assert flow["date"] == "2021-11-15"


def test_climate_null_precipitation_is_unknown_and_flags_are_retained() -> None:
    records = normalize_climate_feature(
        {
            "geometry": {"type": "Point", "coordinates": [-120.8, 50.1167]},
            "properties": {
                "ID": "1125070.2021.11.20",
                "CLIMATE_IDENTIFIER": "1125070",
                "STATION_NAME": "Merritt",
                "LOCAL_DATE": "2021-11-20 00:00:00",
                "TOTAL_PRECIPITATION": None,
                "TOTAL_PRECIPITATION_FLAG": "M",
                "MAX_TEMPERATURE": 3.1,
                "MAX_TEMPERATURE_FLAG": None,
            },
        }
    )
    rain = next(record for record in records if record["variable"] == "total_precipitation")
    assert rain["value"] is None
    assert rain["quality_flag"] == "M"
    assert rain["quality_status"] == "missing"
    assert rain["observed_at"] == "2021-11-20"


def test_current_bc_inventory_never_becomes_historical_damage() -> None:
    layer = normalize_bc_inventory(
        {
            "features": [
                {
                    "id": 44,
                    "geometry": {"type": "Point", "coordinates": [-121.0, 50.1]},
                    "properties": {
                        "CROSSING_SITE_STATUS_DESC": "Barricaded/Closed",
                        "CURRENT_LOAD_RATING": 0,
                        "LAST_INSPECTION_DATE": 1700092800000,
                    },
                }
            ]
        },
        retrieved_at="2026-10-03T20:00:00Z",
    )
    props = layer["features"][0]["properties"]
    assert props["CROSSING_SITE_STATUS_DESC"] == "Barricaded/Closed"
    assert props["reported_damage"] is None
    assert props["event_damage_assessment"] is False
    assert props["evidence_class"] == "current_asset_inventory"
    assert props["inventory_retrieved_at"] == "2026-10-03T20:00:00Z"
    assert props["last_inspection_at"] == "2023-11-16"
