"""CUDA-only native first-place SpaceNet8 flood-attribution reproduction."""

import argparse
import csv
import hashlib
import html
import importlib
import json
import statistics
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from shapely import wkt
from shapely.ops import transform
import torch
import torch.nn.functional as F

CLASSES = ["background", "non-flooded building", "flooded building", "non-flooded road", "flooded/obstructed road"]
PALETTE = np.array([[30, 36, 43], [59, 178, 113], [240, 168, 55], [70, 143, 220], [244, 64, 82]], dtype=np.uint8)
MEAN = np.array([0.249566, 0.318912, 0.21801], dtype=np.float32)[:, None, None]
STD = np.array([0.12903, 0.11784, 0.10739], dtype=np.float32)[:, None, None]


def format_rate(value):
    return "undefined (no positive support/predictions)" if value is None else f"{100 * value:.2f}%"


def metrics(matrix):
    rows = []
    for i, name in enumerate(CLASSES):
        tp = int(matrix[i, i]); support = int(matrix[i].sum()); predicted = int(matrix[:, i].sum())
        rows.append({"class": name, "support_pixels": support, "predicted_pixels": predicted,
                     "precision": tp / predicted if predicted else None,
                     "recall": tp / support if support else None,
                     "f1": 2 * tp / (support + predicted) if support + predicted else None,
                     "iou": tp / (support + predicted - tp) if support + predicted - tp else None})
    return {"confusion_matrix_truth_rows": matrix.tolist(), "classes": rows}


def confusion(truth, prediction):
    known = truth < 5
    return np.bincount((5 * truth[known].astype(np.int64) + prediction[known]), minlength=25).reshape(5, 5)


def reference_mask(rows, profile):
    """Official human reference WKT, author 3m UTM road buffer and class order."""
    affine = profile["transform"]
    to_utm = Transformer.from_crs(profile["crs"], "EPSG:32632", always_xy=True).transform
    from_utm = Transformer.from_crs("EPSG:32632", profile["crs"], always_xy=True).transform
    buildings, roads, unknown = [], [], []
    for row in rows:
        if row["Object"] not in ("Road", "Building"):
            raise ValueError(f"Unrecognized official annotation object: {row['Object']}")
        geometry = wkt.loads(row["Wkt_Pix"])
        if geometry.is_empty:
            continue
        geometry = transform(lambda x, y, z=None: (affine.a * x + affine.b * y + affine.c,
                                                   affine.d * x + affine.e * y + affine.f), geometry)
        if row["Object"] == "Road":
            geometry = transform(from_utm, transform(to_utm, geometry).buffer(3, quad_segs=30))
        if row["Flooded"] not in ("True", "False"):
            unknown.append((geometry, 255)); continue
        category = (3 if row["Object"] == "Road" else 1) + (row["Flooded"] == "True")
        (roads if row["Object"] == "Road" else buildings).append((geometry, category))
    shape = (profile["height"], profile["width"])
    # Author converts separate road/building masks to four channels, then argmax;
    # building channels take priority over road channels at intersections.
    result = rasterize(roads + buildings + unknown, out_shape=shape, transform=affine, dtype="uint8") if roads + buildings + unknown else np.zeros(shape, dtype=np.uint8)
    return result


def load_pair(root, row):
    with rasterio.open(root / "PRE-event" / row["pre-event image"]) as pre:
        rgb = pre.read(); profile = pre.profile.copy(); valid = pre.dataset_mask() > 0
        if rgb.shape != (3, 1300, 1300) or pre.crs != rasterio.crs.CRS.from_epsg(4326):
            raise ValueError("Expected native 1300x1300 Germany RGB/WGS84 pre tile")
        with rasterio.open(root / "POST-event" / row["post-event image 1"]) as post:
            # Same tile IDs and nearly matching bounds are required, not assumed.
            discrepancy = np.abs(np.array(post.bounds) - np.array(pre.bounds)) / abs(pre.transform.a)
            if post.count != 3 or post.crs != pre.crs or discrepancy.max() > 2:
                raise ValueError("Post image has a different tile extent or CRS")
            aligned = np.zeros_like(rgb)
            for i in range(3):
                reproject(rasterio.band(post, i + 1), aligned[i], src_transform=post.transform,
                          src_crs=post.crs, dst_transform=pre.transform, dst_crs=pre.crs,
                          resampling=Resampling.bilinear)
            post_valid = np.zeros(pre.shape, dtype=np.uint8)
            reproject(post.dataset_mask(), post_valid, src_transform=post.transform, src_crs=post.crs,
                      dst_transform=pre.transform, dst_crs=pre.crs, resampling=Resampling.nearest)
            valid &= post_valid > 0
            grid = {"crs": str(pre.crs), "transform": list(pre.transform), "pre_bounds": list(pre.bounds),
                    "post_original_bounds": list(post.bounds), "post_original_shape": list(post.shape),
                    "max_extent_difference_in_pre_pixels": float(discrepancy.max()),
                    "working_grid": "post bilinear-warped to exact pre-event grid"}
    return rgb, aligned, valid, profile, grid


def write_raster(path, array, profile):
    settings = profile.copy()
    settings.update(count=1 if array.ndim == 2 else array.shape[0], dtype=str(array.dtype), compress="deflate")
    if array.ndim == 2:
        settings["nodata"] = 255
    with rasterio.open(path, "w", **settings) as output:
        output.write(array, 1) if array.ndim == 2 else output.write(array)


def overlay(rgb, classes, valid):
    image = np.transpose(rgb, (1, 2, 0)).copy()
    visible = (classes > 0) & (classes < 5) & valid
    image[visible] = (0.4 * image[visible] + 0.6 * PALETTE[classes[visible]]).astype(np.uint8)
    image[~valid | (classes == 255)] = [128, 128, 128]
    return image


