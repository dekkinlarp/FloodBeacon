"""Publish a small, real Rech satellite comparison as package static files.

Run: uv run --locked --group processing python scripts/prepare_rech_satellite.py
TIFF inputs stay ignored. Published imagery/annotations are CC BY-SA 4.0.
This renders source RGB; it does not run a model or synthesize image content.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/research/rech-satellite"
OUT = ROOT / "src/floodbeacon/static/imagery/rech-satellite"
PUBLIC = "/static/imagery/rech-satellite"
BASE = "https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/"
LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"
ATTRIBUTION = "Satellite imagery © Maxar Technologies; SpaceNet Partners; CC BY-SA 4.0"
POINT = (7.03622715, 50.51410390)
SOURCES = [
    ("before", "2021-02-11", "PRE-event", "pre-event", "10500500C4DD7000", "dd73faaff21ad55b76a65a3b6f8a25fa747c2e50e63dadc8dcee7cb258d0d29c"),
    ("after", "2021-07-18", "POST-event", "post-event", "10500500E6DD3C00", "3f5468a4e9c1d35b46dfb87cffe049e4305719a0f6299573fc3f060a1e2a2e0b"),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def square(side):
    """A square measured in metres in local UTM, returned as WGS84 corners."""
    forward = Transformer.from_crs(4326, 25832, always_xy=True)
    backward = Transformer.from_crs(25832, 4326, always_xy=True)
    x, y = forward.transform(*POINT)
    half = side / 2
    corners = [(x-half, y-half), (x+half, y-half), (x+half, y+half), (x-half, y+half)]
    return [list(backward.transform(*p)) for p in corners + [corners[0]]]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for phase, date, folder, archive_phase, scene, expected in SOURCES:
            url = f"{BASE}{folder}/{scene}_0_40_62.tif"
            path = RAW / f"{phase}.tif"
            if not path.exists():
                body = bytearray()
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 10 * 1024 * 1024:
                            raise ValueError("Source exceeded the bounded download size")
                if hashlib.sha256(body).hexdigest() != expected:
                    raise ValueError("Downloaded source checksum changed")
                path.write_bytes(body)
            if digest(path) != expected:
                raise ValueError("Cached source checksum changed")
            archive = f"https://dg-opendata.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=events/western-europe-flooding21/{archive_phase}/{date}/"
            metadata = client.get(archive)
            metadata.raise_for_status()
            if scene not in metadata.text:
                raise ValueError("Scene not present in the retained acquisition-date folder")
            (RAW / f"{phase}-date-evidence.xml").write_bytes(metadata.content)
            with rasterio.open(path) as src:
                if src.count != 3 or src.dtypes != ("uint8",)*3:
                    raise ValueError("Expected three uint8 RGB bands")
                if not (src.bounds.left < POINT[0] < src.bounds.right and src.bounds.bottom < POINT[1] < src.bounds.top):
                    raise ValueError("Target is outside source imagery")
                records.append({"id": phase, "acquired_date": date,
                    "acquired_at": None, "date_precision": "day; provider archive folder",
                    "catalog_id": scene, "source_url": url, "source_sha256": expected,
                    "source_bytes": path.stat().st_size, "source_crs": str(src.crs),
                    "source_transform": list(src.transform)[:6],
                    "source_bounds": list(src.bounds), "source_shape": [src.height, src.width],
                    "date_evidence_url": archive,
                    "date_evidence_sha256": hashlib.sha256(metadata.content).hexdigest()})
    # Shared Web Mercator grid; the same pixel always represents the same place.
    bounds = [transform_bounds(r["source_crs"], 3857, *r["source_bounds"]) for r in records]
    common = (max(b[0] for b in bounds), max(b[1] for b in bounds),
              min(b[2] for b in bounds), min(b[3] for b in bounds))
    width, height = math.ceil(common[2]-common[0]), math.ceil(common[3]-common[1])
    grid = from_bounds(*common, width, height)
    for record in records:
        rgb = np.zeros((3, height, width), dtype="uint8")
        alpha = np.zeros((height, width), dtype="uint8")
        with rasterio.open(RAW / f'{record["id"]}.tif') as src:
            for band in range(3):
                reproject(rasterio.band(src, band+1), rgb[band], src_transform=src.transform,
                    src_crs=src.crs, dst_transform=grid, dst_crs="EPSG:3857",
                    resampling=Resampling.bilinear)
            reproject(src.dataset_mask(), alpha, src_transform=src.transform, src_crs=src.crs,
                dst_transform=grid, dst_crs="EPSG:3857", resampling=Resampling.nearest)
        image = Image.fromarray(np.dstack([rgb.transpose(1, 2, 0), alpha]))
        path = OUT / f'{record["id"]}.png'
        image.save(path)
        record.update({"url": f"{PUBLIC}/{path.name}", "sha256": digest(path),
                       "bytes": path.stat().st_size, "width": width, "height": height})
    project = Transformer.from_crs(4326, 3857, always_xy=True)
    to_wgs = Transformer.from_crs(3857, 4326, always_xy=True)
    west, south = to_wgs.transform(common[0], common[1])
    east, north = to_wgs.transform(common[2], common[3])
    ring = square(90)
    crop_points = [project.transform(*p) for p in square(180)]
    crop = (min(p[0] for p in crop_points), min(p[1] for p in crop_points),
            max(p[0] for p in crop_points), max(p[1] for p in crop_points))
    panel = Image.new("RGB", (1440, 910), "#111827")
    draw = ImageDraw.Draw(panel)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = lambda size: ImageFont.truetype(str(font_path), size) if font_path.exists() else ImageFont.load_default(size=size)
    draw.text((24, 14), "Nepomukbrücke · Rech · actual satellite imagery", font=font(27), fill="white")
    draw.text((24, 52), "Same 180 m review area · 90 m square · manual assessment", font=font(20), fill="#d1d5db")
    box = ((crop[0]-common[0])/grid.a, (common[3]-crop[3])/(-grid.e),
           (crop[2]-common[0])/grid.a, (common[3]-crop[1])/(-grid.e))
    findings = ["Continuous crossing visible", "Northern remnant; missing span across the river"]
    for i, record in enumerate(records):
        with Image.open(OUT / f'{record["id"]}.png') as source:
            zoom = source.crop(box).resize((720, 720), Image.Resampling.NEAREST)
            panel.paste(zoom, (i*720, 110), zoom)
        draw.text((i*720+24, 82), f'{record["acquired_date"]} — {record["id"]}', font=font(21), fill="white")
        outline = []
        for p in ring:
            x, y = project.transform(*p)
            outline.append((i*720+(x-crop[0])/(crop[2]-crop[0])*720,
                            110+(crop[3]-y)/(crop[3]-crop[1])*720))
        draw.line(outline, fill="#fbbf24", width=4)
        draw.text((i*720+24, 842), findings[i], font=font(19), fill="#fbbf24")
    draw.text((24, 878), ATTRIBUTION, font=font(17), fill="#d1d5db")
    panel.save(OUT / "comparison.png")
    features = []
    for record, finding in zip(records, findings):
        features.append({"type": "Feature", "id": f'rech-{record["id"]}',
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"bridge_id": "rech-nepomuk", "name": "Nepomukbrücke",
                "imagery_id": record["id"], "observed_date": record["acquired_date"],
                "finding": finding, "assessment_method": "manual image review",
                "failure_time": None, "annotation": "90 m review square; not a surveyed damage boundary"}})
    (OUT / "bridges.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2)+"\n")
    manifest = {"case_id": "ahr-2021", "target": "Nepomukbrücke, Rech", "target_coordinate": list(POINT),
        "imagery_type": "satellite RGB", "dataset": "SpaceNet 8 Germany_Training_Public", "tile_id": "0_40_62",
        "bounds": [west, south, east, north], "image_coordinates": [[west,north],[east,north],[east,south],[west,south]],
        "output_crs": "EPSG:3857", "output_transform": list(grid)[:6],
        "processing": "RGB bilinear resampling to one shared grid; mask nearest-neighbour; no color enhancement or generated pixels. Comparison zoom uses nearest-neighbour; square is a manual annotation.",
        "images": records, "comparison_url": f"{PUBLIC}/comparison.png",
        "bridges_url": f"{PUBLIC}/bridges.geojson", "license": "CC BY-SA 4.0", "license_url": LICENSE,
        "license_source": "https://spacenet.ai/sn8-challenge/", "attribution": ATTRIBUTION,
        "manual_finding": "Before: complete crossing visible. After: northern remnant with a missing span across the widened river.",
        "agency_evidence": {"source": "Copernicus EMSR517 AOI15", "grade": "Destroyed", "observed_at": "2021-07-18T10:50:00Z", "source_url": "https://mapping.emergency.copernicus.eu/activations/EMSR517/", "note": "Separately imported agency assessment; not a model output."},
        "limitations": ["The exact failure time is unknown.", "Sensor-native GSD and exact UTC acquisition times are not established from the crop metadata.", "The review square is an annotation, not measured damage geometry.", "No automated detector ran; this assessment does not certify nearby routes or surviving structure safety."],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "generated_files": [{"name": p.name, "sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(OUT.iterdir()) if p.suffix in (".png", ".geojson")]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Published images at {OUT}; total PNG bytes: {sum(p.stat().st_size for p in OUT.glob('*.png')):,}")


if __name__ == "__main__":
    main()
