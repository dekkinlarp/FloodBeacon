"""Check attribution evaluation safeguards independently of CUDA execution."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin

pytest.importorskip("torch", reason="SpaceNet runner uses the optional damage-research group")
pytest.importorskip("PIL", reason="SpaceNet visuals use the optional damage-research group")

spec = importlib.util.spec_from_file_location("spacenet8_research", Path(__file__).parents[1] / "scripts/benchmark_spacenet8.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_pixels_are_excluded_and_empty_class_recall_unknown():
    truth = np.array([[4, 3, 255]], dtype=np.uint8)
    prediction = np.array([[3, 3, 4]], dtype=np.uint8)
    matrix = module.confusion(truth, prediction)
    results = module.metrics(matrix)["classes"]
    assert matrix.sum() == 2
    assert results[4]["support_pixels"] == 1
    assert results[4]["predicted_pixels"] == 0
    assert results[4]["recall"] == 0
    assert results[4]["precision"] is None
    assert results[2]["recall"] is None


def test_road_buffer_is_meters_and_unknown_geometry_is_retained():
    # Around latitude50.5 a 0.00001deg grid is roughly0.7x1.1m.
    profile = {"transform": from_origin(6.95, 50.5, 0.00001, 0.00001),
               "crs": "EPSG:4326", "height": 100, "width": 100}
    rows = [{"Wkt_Pix": "LINESTRING (10 20, 80 20)", "Object": "Road", "Flooded": "True"},
            {"Wkt_Pix": "POLYGON ((40 40, 50 40, 50 50, 40 50, 40 40))", "Object": "Building", "Flooded": "Null"}]
    mask = module.reference_mask(rows, profile)
    assert 300 < (mask == 4).sum() < 800
    assert mask[45, 45] == 255
    assert mask[80, 80] == 0


def test_building_channel_priority_matches_author_argmax():
    profile = {"transform": from_origin(6.95, 50.5, 0.00001, 0.00001),
               "crs": "EPSG:4326", "height": 100, "width": 100}
    rows = [{"Wkt_Pix": "LINESTRING (10 20, 80 20)", "Object": "Road", "Flooded": "True"},
            {"Wkt_Pix": "POLYGON ((40 15, 50 15, 50 25, 40 25, 40 15))", "Object": "Building", "Flooded": "False"}]
    mask = module.reference_mask(rows, profile)
    assert mask[20, 45] == 1
    assert mask[20, 20] == 4
