"""Retrieval and normalization for the two approved historical cases.

The output contract is intentionally small: RFC 7946 GeoJSON layers,
time-stamped hydrometeorological observations, and per-input provenance.
Reported agency evidence, current inventory status, and FloodBeacon model
outputs remain separate.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape as make_geometry
from shapely.ops import transform as transform_geometry

from floodbeacon.cases import CASE_SOURCES, get_case

ECCC_API = "https://api.weather.gc.ca"
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=20.0)
_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
_MAX_OGC_PAGES = 20


def ingest_case(
    case_id: str, data_dir: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch a case's public inputs and return layers, observations, provenance.

    ``data_dir`` holds cached CEMS input and timestamped API response snapshots.
    Network errors are surfaced to the caller; partial successful results are
    not silently presented as complete ingestions.
    """
    get_case(case_id)
    source_config = CASE_SOURCES[case_id]
    root = Path(data_dir)
    (root / "raw").mkdir(parents=True, exist_ok=True)

    if case_id == "ahr-2021":
        return _ingest_ahr(source_config, root)
    if case_id == "bc-2021":
        return _ingest_bc(source_config, root)
    # Keep the explicit guard even though get_case and CASE_SOURCES currently
    # have the same keys: adding display metadata must not imply data support.
    raise ValueError(f"No source ingestion implemented for case: {case_id}")


