"""Prepare a small attributed CEMS flood reference from the cached vector ZIP.

This processing module is separate from API serving. Its output includes both
agency ``Flooded area`` and retrospective ``Flood trace`` polygons, retaining
those distinctions; it is not a FloodBeacon water classification.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from pyproj import Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

from floodbeacon.cases import CASES, CASE_SOURCES


SOURCE_SHA256 = "e47c8c3ef9298a93b6e0696b0d279b31754bbb59a6ef2dfbe32451009c281bf3"
MEMBER = "EMSR517_AOI15_GRA_PRODUCT_observedEventA_r1_v1.json"


def prepare_flood_extent(data_dir: Path, output_dir: Path) -> dict:
    """Validate cached source and publish its study-bounded GeoJSON and provenance."""
    config = CASE_SOURCES["ahr-2021"]
    source_path = data_dir / "raw/ahr-2021" / (config["product_id"] + "_vector.zip")
    source_bytes = source_path.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("CEMS archive checksum differs from the reviewed source")
    download = json.loads(source_path.with_suffix(".zip.json").read_text())
    if download["sha256"] != SOURCE_SHA256:
        raise ValueError("Cached CEMS retrieval metadata does not match source")
    with zipfile.ZipFile(source_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CEMS archive failed member CRC validation")
        member_bytes = archive.read(MEMBER)
    collection = json.loads(member_bytes)
    if collection.get("crs", {}).get("properties", {}).get("name") != "urn:ogc:def:crs:OGC:1.3:CRS84":
        raise ValueError("Expected CEMS GeoJSON in WGS84 longitude/latitude")
    study_bounds = CASES["ahr-2021"]["bbox"]
    study = box(*study_bounds)
    projected = Transformer.from_crs(4326, 25832, always_xy=True).transform
    features = []
    geometries = []
    areas = Counter()
    for index, feature in enumerate(collection["features"]):
        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Invalid CEMS flood polygon")
        if not geometry.intersects(study):
            continue
        geometry = geometry.intersection(study)
        properties = dict(feature["properties"])
        if properties.get("notation") not in {"Flooded area", "Flood trace"}:
            raise ValueError("Unexpected agency flood notation")
        areas[properties["notation"]] += transform(projected, geometry).area / 1_000_000
        properties.update(
            evidence_source="Copernicus EMS agency interpretation",
            evidence_layer="observedEventA",
            source_product_id=config["product_id"],
            observed_at=config["scene_time"],
            available_at=None,
            product_metadata_date=config["product_metadata_date"],
            timestamp_precision_note=config["scene_time_note"],
        )
        features.append({"type": "Feature", "id": f"cems-flood-{index}",
                         "geometry": mapping(geometry), "properties": properties})
        geometries.append(geometry)
    bounds = [min(g.bounds[0] for g in geometries), min(g.bounds[1] for g in geometries),
              max(g.bounds[2] for g in geometries), max(g.bounds[3] for g in geometries)]
    output = {"type": "FeatureCollection", "features": features}
    payload = (json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    provenance = {
        "source": "Copernicus EMSR517 AOI15 observedEventA",
        "source_url": config["cems_vector_zip"],
        "source_product_id": config["product_id"],
        "source_sha256": SOURCE_SHA256,
        "source_member": MEMBER,
        "source_member_sha256": hashlib.sha256(member_bytes).hexdigest(),
        "retrieved_at": download["retrieved_at"],
        "observed_at": config["scene_time"],
        "available_at": None,
        "product_metadata_date": config["product_metadata_date"],
        "timestamp_precision_note": config["scene_time_note"],
        "license": "Copernicus EMS information; free reproduction, distribution and adaptation with attribution",
        "license_url": "https://mapping.emergency.copernicus.eu/terms-and-conditions/",
        "attribution": "Contains modified Copernicus EMS information (2021).",
        "citation_url": "https://mapping.emergency.copernicus.eu/about/citation-guidelines/",
        "source_crs": "OGC:CRS84",
        "output_crs": "EPSG:4326; longitude/latitude",
        "area_crs": "EPSG:25832",
        "processing": "Validate source checksum and polygon geometry; intersect with study bounds; retain agency properties. No simplification.",
        "study_bounds": study_bounds,
        "bounds": bounds,
        "feature_count": len(features),
        "notation_counts": dict(Counter(f["properties"]["notation"] for f in features)),
        "area_km2_by_notation": dict(areas),
        "limitations": [
            "Flood trace is retrospective evidence of inundation, not water present at the reference scene time.",
            "Agency photo-interpretation; not output from a FloodBeacon detector.",
            "Product reference time does not provide per-feature observation times or first public availability.",
            "Coverage is EMSR517 AOI15 within the selected study area, not all of the German flood event.",
        ],
        "url": "/static/imagery/ahr-region/flood-extent.geojson",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "flood-extent.geojson").write_bytes(payload)
    (output_dir / "flood-extent-source.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance
