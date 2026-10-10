"""Retrieve a fixed public Ahr pre/post RGB pair for damage-model research.

Run ``uv run --group processing python scripts/prepare_ahr_imagery.py`` for populated Altenahr.
The initial forest crop remains available with ``--sample forest``.
WMS 1.1.1 is retained to reproduce the verified source requests exactly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import httpx
import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_bounds

BBOX = (362976.8339317417, 5600615.751896863, 363386.4339317417, 5601025.3518968625)
ALTENAHR_BBOX = (357542.82744040847, 5597878.304765015, 357952.42744040844, 5598287.904765015)
WIDTH = HEIGHT = 1024
MAX_DOWNLOAD = 16 * 1024 * 1024
ISO_METADATA_URL = (
    "https://www.geoportal.rlp.de/mapbender/php/mod_dataISOMetadata.php?"
    "outputFormat=iso19139&id=dc9b8a92-aea2-2df4-2177-836e91e39e8a"
)
SOURCES = {
    "ahr-vhr-pre-2019": {
        "service": "https://geo4.service24.rlp.de/wms/rp_hkdop20.fcgi",
        "layer": "rp_dop20_rgb_2019",
        "info_layer": "rp_dop20_info_2019",
        "sha256": "716b76fa8f0873d436aef3c5ae6ad0056052dcaeebdfe55e63a648899af50e0f",
        "acquisition_date": "2019-06-27",
        "date_assignment": "Center GetFeatureInfo: dop_32362_5600, explicit Bildflugdatum",
        "resolution_note": "DOP20 source rendered to the matching 0.4 m output grid",
    },
    "ahr-vhr-post": {
        "service": "https://geo4.service24.rlp.de/wms/rp_dop40_sonderbefliegung_hochwasser.fcgi",
        "layer": "rp_dop40_sonderbefliegung_hochwasser_ahr_2021_rgb",
        "info_layer": "rp_dop10_sonderbefliegung_hochwasser_ahr_2021_info",
        "sha256": "b29bb36c410c3c832269d26398ee88397230f6f4b9298c2f66a9e2f9e3f4c268",
        "acquisition_dates": ["2021-07-24", "2021-07-28", "2021-07-29"],
        "metadata_creation_date": "2021-07-24",
        "metadata_publication_time": "2021-10-12 07:27:18.609",
        "date_assignment": (
            "Center GetFeatureInfo: rgbi_32_363_560; Erstellung means creation, "
            "not explicitly flight time. Acquisition dates are collection-level."
        ),
        "availability_note": (
            "Publication timezone is unspecified; this WMS publication time does "
            "not establish earliest availability through all other channels. "
            "Do not treat the image as an input known on July 18, 2021."
        ),
    },
}
ALTENAHR_SOURCES = {
    "ahr-altenahr-vhr-pre-2019": {
        **SOURCES["ahr-vhr-pre-2019"],
        "sha256": "eef70991e2e7b6f0445ca83e9ac655b97ec301122d3b2ab562905d0fccc1ae90",
        "acquisition_date": "2019-06-28",
        "date_assignment": "Center GetFeatureInfo: dop_32356_5598, explicit Bildflugdatum",
    },
    "ahr-altenahr-vhr-post": {
        **SOURCES["ahr-vhr-post"],
        "sha256": "fdf0c042d2bd980e7b30e2c24bd2de372dec8c75e1f2c9d324d0ae0cdefe03d2",
        "metadata_publication_time": "2021-10-12 07:27:14.024",
        "date_assignment": (
            "Center GetFeatureInfo: rgbi_32_357_559; Erstellung means creation, "
            "not explicitly flight time. Acquisition dates are collection-level."
        ),
    },
}
SAMPLES = {"altenahr": (ALTENAHR_BBOX, ALTENAHR_SOURCES), "forest": (BBOX, SOURCES)}


def urls(source: dict, bbox: tuple) -> tuple[str, str]:
    common = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "STYLES": "", "SRS": "EPSG:25832",
        "BBOX": ",".join(map(str, bbox)), "WIDTH": WIDTH, "HEIGHT": HEIGHT,
    }
    image = httpx.URL(source["service"], params={
        **common, "REQUEST": "GetMap", "LAYERS": source["layer"],
        "FORMAT": "image/tiff", "TRANSPARENT": "TRUE",
        "EXCEPTIONS": "application/vnd.ogc.se_xml",
    })
    metadata = httpx.URL(source["service"], params={
        **common, "REQUEST": "GetFeatureInfo", "LAYERS": source["info_layer"],
        "QUERY_LAYERS": source["info_layer"], "X": 512, "Y": 512,
        "INFO_FORMAT": "text/html",
    })
    return str(image), str(metadata)


def retrieve(client: httpx.Client, url: str, expected_sha: str) -> bytes:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > MAX_DOWNLOAD:
                raise ValueError("Ahr imagery response exceeded the bounded download limit")
            body.extend(chunk)
    raw = bytes(body)
    if raw[:2] not in (b"II", b"MM") or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Ahr source TIFF/checksum changed; review the source before updating the pin")
    return raw


def prepare(output: Path, sample: str = "altenahr") -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    verified_at = datetime.now(timezone.utc).isoformat()
    bbox, sources = SAMPLES[sample]
    expected_transform = tuple(from_bounds(*bbox, WIDTH, HEIGHT))
    results = []
    with httpx.Client(timeout=45, follow_redirects=True, max_redirects=5) as client:
        for name, source in sources.items():
            image_url, metadata_url = urls(source, bbox)
            path = output / f"{name}.tif"
            metadata_path = output / f"{name}.json"
            previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
            cached = path.exists()
            if cached:
                if path.stat().st_size > MAX_DOWNLOAD:
                    raise ValueError(f"Oversized cached image: {name}")
                if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                    raise ValueError(f"Cached checksum mismatch: {name}; remove it to retry retrieval")
            else:
                raw = retrieve(client, image_url, source["sha256"])
                temporary = path.with_suffix(".tif.part")
                temporary.write_bytes(raw)
                temporary.replace(path)
            with rasterio.open(path) as raster:
                if raster.crs != rasterio.crs.CRS.from_epsg(25832) or raster.shape != (HEIGHT, WIDTH):
                    raise ValueError(f"Unexpected Ahr CRS/grid dimensions: {name}")
                if not np.allclose(tuple(raster.transform), expected_transform, rtol=0, atol=1e-6):
                    raise ValueError(f"Unexpected Ahr pixel alignment: {name}")
                if raster.count != 4 or raster.colorinterp[-1] != ColorInterp.alpha:
                    raise ValueError(f"Expected original RGBA imagery: {name}")
                metadata = {
                    **{key: value for key, value in source.items() if key not in {"service", "info_layer"}},
                    "url": image_url, "metadata_url": metadata_url,
                    "bbox": bbox, "width": WIDTH, "height": HEIGHT, "sample": sample,
                    "crs": "EPSG:25832", "transform": list(raster.transform),
                    "bytes": path.stat().st_size, "license": "dl-de-by-2.0",
                    "license_url": "https://www.govdata.de/dl-de/by-2-0",
                    "source_iso_metadata_url": ISO_METADATA_URL,
                    "attribution": "©GeoBasis-DE / LVermGeoRP 2026, dl-de/by-2-0, www.lvermgeo.rlp.de [Daten bearbeitet]",
                    "verified_at": verified_at, "cache_verified": cached,
                    "retrieved_at": previous.get("retrieved_at") if cached else verified_at,
                    "alpha_note": "Original fourth alpha band preserved; no pixels replaced or filled",
                    "valid_alpha_pixels": int(np.count_nonzero(raster.read(4))),
                    "purpose": "Retrospective image-pair research; no damage labels or predictions",
                    "selection_note": (
                        "Populated Altenahr crop; manually inspected visible buildings before inference"
                        if sample == "altenahr" else
                        "Initial exploratory forest crop, unsuitable for evaluating building damage"
                    ),
                }
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
            results.append(path)
            print(f"{name}: {'verified cache' if cached else 'downloaded'}, original RGBA preserved")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/research"))
    parser.add_argument("--sample", choices=SAMPLES, default="altenahr")
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.sample)
