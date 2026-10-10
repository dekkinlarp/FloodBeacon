"""Reproduce manually reviewed Ahr bridge before/after imagery; no ML inference.

Run: uv run --group damage-research python scripts/prepare_bridge_demo_existing.py

Requires the existing EMSR517 AOI15 vector ZIP in data/raw/ahr-2021. Outputs
are ignored research artifacts. Reuses the existing verified RLP WMS requests,
including their protocol version, to preserve reproducibility. The imagery is
an aerial orthophoto, not satellite imagery. No new dependency is required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import rasterio
from rasterio.warp import transform
from shapely.geometry import shape

from prepare_ahr_imagery import ISO_METADATA_URL, SOURCES, urls

DEFAULT_OUTPUT = Path("data/research/bridge-demo-existing")
VECTOR_PATH = Path("data/raw/ahr-2021/EMSR517_AOI15_GRA_PRODUCT_r1_RTP01_v1_vector.zip")
PRODUCT_ID = "EMSR517_AOI15_GRA_PRODUCT_r1_RTP01_v1"
METADATA_URL = "https://www.geoportal.rlp.de/mapbender/php/mod_showMetadata.php?id=73160&languageCode=de&layout=tabs&resource=layer"
LICENSE_URL = "https://www.govdata.de/dl-de/by-2-0"
ATTRIBUTION = "©GeoBasis-DE / LVermGeoRP 2026, dl-de/by-2-0, www.lvermgeo.rlp.de [Daten bearbeitet]"
TARGETS = {
    "rech": {
        "name": "Nepomukbrücke", "place": "Rech",
        "sha256": ["52e560962768f49439104914cb0176f199d72bae3208dc6cbd31d4823982c0dc", "fbfb55380aac0b01e6e2549184e130cf0d73da9c5132bfc266f941a2f9d6743d"],
        "finding": "Continuous bridge before; northern section remains after, with southern span/connection absent and widened river channel.",
        "confidence": "high for visible missing crossing segment; no engineering assessment of surviving arches",
        "before_label": "Continuous bridge crossing", "after_label": "Southern span / connection missing",
        "evidence_urls": [
            "https://kreis-ahrweiler.de/denkmalrechtliche-genehmigung-fuer-den-abbruch-der-nepomuk-bruecke-in-rech/",
            "https://www.kv-aw.drk.de/leichte-sprache/aktuelles-presse/aktuelle-informationen/meldung/pressemitteilung-07-22-drk-wasserwacht-rheinland-pfalz-uebt-in-der-ahr-wasserwachttaucher-begutachten-fundament-der-nepomukbruecke-in-rech.html",
        ],
    },
    "dernau": {
        "name": "Josefstraße", "place": "Dernau",
        "sha256": ["0697df9e12e012704f0ccba1955de5a8839ff6bff2fa4265a899900d0d41884b", "0f75232008973ceb966637d052261e7d1b0e24c6933d6e5a9a0206dacdd79ee9"],
        "finding": "Bridge deck remains connected to northern approach after; southern end has exposed irregular remnants and lacks the former connection across the widened channel.",
        "confidence": "moderate for lost southern connection; high for major visible physical change; mechanism not determined",
        "before_label": "Continuous crossing; trees obscure edge", "after_label": "Southern connection interrupted",
        "evidence_urls": [],
    },
    "ahrweiler": {
        "name": "Karl-von-Ehrenwall-Allee", "place": "Ahrweiler",
        "sha256": ["285057d627c118b9ae16c764a290d60d1c399f61d8aec5d73e38ce5966f061c8", "ce3becd2a5716c29f65ec311c35dfc4948a9d28ae4de0533e44afd29e586d542"],
        "finding": "Narrow diagonal bridge is continuous before; the crossing deck is absent after, with isolated small remnants in the widened river channel.",
        "confidence": "high for visible missing bridge crossing; precise component/failure mechanism unknown",
        "before_label": "Continuous diagonal footbridge", "after_label": "Crossing deck absent",
        "evidence_urls": [],
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(client: httpx.Client, url: str, path: Path, maximum: int = 16 * 1024 * 1024) -> None:
    if path.exists():
        return
    body = bytearray()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > maximum:
                raise ValueError("Response exceeded bounded research download limit")
    path.write_bytes(body)


def metadata_value(raw: str, label: str) -> str | None:
    match = re.search(rf'{label}:</b>"\s*,\s*"([^"\n]+)"', raw)
    return match.group(1) if match else None


def annotate(images: list[Image.Image], target: dict, output: Path) -> None:
    """Enlarge real evidence pixels and add labels; no reconstruction or filling."""
    panel = Image.new("RGB", (1600, 1010), "#111827")
    draw = ImageDraw.Draw(panel)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 26) if font_path.exists() else ImageFont.load_default(size=26)
    small = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default(size=18)
    draw.text((24, 16), f"{target['name']} — {target['place']}, Ahr Valley", font=font, fill="white")
    draw.text((24, 55), "Aerial orthophotos • manual visual review • same 144 m × 144 m crop", font=small, fill="#d1d5db")
    for index, image in enumerate(images):
        crop = image.crop((332, 332, 692, 692)).resize((800, 800), Image.Resampling.NEAREST)
        panel.paste(crop, (index * 800, 112))
        draw.text((index * 800 + 24, 82), "2019-06-27 — before" if index == 0 else "July 2021 — after (collection flight dates)", font=small, fill="white")
        # Rectangle encompasses the entire crossing including its lost southern end.
        draw.rectangle((index * 800 + 267, 312, index * 800 + 511, 690), outline="#fbbf24", width=4)
        draw.text((index * 800 + 24, 920), target['before_label'] if index == 0 else target['after_label'], font=small, fill="#fbbf24")
    draw.text((24, 957), "Agency grade: Destroyed (CEMS EMSR517). Rectangle: manual region of interest; no model output.", font=small, fill="white")
    draw.text((24, 985), ATTRIBUTION, font=small, fill="#d1d5db")
    panel.save(output)


def prepare(output: Path, targets: list[str]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(VECTOR_PATH) as archive:
        features = json.loads(archive.read("EMSR517_AOI15_GRA_PRODUCT_transportationL_r1_v1.json"))["features"]
    with httpx.Client(timeout=60, follow_redirects=True, max_redirects=5) as client:
        for short in targets:
            target = TARGETS[short]
            feature = next(f for f in features if f["properties"]["name"] == target["name"]
                           and f["properties"]["damage_gra"] == "Destroyed"
                           and f["properties"]["info"] == "2141-Bridges and elevated highways")
            centroid = shape(feature["geometry"]).centroid
            xx, yy = transform("EPSG:4326", "EPSG:25832", [centroid.x], [centroid.y])
            x, y = xx[0], yy[0]
            bbox = (x - 204.8, y - 204.8, x + 204.8, y + 204.8)
            now = datetime.now(timezone.utc).isoformat()
            manifest_path = output / f"{short}-manifest.json"
            previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
            manifest = {
                "target_id": f"ahr-2021-{short}", "target": target["name"], "place": target["place"],
                "lon": centroid.x, "lat": centroid.y, "coordinate_source": "CEMS explicit bridge feature centroid",
                "cems_feature": feature, "source_product": PRODUCT_ID, "source_zip_sha256": sha256(VECTOR_PATH),
                "source_url": "https://mapping.emergency.copernicus.eu/activations/EMSR517/",
                "source_observation_time": "2021-07-18T10:50:00Z", "agency_publication_date": "2021-07-19",
                "retrieved_at": previous.get("retrieved_at", now), "verified_at": now,
                "modality": "aerial orthophoto (not satellite)", "imagery": [],
                "manual_finding": target["finding"], "manual_confidence": target["confidence"],
                "evidence_urls": target["evidence_urls"], "manual_reviewed_at": now,
                "model_output": False, "historical_note": "Retrospective comparison; post-image publication does not prove availability in July 2021.",
            }
            images = []
            for index, (period, source) in enumerate(SOURCES.items()):
                url, meta_url = urls(source, bbox)
                image_path = output / f"{short}-{period}.tif"
                meta_path = output / f"{short}-{period}-metadata.html"
                fetch(client, url, image_path)
                if sha256(image_path) != target["sha256"][index]:
                    raise ValueError(f"Source TIFF checksum changed: {image_path}; investigate before updating pin")
                fetch(client, meta_url, meta_path, 1024 * 1024)
                raw_meta = meta_path.read_text()
                with rasterio.open(image_path) as raster:
                    if raster.crs.to_epsg() != 25832 or raster.shape != (1024, 1024) or raster.count != 4:
                        raise ValueError("Unexpected source raster grid")
                    if not np.allclose(raster.res, (0.4, 0.4), atol=1e-8):
                        raise ValueError("Unexpected output pixel spacing")
                    image = Image.fromarray(raster.read([1, 2, 3]).transpose(1, 2, 0))
                    image.save(image_path.with_suffix(".png"))
                    images.append(image)
                    manifest["imagery"].append({
                        "path": str(image_path.resolve()), "png_path": str(image_path.with_suffix(".png").resolve()),
                        "url": url, "metadata_url": meta_url, "sha256": sha256(image_path), "crs": str(raster.crs),
                        "bounds": list(raster.bounds), "resolution_m": list(raster.res),
                        "source_item_id": metadata_value(raw_meta, "Blattname") or metadata_value(raw_meta, "Name"),
                        "acquisition_date": metadata_value(raw_meta, "Bildflugdatum"),
                        "collection_acquisition_dates": source.get("acquisition_dates"),
                        "metadata_creation_date": metadata_value(raw_meta, "Erstellung") if index else None,
                        "metadata_publication_time": metadata_value(raw_meta, "Publikation"),
                        "date_note": "Bildflugdatum is explicit flight date; Erstellung means creation and is not asserted as the chip flight date. Publication timezone unknown.",
                        "alpha_valid_pixels": int(np.count_nonzero(raster.read(4))), "total_pixels": 1024 * 1024,
                        "native_resolution_m": 0.2 if index == 0 else 0.4,
                        "license": "dl-de-by-2.0", "license_url": LICENSE_URL,
                        "dataset_metadata_url": METADATA_URL, "source_iso_metadata_url": ISO_METADATA_URL,
                        "attribution": ATTRIBUTION,
                    })
            panel_path = output / f"{short}-before-after.png"
            annotate(images, target, panel_path)
            manifest["annotated_image"] = str(panel_path.resolve())
            manifest["generated_outputs"] = [{"path": str(p.resolve()), "sha256": sha256(p)} for p in
                [panel_path, *(Path(a["png_path"]) for a in manifest["imagery"])]]
            manifest["display_processing"] = "Native RGB unchanged; 360×360-pixel crop enlarged with nearest-neighbour; rectangle and captions added separately. Raw TIFF retains alpha/no-data."
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"{short}: verified TIFF pair, regenerated manual-review panel and manifest", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--targets", nargs="+", choices=TARGETS, default=["rech", "ahrweiler", "dernau"])
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.targets)
