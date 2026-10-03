"""Batch inference on fixed, metric grids using public Sentinel-1 RTC assets."""

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from shapely.geometry import mapping, shape
from shapely.ops import transform as geometry_transform
from pyproj import Transformer

from floodbeacon.ml import load_model, predict_water

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SCENES = {
    "ahr-2021": (
        "S1A_IW_GRDH_1SDV_20210703T055051_20210703T055116_038609_048E45_rtc",
        "S1A_IW_GRDH_1SDV_20210715T055052_20210715T055117_038784_049389_rtc",
        "EPSG:32632",
    ),
    "bc-2021": (
        "S1B_IW_GRDH_1SDV_20211104T142031_20211104T142056_029439_038363_rtc",
        "S1B_IW_GRDH_1SDV_20211116T142031_20211116T142056_029614_0388BC_rtc",
        "EPSG:32610",
    ),
}


def _json_get(client, url, params=None):
    for attempt in range(3):
        try:
            response = client.get(url, params=params)
            if response.status_code not in (429, 502, 503, 504):
                response.raise_for_status()
                return response.json()
        except httpx.TransportError:
            pass
        if attempt < 2:
            time.sleep(attempt + 1)
    raise RuntimeError("Satellite metadata/signing service unavailable after three attempts")


def grid_for_bbox(bbox, crs, resolution=20):
    west, south, east, north = transform_bounds("EPSG:4326", crs, *bbox)
    width = math.ceil((east - west) / resolution)
    height = math.ceil((north - south) / resolution)
    if width * height > 4_000_000:
        raise ValueError("POC grid exceeds four million pixels; narrow the study area")
    return from_origin(west, north, resolution, resolution), width, height