def _ingest_ahr(
    config: dict[str, object], data_dir: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    url = str(config["cems_vector_zip"])
    cache_path, download = _download_cached_zip(url, data_dir / "raw" / "ahr-2021")
    product_id = str(config["product_id"])
    observed_at = str(config["scene_time"])
    product_metadata_date = str(config["product_metadata_date"])

    with zipfile.ZipFile(cache_path) as archive:
        transportation = _read_cems_layer(
            archive,
            layer_token="transportationL",
            source_name="CEMS EMSR517 transportation assessment",
            source_crs_hint=None,
            product_id=product_id,
            observed_at=observed_at,
            available_at=None,
            product_metadata_date=product_metadata_date,
            timestamp_note=str(config["scene_time_note"]),
            damage_field=True,
        )
        flood_areas = _read_cems_layer(
            archive,
            layer_token="observedEventA",
            source_name="CEMS EMSR517 observed flood extent",
            source_crs_hint=None,
            product_id=product_id,
            observed_at=observed_at,
            available_at=None,
            product_metadata_date=product_metadata_date,
            timestamp_note=str(config["scene_time_note"]),
            damage_field=False,
        )

    provenance = [
        {
            "source_id": "cems-emsr517-aoi15",
            "title": "Copernicus Emergency Management Service EMSR517 AOI15 vector product",
            "source_url": url,
            "retrieved_at": download["retrieved_at"],
            "source_product_id": product_id,
            "product_metadata_date": product_metadata_date,
            "available_at": None,
            "sha256": download["sha256"],
            "bytes": download["bytes"],
            "raw_file": str(cache_path.relative_to(data_dir)),
            "crs_source": "Read from each shapefile .prj; output is WGS84 longitude/latitude.",
            "license": "Copernicus EMS product; attribution and third-party imagery terms apply.",
            "license_url": "https://mapping.emergency.copernicus.eu/terms-and-conditions/",
            "attribution": "Contains modified Copernicus EMS information (2021).",
            "citation_url": "https://mapping.emergency.copernicus.eu/about/citation-guidelines/",
            "notes": [
                "damage_gra is the agency-reported grade, not a FloodBeacon detector result.",
                "No visible damage and Not Analysed are preserved as reported; neither proves an asset is intact.",
                "The product metadata date is not independently verified as first public-availability time.",
                "The scene time is a product-level reference; per-feature observation times are unavailable.",
                "The flood polygons are agency-interpreted observedEventA evidence, not a model output.",
            ],
        }
    ]
    return (
        {
            "assets": transportation,
            "reported_damage": _positive_damage_layer(transportation),
            "agency_flood_reference": flood_areas,
        },
        [],
        provenance,
    )


def _read_cems_layer(
    archive: zipfile.ZipFile,
    *,
    layer_token: str,
    source_name: str,
    source_crs_hint: str | None,
    product_id: str,
    observed_at: str,
    available_at: str | None,
    timestamp_note: str,
    damage_field: bool,
    product_metadata_date: str | None = None,
) -> dict[str, Any]:
    shp_name = next(
        (name for name in archive.namelist() if name.endswith(".shp") and layer_token in name),
        None,
    )
    if shp_name is None:
        raise ValueError(f"CEMS vector archive has no {layer_token} shapefile")
    stem = shp_name[:-4]
    missing = [suffix for suffix in (".dbf", ".shx", ".prj") if stem + suffix not in archive.namelist()]
    if missing:
        raise ValueError(f"CEMS layer {layer_token} is missing required files: {missing}")

    prj_text = archive.read(stem + ".prj").decode("utf-8", errors="replace").strip()
    source_crs = CRS.from_user_input(source_crs_hint or prj_text)
    transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
    reader = shapefile.Reader(
        shp=io.BytesIO(archive.read(shp_name)),
        shx=io.BytesIO(archive.read(stem + ".shx")),
        dbf=io.BytesIO(archive.read(stem + ".dbf")),
        encoding="utf-8",
        encodingErrors="replace",
    )
    features = []
    for source_index, shape_record in enumerate(reader.iterShapeRecords()):
        if shape_record.shape.shapeType == shapefile.NULL:
            continue
        geometry = make_geometry(shape_record.shape.__geo_interface__)
        geometry = transform_geometry(transformer.transform, geometry)
        if geometry.is_empty:
            continue
        properties = _json_safe(shape_record.record.as_dict())
        properties.update(
            {
                "evidence_source": "Copernicus EMS agency interpretation",
                "evidence_layer": layer_token,
                "source_product_id": product_id,
                "observed_at": observed_at,
                "available_at": available_at,
                "product_metadata_date": product_metadata_date,
                "timestamp_precision_note": timestamp_note,
            }
        )
        if damage_field:
            # Preserve the input field verbatim while giving the API/map a
            # stable, explicitly agency-reported label.
            properties["reported_damage"] = properties.get("damage_gra")
            properties["evidence_class"] = "agency_reported_transport_condition"
            properties["damage_label_is_model_output"] = False
        else:
            properties["evidence_class"] = "agency_observed_event_extent"
            properties["damage_label_is_model_output"] = False
        features.append(
            {
                "type": "Feature",
                "id": f"{product_id}:{layer_token}:{source_index}",
                "geometry": _json_safe(geometry.__geo_interface__),
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "name": source_name, "features": features}


def _ingest_bc(
    config: dict[str, object], data_dir: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    bbox = [float(value) for value in config["climate_bbox"]]
    start, end = str(config["observation_start"]), str(config["observation_end"])
    fetched_at = _utc_now()
    raw_dir = data_dir / "raw" / "bc-2021"

    hydro_url = f"{ECCC_API}/collections/hydrometric-daily-mean/items"
    hydro_pages = _fetch_ogc_pages(
        hydro_url,
        {"f": "json", "STATION_NUMBER": str(config["hydrometric_station"]), "datetime": f"{start}/{end}", "limit": 1000},
        raw_dir,
        "eccc-hydrometric-daily-mean",
    )
    climate_url = f"{ECCC_API}/collections/climate-daily/items"
    climate_pages = _fetch_ogc_pages(
        climate_url,
        {"f": "json", "bbox": ",".join(map(str, bbox)), "datetime": f"{start}/{end}", "limit": 100},
        raw_dir,
        "eccc-climate-daily",
    )

    bridge_url = str(config["bridge_layer_url"])
    bridge_geojson, bridge_source_url = _fetch_bc_bridge_inventory(bridge_url, bbox)
    bridge_raw = _save_json_snapshot(
        bridge_geojson,
        raw_dir,
        "bc-mof-bridges-major-culverts",
        fetched_at,
    )
    bridge_layer = normalize_bc_inventory(bridge_geojson, retrieved_at=fetched_at)

    observations: list[dict[str, Any]] = []
    for page in hydro_pages:
        for feature in page["payload"]["features"]:
            observations.extend(normalize_hydrometric_feature(feature))
    for page in climate_pages:
        for feature in page["payload"]["features"]:
            observations.extend(normalize_climate_feature(feature))

    provenance = []
    for source_id, title, url, pages, license_url in (
        (
            "eccc-hydrometric-daily-mean",
            "ECCC HYDAT hydrometric daily mean observations",
            hydro_url,
            hydro_pages,
            "https://www.canada.ca/en/environment-climate-change/services/water-overview/quantity/monitoring/survey/data-products-services/national-archive-hydat.html",
        ),
        (
            "eccc-climate-daily",
            "ECCC daily climate observations",
            climate_url,
            climate_pages,
            "https://api.weather.gc.ca/collections/climate-daily?f=html",
        ),
    ):
        provenance.append(
            {
                "source_id": source_id,
                "title": title,
                "source_url": url,
                "query_urls": [page["url"] for page in pages],
                "retrieved_at": fetched_at,
                "raw_files": [str((data_dir / page["raw_file"]).relative_to(data_dir)) for page in pages],
                "sha256": [page["sha256"] for page in pages],
                "license": "Government of Canada Open Government Licence applies; review source terms.",
                "license_url": license_url,
                "attribution": "Environment and Climate Change Canada (ECCC).",
                "crs_source": "OGC API geometries returned in WGS84 longitude/latitude.",
                "observation_period": {"start": start, "end": end},
                "notes": [
                    "Observation dates are local daily periods; the API does not supply an instant UTC observation time.",
                    "Null values and source quality symbols are retained.",
                    "These are historical observations, not forecasts or bridge-level water depth/current.",
                ],
            }
        )

    provenance.append(
        {
            "source_id": "bc-mof-bridges-major-culverts-current",
            "title": "BC Ministry of Forests Bridges and Major Culverts public layer",
            "source_url": bridge_source_url,
            "retrieved_at": fetched_at,
            "raw_file": str((data_dir / bridge_raw["raw_file"]).relative_to(data_dir)),
            "sha256": bridge_raw["sha256"],
            "license": "Publicly queryable government layer; confirm catalogue conditions before redistribution.",
            "license_url": "https://catalogue.data.gov.bc.ca/dataset/df943320-9e31-421c-8ada-d4df80518684",
            "attribution": "DataBC / Government of British Columbia, Ministry of Forests.",
            "crs_source": "ArcGIS query requested output spatial reference EPSG:4326.",
            "notes": [
                "This is a current asset inventory snapshot retrieved at retrieved_at, not a November 2021 snapshot.",
                "Current crossing status and inspection dates are not evidence of event damage or 2021 passability.",
                "The public layer exposes inventory attributes, not complete design drawings or foundation/scour details.",
            ],
        }
    )
    provenance.append(
        {
            "source_id": "bc-2021-flood-impact-map-reference",
            "title": "Flood Recovery November 2021 Impacted Routes and Structures Map",
            "source_url": (
                "https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/"
                "natural-resource-use/resource-roads/local-road-safety-information/"
                "cascades/dcs_flood2021_restrictedaccess_publicmap.pdf"
            ),
            "ingested": False,
            "format": "Static PDF map linked by the official Cascades District page",
            "map_date": "2022-05",
            "notes": [
                "Official historical route/structure impact reference; not parsed into geospatial features in this ingestion.",
                "The map is not an event-time closure log or comprehensive bridge engineering dataset.",
                "No individual damage point is inferred from this PDF link or from proximity to a bridge inventory point.",
            ],
        }
    )
    return {"assets": bridge_layer}, observations, provenance


def _positive_damage_layer(transportation: dict[str, Any]) -> dict[str, Any]:
    """Select only explicit positive agency damage grades from a transport layer."""
    positive_grades = {"destroyed", "damaged", "possibly damaged"}
    features = []
    for feature in transportation.get("features", []):
        properties = feature.get("properties") or {}
        grade = properties.get("reported_damage")
        if isinstance(grade, str) and grade.strip().casefold() in positive_grades:
            # A shallow copy prevents changes to this output layer affecting the
            # complete inventory layer; all original source properties persist.
            features.append(
                {
                    **feature,
                    "properties": {**properties, "damage_evidence_filter": "positive agency grade"},
                }
            )
    return {
        "type": "FeatureCollection",
        "name": "CEMS reported positive transportation damage grades",
        "features": features,
    }


def normalize_hydrometric_feature(feature: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize one ECCC daily-mean feature without discarding source flags."""
    props = feature.get("properties") or {}
    point = feature.get("geometry")
    result = []
    for field, unit, flag_field in (
        ("LEVEL", "m", "LEVEL_SYMBOL_EN"),
        ("DISCHARGE", "m3/s", "DISCHARGE_SYMBOL_EN"),
    ):
        value = props.get(field)
        flag = props.get(flag_field)
        result.append(
            {
                "case_id": "bc-2021",
                "source_id": "eccc-hydrometric-daily-mean",
                "series_id": props.get("STATION_NUMBER"),
                "station_name": props.get("STATION_NAME"),
                "variable": field.lower(),
                "parameter": "discharge" if field == "DISCHARGE" else "level",
                "value": value,
                "unit": unit,
                "observed_at": props.get("DATE"),
                "date": props.get("DATE"),
                "time_semantics": "local calendar-day mean; not an instant UTC reading",
                "quality_flag": flag,
                "quality_status": _quality_status(value, flag),
                "geometry": _json_safe(point),
                "source_record_id": props.get("IDENTIFIER"),
                "raw": _json_safe(props),
            }
        )
    return result


def normalize_climate_feature(feature: dict[str, Any]) -> list[dict[str, Any]]:
    """Return selected daily weather measures, keeping missing values and flags."""
    props = feature.get("properties") or {}
    point = feature.get("geometry")
    values = (
        ("TOTAL_PRECIPITATION", "mm"),
        ("MAX_TEMPERATURE", "degC"),
        ("MIN_TEMPERATURE", "degC"),
        ("MEAN_TEMPERATURE", "degC"),
    )
    result = []
    for field, unit in values:
        value = props.get(field)
        flag = props.get(f"{field}_FLAG")
        result.append(
            {
                "case_id": "bc-2021",
                "source_id": "eccc-climate-daily",
                "series_id": props.get("CLIMATE_IDENTIFIER"),
                "station_name": props.get("STATION_NAME"),
                "variable": field.lower(),
                "parameter": field.lower(),
                "value": value,
                "unit": unit,
                "observed_at": (props.get("LOCAL_DATE") or "")[:10] or None,
                "date": (props.get("LOCAL_DATE") or "")[:10] or None,
                "time_semantics": "local calendar-day observation; not an instant UTC reading",
                "quality_flag": flag,
                "quality_status": _quality_status(value, flag),
                "geometry": _json_safe(point),
                "source_record_id": props.get("ID"),
                "raw": _json_safe(props),
            }
        )
    return result


def normalize_bc_inventory(
    payload: dict[str, Any], *, retrieved_at: str
) -> dict[str, Any]:
    """Mark current BC inventory features as present-day context, not event labels."""
    features = []
    for index, feature in enumerate(payload.get("features", [])):
        properties = _json_safe(feature.get("properties") or {})
        properties.update(
            {
                "evidence_class": "current_asset_inventory",
                "event_damage_assessment": False,
                "reported_damage": None,
                "inventory_retrieved_at": retrieved_at,
            }
        )
        last_inspection = properties.get("LAST_INSPECTION_DATE")
        properties["last_inspection_at"] = _epoch_millis_date(last_inspection)
        features.append(
            {
                "type": "Feature",
                "id": str(feature.get("id", properties.get("RRI_BMC_SP_SYSID", index))),
                "geometry": _json_safe(feature.get("geometry")),
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "name": "BC current bridge and culvert inventory", "features": features}


def _quality_status(value: Any, flag: Any) -> str:
    if value is None:
        return "missing"
    if flag:
        return "flagged"
    return "unflagged"


def _epoch_millis_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _fetch_ogc_pages(
    url: str,
    params: dict[str, Any],
    raw_dir: Path,
    source_id: str,
) -> list[dict[str, Any]]:
    """Fetch OGC API Features pages and persist each exact response snapshot."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    next_url: str | None = url
    next_params: dict[str, Any] | None = params
    pages = []
    seen = set()
    with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        while next_url and len(pages) < _MAX_OGC_PAGES:
            if next_url in seen:
                raise RuntimeError(f"Pagination loop in {source_id}: {next_url}")
            seen.add(next_url)
            response = client.get(next_url, params=next_params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
                raise ValueError(f"Unexpected response from {source_id}: expected GeoJSON FeatureCollection")
            saved = _save_response_snapshot(response.content, raw_dir, source_id)
            pages.append({"payload": payload, "url": str(response.url), **saved})
            link = next((item for item in payload.get("links", []) if item.get("rel") == "next"), None)
            next_url = str(link["href"]) if link else None
            next_params = None
    if next_url:
        raise RuntimeError(f"Exceeded {_MAX_OGC_PAGES} pages fetching {source_id}")
    return pages


def _fetch_bc_bridge_inventory(base_url: str, bbox: list[float]) -> tuple[dict[str, Any], str]:
    endpoint = f"{base_url.rstrip('/')}/query"
    params = {
        "where": "1=1",
        "geometry": ",".join(map(str, bbox)),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }
    response = httpx.get(endpoint, params=params, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload or not isinstance(payload.get("features"), list):
        raise ValueError(f"Unexpected BC ArcGIS response: {payload.get('error', 'missing features')}")
    if len(payload["features"]) >= 1000:
        raise RuntimeError("BC bridge query reached ArcGIS page limit; narrow the case AOI or add object-ID pagination")
    return payload, str(response.url)


def _download_cached_zip(url: str, cache_dir: Path) -> tuple[Path, dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urlparse(url).path).name
    path = cache_dir / filename
    metadata_path = path.with_suffix(path.suffix + ".json")
    if path.exists() and _valid_zip(path):
        digest = _sha256_file(path)
        metadata = _read_json_if_exists(metadata_path) or {}
        # A newly adopted valid archive gets an integrity record, but its
        # historic retrieval time remains unknown rather than invented.
        if metadata.get("sha256") != digest:
            metadata = {
                "source_url": url,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "retrieved_at": metadata.get("retrieved_at"),
                "integrity_checked_at": _utc_now(),
            }
            _write_json_atomic(metadata_path, metadata)
        return path, metadata

    response = httpx.get(url, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    if len(response.content) > _MAX_ARCHIVE_BYTES:
        raise ValueError(f"Refusing oversized source archive ({len(response.content)} bytes)")
    if not response.content.startswith(b"PK"):
        raise ValueError("CEMS source did not return a ZIP archive")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(response.content)
    if not _valid_zip(temp):
        temp.unlink(missing_ok=True)
        raise ValueError("Downloaded CEMS ZIP failed CRC/archive validation")
    temp.replace(path)
    metadata = {
        "source_url": url,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "bytes": len(response.content),
        "retrieved_at": _utc_now(),
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "integrity": "ZIP CRC and member structure validated; SHA-256 recorded locally",
    }
    _write_json_atomic(metadata_path, metadata)
    return path, metadata


def _valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None and len(archive.namelist()) > 0
    except (OSError, zipfile.BadZipFile):
        return False


def _save_response_snapshot(content: bytes, raw_dir: Path, source_id: str) -> dict[str, Any]:
    return _save_bytes_snapshot(content, raw_dir, source_id)


def _save_json_snapshot(
    payload: dict[str, Any], raw_dir: Path, source_id: str, fetched_at: str
) -> dict[str, Any]:
    del fetched_at  # already reflected in this ingestion's provenance timestamp
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _save_bytes_snapshot(content, raw_dir, source_id)


def _save_bytes_snapshot(content: bytes, raw_dir: Path, source_id: str) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    timestamp = _utc_now().replace(":", "").replace("-", "")
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "_", source_id)
    path = raw_dir / f"{safe_id}-{timestamp}-{digest[:12]}.json"
    if not path.exists():
        path.write_bytes(content)
    return {"raw_file": str(path), "sha256": digest}


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value
