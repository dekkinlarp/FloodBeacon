"""Historical case-study areas and their source configurations."""

from __future__ import annotations

CASES: dict[str, dict[str, object]] = {
    "ahr-2021": {
        "id": "ahr-2021",
        "name": "Ahr Valley, Germany (EMSR517 AOI 15)",
        "bbox": [6.88, 50.37, 7.17, 50.59],
        "description": (
            "July 2021 Ahr Valley flood. Copernicus EMS agency assessments are "
            "kept distinct from FloodBeacon detections."
        ),
    },
    "bc-2021": {
        "id": "bc-2021",
        "name": "Merritt and Nicola Valley, British Columbia",
        "bbox": [-121.48, 50.05, -120.7, 50.25],
        "description": (
            "November 2021 British Columbia floods. The Coldwater gauge is one "
            "local measurement, not a proxy for every asset in the area."
        ),
    },
}

# Source configuration intentionally lives apart from case display metadata.
CASE_SOURCES: dict[str, dict[str, object]] = {
    "ahr-2021": {
        "cems_vector_zip": (
            "https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/"
            "activations/EMSR517/EMSR517_AOI15_GRA_PRODUCT_r1_RTP01_v1_vector.zip"
        ),
        "product_id": "EMSR517_AOI15_GRA_PRODUCT_r1_RTP01_v1",
        "product_metadata_date": "2021-07-19",
        "scene_time": "2021-07-18T10:50:00Z",
        "scene_time_note": (
            "Product map scene time; individual feature observation times are not provided."
        ),
    },
    "bc-2021": {
        "hydrometric_station": "08LG010",
        "observation_start": "2021-11-01",
        "observation_end": "2021-11-30",
        "climate_bbox": [-121.48, 50.05, -120.7, 50.25],
        "bridge_layer_url": (
            "https://delivery.maps.gov.bc.ca/arcgis/rest/services/whse/"
            "bcgw_pub_whse_forest_tenure/MapServer/38"
        ),
    },
}


def get_case(case_id: str) -> dict[str, object]:
    """Return a case config or raise a useful error for unknown identifiers."""
    try:
        return CASES[case_id]
    except KeyError as exc:
        raise ValueError(f"Unknown FloodBeacon case: {case_id}") from exc
