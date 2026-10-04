"""Fetch small public GeoEye-1 windows for manual bridge review in Derna.

Run with the repository's existing damage-research environment:
    uv run --group damage-research python scripts/prepare_bridge_demo_derna.py
Outputs remain ignored under data/research/bridge-demo-other/.
"""

import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import httpx
import matplotlib.pyplot as plt
import rasterio
from matplotlib.patches import Circle
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds

OUT = Path(__file__).resolve().parents[1] / "data/research/bridge-demo-other"
BASE = "https://maxar-opendata.s3.amazonaws.com/events/Libya-Floods-Sept-2023/ard/34/120200213130/"
PAIRS = [
    ("before", "2023-07-01", "105005005ADE7C00"),
    ("after", "2023-09-13", "10500100363D0900"),
]
TARGETS = [
    ("derna_middle_bridge", "Derna middle Wadi crossing", 22.641427, 32.762475),
    ("derna_north_bridge", "Derna northern Wadi crossing", 22.643210, 32.764157),
]
REFERENCE = "https://unosat.org/static/unosat_filesystem/3672/UNOSAT_A3_Natural_Portrait_FL20230912LBY_DernaCity_ZoomInRiver_13Sep2023.pdf"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_window(client, target, phase, date, catalog_id, bounds):
    item_url = BASE + date + "/" + catalog_id + ".json"
    response = client.get(item_url)
    response.raise_for_status()
    item = response.json()
    item_path = OUT / (catalog_id + "_item.json")
    item_path.write_text(json.dumps(item, indent=2))
    url = urljoin(item_url, item["assets"]["visual"]["href"])
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    ):
        with rasterio.open(url) as src:
            window = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
            rgb = src.read([1, 2, 3], window=window)
            transform = src.window_transform(window)
            profile = src.profile.copy()
            profile.update(
                height=rgb.shape[1], width=rgb.shape[2], transform=transform,
                count=3, photometric="RGB", compress="deflate", tiled=True,
                blockxsize=256, blockysize=256,
            )
            tif = OUT / (target + "_" + phase + ".tif")
            with rasterio.open(tif, "w", **profile) as dst:
                dst.write(rgb)
    png = OUT / (target + "_" + phase + ".png")
    Image.fromarray(rgb.transpose(1, 2, 0)).save(png)
    info = {
        "png": str(png), "geotiff": str(tif),
        "item_id": item["id"], "item_url": item_url, "visual_cog_url": url,
        "acquired_at": item["properties"]["datetime"],
        "native_gsd_m": item["properties"]["gsd"],
        "visual_grid_m": profile["transform"].a,
        "platform": item["properties"]["platform"], "crs": "EPSG:32634",
        "transform": list(transform), "shape": list(rgb.shape),
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sha256": {path.name: sha256(path) for path in [png, tif, item_path]},
    }
    return rgb, info


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    to_xy = Transformer.from_crs(4326, 32634, always_xy=True)
    records = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for target, name, lon, lat in TARGETS:
            x, y = to_xy.transform(lon, lat)
            bounds = (x - 175, y - 175, x + 175, y + 175)
            record = {
                "id": target, "name": name, "coordinate": [lon, lat],
                "coordinate_crs": "EPSG:4326",
                "coordinate_method": "Approximate pre-event deck center from visual COG inspection; not surveyed",
                "bbox_epsg32634": bounds,
                "target_status": "manual satellite review plus UNOSAT preliminary destroyed-bridge assessment",
                "finding": "Pre-event road deck crosses Wadi; post-event corresponding deck absent, road continuity severed and river corridor scoured. Image interpretation is a demo annotation, not validated automated detection.",
                "manual_label": "destroyed bridge candidate", "images": {},
            }
            fig, axes = plt.subplots(1, 2, figsize=(14, 7))
            fig.subplots_adjust(left=.01, right=.99, bottom=.07, top=.88, wspace=.03)
            for ax, (phase, date, catalog_id) in zip(axes, PAIRS):
                rgb, info = fetch_window(client, target, phase, date, catalog_id, bounds)
                record["images"][phase] = info
                # Display using the actual rounded pixel-window transform.
                transform = rasterio.Affine(*info["transform"][:6])
                height, width = rgb.shape[1:]
                extent = (
                    transform.c, transform.c + width * transform.a,
                    transform.f + height * transform.e, transform.f,
                )
                ax.imshow(rgb.transpose(1, 2, 0), extent=extent)
                ax.add_patch(Circle((x, y), 50, edgecolor="#ffdd44", facecolor="none", linewidth=2))
                ax.set_title(f"{phase.title()} | {date} | GeoEye-1")
                ax.set_axis_off()
            fig.suptitle(name + " — manual comparison at known flood-damage site", fontsize=16)
            fig.text(.5, .02, "Yellow circle: approximate deck location | © Maxar 2023; CC BY-NC 4.0 | Manual review, no automated damage model", ha="center", fontsize=9)
            comparison = OUT / (target + "_comparison.png")
            fig.savefig(comparison, dpi=180)
            plt.close(fig)
            record["comparison_png"] = str(comparison)
            record["comparison_sha256"] = sha256(comparison)
            records.append(record)
    manifest = {
        "license": "CC-BY-NC-4.0", "attribution": "© Maxar 2023",
        "license_source": "https://maxar-opendata.s3.amazonaws.com/events/Libya-Floods-Sept-2023/collection.json",
        "source_event": "Libya-Floods-Sept-2023", "independent_reference": REFERENCE,
        "reference_caveat": "UNOSAT preliminary analysis, not field validated; three destroyed bridges in map extent.",
        "processing": "RGB visual COG clipped to 350 m square EPSG:32634; native visual RGB grid maintained; PNG channel transfer without color modification; side-by-side circle annotations",
        "targets": records,
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(manifest_path)


if __name__ == "__main__":
    main()