def read_scene(scene_id, bbox, crs, data_dir, resolution=20):
    """Read only the requested AOI. Cache local arrays; never persist SAS URLs."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    grid, width, height = grid_for_bbox(bbox, crs, resolution)
    key = hashlib.sha256(json.dumps([scene_id, bbox, crs, resolution]).encode()).hexdigest()[:16]
    cache = data_dir / f"{key}.npz"
    metadata_path = data_dir / f"{key}.json"
    if cache.exists() and metadata_path.exists():
        with np.load(cache) as arrays:
            metadata = json.loads(metadata_path.read_text())
            metadata.setdefault("catalog_created_at", metadata.get("available_at"))
            metadata["available_at"] = None
            metadata["availability_note"] = "Historical first availability was not verified; catalog creation is not a release timestamp."
            return arrays["vv"], arrays["vh"], grid, metadata
    item_url = f"{STAC}/collections/sentinel-1-rtc/items/{scene_id}"
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        item = _json_get(client, item_url)
        arrays = []
        asset_urls = {}
        for polarization in ("vv", "vh"):
            href = item["assets"][polarization]["href"]
            asset_urls[polarization] = href
            signed = _json_get(client,
                "https://planetarycomputer.microsoft.com/api/sas/v1/sign",
                params={"href": href},
            )
            # GDAL may include the URL in its error. Do not expose that signed URL.
            try:
                with rasterio.Env(
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                    GDAL_HTTP_TIMEOUT="90",
                    GDAL_HTTP_MAX_RETRY="2",
                ):
                    with rasterio.open(signed["href"]) as src:
                        with WarpedVRT(
                            src, crs=crs, transform=grid, width=width, height=height,
                            resampling=Resampling.average, nodata=-32768,
                        ) as vrt:
                            linear = vrt.read(1, masked=True).filled(np.nan).astype("float32")
            except rasterio.errors.RasterioError:
                raise RuntimeError(f"Raster access failed for {scene_id}/{polarization}") from None
            valid = np.isfinite(linear) & (linear > 0)
            db = np.full(linear.shape, np.nan, dtype="float32")
            db[valid] = 10 * np.log10(linear[valid])
            arrays.append(db)
    metadata = {
        "id": scene_id, "url": item_url,
        "observed_at": item["properties"]["datetime"],
        "available_at": None,
        "catalog_created_at": item["properties"].get("created"),
        "availability_note": "Historical first availability was not verified; catalog creation is not a release timestamp.",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "assets": asset_urls, "crs": crs, "resolution_m": resolution,
        "bbox": bbox, "shape": [height, width],
        "units": "gamma-naught dB converted from positive RTC linear values",
        "relative_orbit": item["properties"].get("sat:relative_orbit"),
        "cache_sha256": None,
    }
    np.savez_compressed(cache, vv=arrays[0], vh=arrays[1])
    metadata["cache_sha256"] = hashlib.sha256(cache.read_bytes()).hexdigest()
    metadata_path.write_text(json.dumps(metadata, indent=2))
    return arrays[0], arrays[1], grid, metadata


def mask_features(mask, grid, crs, properties, minimum_pixels=1):
    """Convert a raster mask into WGS84 features without treating nodata as dry."""
    selected = mask.astype("uint8")
    to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    features = []
    for geom, value in shapes(selected, mask=selected.astype(bool), transform=grid):
        if value == 1:
            metric = shape(geom)
            if metric.area < minimum_pixels * abs(grid.a * grid.e):
                continue
            features.append({
                "type": "Feature", "id": f"{properties['kind']}-{len(features)}",
                "geometry": mapping(geometry_transform(to_wgs84, metric)),
                "properties": {**properties, "area_m2": metric.area},
            })
    return {"type": "FeatureCollection", "features": features}


def infer_case(case, model_path, data_dir, threshold=0.5):
    before, after, crs = SCENES[case["id"]]
    pre_vv, pre_vh, grid, pre_meta = read_scene(before, case["bbox"], crs, data_dir)
    post_vv, post_vh, _, post_meta = read_scene(after, case["bbox"], crs, data_dir)
    pre_valid = np.isfinite(pre_vv) & np.isfinite(pre_vh)
    post_valid = np.isfinite(post_vv) & np.isfinite(post_vh)
    jointly_valid = pre_valid & post_valid
    model = load_model(Path(model_path))
    pre_score = predict_water(model, pre_vv, pre_vh, pre_valid)
    post_score = predict_water(model, post_vv, post_vh, post_valid)
    new_water = jointly_valid & (post_score >= threshold) & (pre_score < threshold)
    base = {
        "observed_at": post_meta["observed_at"], "method": "supervised SAR water classifier",
        "evidence_type": "modeled_exposure", "classification_threshold": threshold,
        "structural_damage": "unknown", "score_calibration": "uncalibrated",
    }
    layers = {
        "modeled_new_water": mask_features(new_water, grid, crs, {**base, "kind": "modeled_new_water"}, minimum_pixels=4),
        "modeled_event_water": mask_features(post_valid & (post_score >= threshold), grid, crs, {**base, "kind": "modeled_event_water"}, minimum_pixels=4),
        "valid_coverage": mask_features(jointly_valid, grid, crs, {"kind": "valid_coverage", "evidence_type": "coverage", "observed_at": post_meta["observed_at"]}),
        "unknown_coverage": mask_features(~jointly_valid, grid, crs, {"kind": "unknown_coverage", "evidence_type": "unknown", "observed_at": post_meta["observed_at"]}),
    }
    metrics = {
        "valid_fraction": float(jointly_valid.mean()),
        "coverage_definition": "Finite positive VV/VH input in both scenes; terrain shadow/layover is not screened.",
        "new_water_area_m2_before_filter": int(new_water.sum()) * 400,
        "processing_resolution_m": 20,
        "minimum_component_pixels": 4,
        "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
        "limitations": [
            "Water classification indicates exposure, not destroyed infrastructure.",
            "Sen1Floods11 training and terrain-corrected gamma-naught inputs have domain differences.",
            "No bridge failure time, route passability, or boat navigability is inferred.",
            "Radar shadow/layover and vegetated/urban flooding are not fully resolved by this POC.",
            "Scene sampling can miss peak flooding; source dates differ from agency assessments.",
        ],
    }
    return layers, [pre_meta, post_meta], metrics