def run(args):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; CPU inference fallback is forbidden")
    manifest = json.loads((args.data / "manifest.json").read_text())
    for receipt in manifest["files"]:
        if hashlib.sha256((args.data / receipt["path"]).read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError(f"Input/source checksum mismatch: {receipt['path']}")
    args.output.mkdir(parents=True, exist_ok=True)
    # Preserve the exact executed source when later changes only affect viewing.
    (args.output / "run-script.py").write_bytes(Path(__file__).read_bytes())
    (args.output / "input-manifest.json").write_bytes((args.data / "manifest.json").read_bytes())
    compatible = args.data / "source-compatible/models"
    compatible.mkdir(parents=True, exist_ok=True)
    original = (args.data / "source/models/seg_hrnet_ocr.py").read_text()
    # np.int was precisely the built-in int alias; replacing it preserves
    # channel-count arithmetic without downgrading the existing NumPy runtime.
    replacement = original.replace("np.int(", "int(")
    (compatible / "seg_hrnet_ocr.py").write_text(replacement)
    for filename in ("bn_helper.py", "config.py"):
        shutil.copyfile(args.data / "source/models" / filename, compatible / filename)
    sys.path.insert(0, str(compatible.parent.resolve()))
    module = importlib.import_module("models.seg_hrnet_ocr")
    # Legacy author saves a complete torch module, not just tensor weights.
    # Load only the official author URL retained in the manifest, on CPU first.
    checkpoint = torch.load(args.data / "best_flood.pt", map_location="cpu", weights_only=False)
    stored_model = checkpoint["model"].float()
    if type(stored_model) is not module.HighResolutionNet:
        raise TypeError(f"Unexpected checkpoint architecture: {type(stored_model)}")
    config_module = importlib.import_module("models.config")
    cfg = config_module.update_config(str(args.data / "source/models/seg_hrnet_ocr_w48_train_512x1024_sgd_lr1e-2_wd5e-4_bs_12_epoch484.yaml"))
    # Build the architecture fresh from native pinned source and config. The
    # ImageNet initialization is unnecessary because every key is strictly loaded.
    model = module.HighResolutionNet(cfg)
    model.load_state_dict(stored_model.state_dict(), strict=True)
    del stored_model
    model = model.to("cuda").eval()
    if not all(p.device.type == "cuda" for p in model.parameters()):
        raise RuntimeError("Model did not move completely to CUDA")
    references = list(csv.DictReader((args.data / "Germany_Training_Public_reference.csv").open()))
    pooled = np.zeros((5, 5), dtype=np.int64); per_tile = []; panels = []; times = []
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        for row in manifest["selection"]["rows"]:
            identifier = Path(row["label"]).stem
            rgb, post, valid, profile, grid = load_pair(args.data, row)
            tile_references = [r for r in references if r["ImageId"] == Path(row["pre-event image"]).stem]
            if not tile_references:
                raise ValueError(f"Missing human reference annotations for selected tile {identifier}")
            truth = reference_mask(tile_references, profile)
            truth[~valid] = 255
            inputs = [torch.from_numpy(((image.astype(np.float32) / 255 - MEAN) / STD)[None]).to("cuda") for image in (rgb, post)]
            torch.cuda.synchronize(); started = time.perf_counter()
            outputs = model(*inputs)
            logits = F.interpolate(outputs[5], size=rgb.shape[-2:], mode="bilinear", align_corners=False)
            probabilities = logits.softmax(1)
            prediction = probabilities.argmax(1)
            # Original val_best.py conservative attribution threshold, unchanged.
            for flooded, dry in ((2, 1), (4, 3)):
                prediction = torch.where((prediction == flooded) & (probabilities[:, flooded] < 0.9), dry, prediction)
            if logits.device.type != "cuda":
                raise RuntimeError("Output is not on CUDA")
            torch.cuda.synchronize(); elapsed = time.perf_counter() - started
            prediction = prediction[0].cpu().numpy().astype(np.uint8); prediction[~valid] = 255
            score = probabilities[0, 4].cpu().numpy().astype(np.float32)
            score[~valid] = np.nan
            matrix = confusion(truth, prediction); pooled += matrix; times.append(elapsed)
            per_tile.append({"id": identifier, "forward_seconds": elapsed, "unknown_pixels": int((truth == 255).sum()),
                             "grid": grid, "metrics": metrics(matrix)})
            write_raster(args.output / f"{identifier}-pre.tif", rgb, profile)
            write_raster(args.output / f"{identifier}-post.tif", post, profile)
            write_raster(args.output / f"{identifier}-truth.tif", truth, profile)
            write_raster(args.output / f"{identifier}-prediction.tif", prediction, profile)
            score_profile = profile.copy(); score_profile.update(dtype="float32", count=1, nodata=float("nan"), compress="deflate")
            with rasterio.open(args.output / f"{identifier}-road-score.tif", "w", **score_profile) as out:
                out.write(score, 1)
            for kind, array in (("pre", rgb.transpose(1, 2, 0)), ("post", post.transpose(1, 2, 0)),
                                ("truth", overlay(post, truth, valid)), ("prediction", overlay(post, prediction, valid))):
                Image.fromarray(array).save(args.output / f"{identifier}-{kind}.png")
            detail = per_tile[-1]["metrics"]["classes"][4]
            panels.append(f'<article id="tile-{html.escape(identifier)}"><h2>{html.escape(identifier)}</h2><p>Human obstructed-road pixels: {detail["support_pixels"]:,}; model: {detail["predicted_pixels"]:,}. Recall: {format_rate(detail["recall"])}; F1: {format_rate(detail["f1"])}.</p><div class="row">' + ''.join(
                f'<figure><a href="{identifier}-{kind}.png"><img src="{identifier}-{kind}.png" alt="{kind}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>'
                for kind, caption in (("pre", "Before: RGB satellite image"), ("post", "After: RGB satellite image"), ("truth", "Human vectors rasterized: road centerlines buffered3m"), ("prediction", "Model attribution on after image"))) + '</div></article>')
            print(f'{identifier}: {elapsed:.3f}s CUDA; obstructed road support {detail["support_pixels"]}, recall {detail["recall"]}', flush=True)
            del outputs, inputs, logits, probabilities
    report = {"experiment": "SpaceNet 8 first-place Germany same-event reproduction", "generated_at": datetime.now(timezone.utc).isoformat(),
              "selection": manifest["selection"], "device": torch.cuda.get_device_name(), "torch": torch.__version__, "cuda": torch.version.cuda,
              "checkpoint_epoch": checkpoint.get("epoch"), "checkpoint_date": str(checkpoint.get("date")),
              "execution": "single GPU FP32 batch1 full1300x1300, native author HRNet48+OCR, no TTA/tiling, author normalization and flood threshold0.9",
              "adaptation": "Native module loaded from official full-model checkpoint; fresh architecture strictly loads every key; no DDP wrapper. Only removed np.int alias replaced by built-in int. Bilinear post warp targets exact pre grid instead of author width/height-only warp; originals differ by <2 pre pixels.",
              "compatible_source_sha256": hashlib.sha256(replacement.encode()).hexdigest(),
              "labels": "Official reference.csv human vector labels rasterized; highway centerlines buffered3m each side in EPSG32632 (nominal6m corridor, not measured road-surface footprint), building priority at road overlaps; empty Null rows are absent objects, nonempty Null geometry unknown255",
              "road_buffer_meters_each_side": 3.0,
              "metrics": metrics(pooled), "per_tile": per_tile, "median_forward_seconds": statistics.median(times),
              "peak_allocated_cuda_gib": torch.cuda.max_memory_allocated() / 1024**3,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "input_manifest_sha256": hashlib.sha256((args.output / "input-manifest.json").read_bytes()).hexdigest(),
              "limitations": ["Germany training imagery, same2021event as Ahr: not independent test or transfer accuracy", "Six preselected tiles: sample reproduction, not full benchmark or instance/APLS score", "Flooded road means water-covered or rubble-obstructed; not structural collapse, engineering closure or passability", "Scores uncalibrated; clear-looking/zero class does not establish asset safety", "Exact acquisition times unavailable in retained CSV/TIFF metadata"]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    legend = ''.join(f'<span style="border-left:12px solid rgb({int(c[0])},{int(c[1])},{int(c[2])});padding-left:8px;margin-right:18px">{html.escape(name)}</span>' for name, c in zip(CLASSES[1:], PALETTE[1:]))
    (args.output / "index.html").write_text('<!doctype html><html><meta charset="utf-8"><title>SpaceNet8 reproduction</title><style>body{font:16px system-ui;background:#151b23;color:#e8eff5;margin:24px}a{color:#8cc9ff}.row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}figure{margin:0}img{width:100%}article{margin:40px 0}p{max-width:1100px;line-height:1.6}@media(max-width:1000px){.row{grid-template-columns:repeat(2,1fr)}}</style><h1>SpaceNet 8: before, after, human labels and model</h1><p>Six fixed seed42 Germany training tiles, selected before labels/results. These reproduce a model on the same flood event used in its dataset; they do not establish independent Ahr transfer accuracy. Click any image for its full1300px view. Roads marked red are water-covered or rubble-obstructed, not a structural-collapse grade. Human road references are vector centerlines rasterized with the author baseline 3 m buffer on each side, not manually drawn road-surface pixel masks. <a href="#tile-0_27_67">Jump to the positive flood tile</a>.</p><p>'+legend+'</p><p>Gray means missing/unknown pixels. Dark background is outside annotated road/building footprints, not a passability assessment. All positive/negative sample tiles are shown. <a href="report.json">Metrics and runtime report</a>; <a href="input-manifest.json">source receipts</a>. Dataset imagery/labels: SpaceNet/Maxar, CC BY-SA4.0; author code Apache-2.0.</p>' + ''.join(panels) + '</html>')
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file() and p.name != "checksums.json"}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "road": report["metrics"]["classes"][4], "peak_gib": report["peak_allocated_cuda_gib"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/research/spacenet8"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/damage-research/spacenet8"))
    run(parser.parse_args())
