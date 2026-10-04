"""CUDA-only diagnostic building damage inference on public paired Ahr orthophotos.

This experiment does not publish to the API or measure accuracy without labels.
"""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_bounds, transform_geom
from safetensors.torch import load_file
from shapely.geometry import shape
import torch


MODEL = "EVER-Z/torchange_example_changeos_swint_on_xview2_best42k"
REVISION = "4007dd10c5eaee67161e2d4a45a43da3ead6c722"
WEIGHT_BYTES = 166117752
WEIGHT_SHA256 = "81ae6386ceebe225ab6c072cb987b57312fdcfdb2a7f72ab9b30e5e8f1041cc4"
CLASSES = {0: "background", 1: "no-damage", 2: "minor-damage", 3: "major-damage", 4: "destroyed"}
PALETTE = np.array([[245, 245, 245], [70, 181, 121], [245, 215, 90], [239, 145, 70], [182, 70, 69]], dtype=np.uint8)
LIMITATIONS = [
    "Diagnostic inference only: no matched independent building labels and no accuracy measurement.",
    "Building pixel classes are model predictions, not confirmed structural damage or individual building instances.",
    "This building model does not assess roads, bridges, safe routes, or future collapse.",
    "Orthophotos differ from the VHR satellite imagery used for training.",
    "The 2019 baseline leaves a two-year interval with possible construction, demolition and seasonal changes.",
    "Late-July post-event imagery may include cleanup and changes after the July 18 agency assessment.",
    "Post-event mosaic dates are not an exact acquisition date for every pixel; preserve the source metadata distinctions.",
    "Alpha/nodata validity is not a complete occlusion, registration-error, or semantic reliability mask.",
    "Model scores are uncalibrated; the no-damage class does not establish safety or passability.",
    "Ahr event independence is conditional on the author's documented xBD-only training recipe; training has not been audited.",
]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path, max_bytes, expected_sha256=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    cached = path.exists()
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".download")
        for attempt in range(3):
            try:
                with httpx.stream("GET", url, timeout=90, follow_redirects=True) as response:
                    response.raise_for_status()
                    count = 0
                    with temporary.open("wb") as output:
                        for chunk in response.iter_bytes():
                            count += len(chunk)
                            if count > max_bytes:
                                raise ValueError("Download exceeded the pinned asset size budget")
                            output.write(chunk)
                if expected_sha256 and sha256(temporary) != expected_sha256:
                    raise ValueError("Downloaded checkpoint SHA256 does not match pinned host metadata")
                temporary.replace(path)
                break
            except (httpx.TransportError, httpx.HTTPStatusError):
                temporary.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
    size = path.stat().st_size
    checksum = sha256(path)
    if size > max_bytes or (expected_sha256 and checksum != expected_sha256):
        raise ValueError("Cached model asset failed size/checksum validation")
    checked_at = datetime.now(timezone.utc).isoformat()
    return {
        "url": url, "path": str(path), "bytes": size, "sha256": checksum,
        "verified_at": checked_at, "cache_verified": cached,
        "retrieved_at": None if cached else checked_at,
    }


def read_input(path):
    metadata_path = path.with_suffix(".json")
    provenance = json.loads(metadata_path.read_text())
    checksum = sha256(path)
    if checksum != provenance.get("sha256"):
        raise ValueError(f"Input SHA256 differs from provenance: {path}")
    with rasterio.open(path) as raster:
        if raster.count < 3 or not raster.crs or not raster.crs.is_projected:
            raise ValueError("Expected georeferenced projected RGB imagery")
        rgb = raster.read([1, 2, 3]).astype(np.float32)
        valid = (raster.read_masks([1, 2, 3]) > 0).all(axis=0)
        alpha_bands = [i + 1 for i, interpretation in enumerate(raster.colorinterp) if interpretation == rasterio.enums.ColorInterp.alpha]
        for band in alpha_bands:
            valid &= raster.read(band) > 0
        valid &= np.isfinite(rgb).all(axis=0)
        if valid.any() and (rgb[:, valid].min() < 0 or rgb[:, valid].max() > 255):
            raise ValueError("The author's RGB normalization expects values in [0,255]")
        rgb[:, ~valid] = 0
        grid = {"crs": raster.crs, "transform": raster.transform, "height": raster.height, "width": raster.width}
    return rgb, valid, grid, {
        "path": str(path), "sha256": checksum,
        "provenance_path": str(metadata_path), "provenance_sha256": sha256(metadata_path),
        "source": provenance,
    }


def assert_aligned(pre_grid, post_grid):
    if any(pre_grid[key] != post_grid[key] for key in ("crs", "width", "height")):
        raise ValueError("Pre/post imagery must have matching CRS and dimensions")
    mapping = ~pre_grid["transform"] @ post_grid["transform"]
    width, height = pre_grid["width"], pre_grid["height"]
    for point in ((0, 0), (width, 0), (0, height), (width, height)):
        if not np.allclose(mapping @ point, point, rtol=0, atol=1e-6):
            raise ValueError("Pre/post imagery grids are not aligned")
    if width % 32 or height % 32:
        raise ValueError("Use full input dimensions divisible by 32; this experiment does not resample/pad")


def export_raster(path, data, grid):
    count = 1 if data.ndim == 2 else data.shape[0]
    with rasterio.open(
        path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
        count=count, dtype=data.dtype, crs=grid["crs"], transform=grid["transform"],
        nodata=255 if data.dtype == np.uint8 else np.nan, compress="deflate",
    ) as output:
        output.write(data[None] if data.ndim == 2 else data)


def export_geojson(path, prediction, grid):
    features = []
    transform = grid["transform"]
    pixel_area = abs(transform.a * transform.e - transform.b * transform.d)
    if rasterio.crs.CRS.from_user_input(grid["crs"]).linear_units != "metre":
        raise ValueError("Prediction area export requires a metric projected CRS")
    for geometry, value in shapes(prediction, mask=(prediction > 0) & (prediction < 255), transform=transform):
        area = shape(geometry).area
        classification = int(value)
        features.append({
            "type": "Feature", "id": len(features) + 1,
            "geometry": transform_geom(grid["crs"], "EPSG:4326", geometry, precision=8),
            "properties": {
                "predicted_class": classification, "predicted_damage_grade": CLASSES[classification],
                "area_m2": round(area, 4), "pixel_count": round(area / pixel_area),
                "evidence_class": "modeled_building_damage", "structural_damage_confirmed": False,
                "geometry_meaning": "contiguous predicted pixels; not individual building instances",
                "model_id": MODEL, "model_revision": REVISION,
            },
        })
    collection = {"type": "FeatureCollection", "features": features, "limitations": LIMITATIONS}
    path.write_text(json.dumps(collection, indent=2) + "\n")
    return len(features)


def render(path, pre, post, prediction):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    pre_rgb = np.moveaxis(pre.astype(np.uint8), 0, -1)
    post_rgb = np.moveaxis(post.astype(np.uint8), 0, -1)
    colors = np.empty((*prediction.shape, 3), dtype=np.uint8)
    colors[:] = [130, 130, 130]
    for classification, color in enumerate(PALETTE):
        colors[prediction == classification] = color
    figure, axes = plt.subplots(1, 4, figsize=(18, 5.2))
    axes[0].imshow(pre_rgb)
    axes[1].imshow(post_rgb)
    axes[2].imshow(colors)
    axes[3].imshow(post_rgb)
    overlay = np.concatenate([colors, np.where((prediction >= 2) & (prediction <= 4), 170, 0)[..., None].astype(np.uint8)], axis=2)
    axes[3].imshow(overlay)
    for axis, title in zip(axes, ["Pre-event: 2019", "Post-event: late July 2021 mosaic", "Predicted building pixel classes", "Positive damage predictions over imagery"]):
        axis.set_title(title, fontsize=10)
        axis.axis("off")
    handles = [Patch(color=PALETTE[index] / 255, label=label) for index, label in CLASSES.items()]
    handles.append(Patch(color=[.51, .51, .51], label="unknown / invalid"))
    figure.legend(handles=handles, loc="lower center", ncol=6, fontsize=9)
    figure.suptitle("Ahr ChangeOS diagnostic — no independent accuracy measurement; building model, not bridge damage", fontsize=12)
    figure.subplots_adjust(left=.01, right=.99, top=.85, bottom=.13, wspace=.05)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(args):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment; there is no CPU fallback")
    args.output.mkdir(parents=True, exist_ok=True)
    pre, pre_valid, grid, pre_provenance = read_input(args.pre)
    post, post_valid, post_grid, post_provenance = read_input(args.post)
    assert_aligned(grid, post_grid)
    valid = pre_valid & post_valid
    if not valid.any():
        raise ValueError("No jointly valid imagery pixels")
    base = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/"
    config_path, weight_path = args.cache / "config.json", args.cache / "model.safetensors"
    config_asset = download(base + "config.json", config_path, 20000)
    weight_asset = download(base + "model.safetensors", weight_path, WEIGHT_BYTES, WEIGHT_SHA256)
    config = json.loads(config_path.read_text())["config"]
    config["encoder"]["params"]["weights"] = None

    import torchange  # Registers the author encoder implementations.
    from torchange.models.changeos import ChangeOS

    model = ChangeOS(config)
    incompatible = model.load_state_dict(load_file(str(weight_path), device="cpu"), strict=True)
    model = model.to("cuda").eval()
    mean = np.array([.485, .456, .406], dtype=np.float32)[:, None, None]
    std = np.array([.229, .224, .225], dtype=np.float32)[:, None, None]
    normalized = np.concatenate([(pre / 255 - mean) / std, (post / 255 - mean) / std], axis=0)
    images = torch.from_numpy(normalized[None]).to("cuda")
    if images.device.type != "cuda" or any(parameter.device.type != "cuda" for parameter in model.parameters()):
        raise RuntimeError("Model and input must both be on CUDA")
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with torch.inference_mode():
        output = model(images)
        footprint = output["t1_semantic_prediction"][:, 0]
        scores = output["change_prediction"]
        if footprint.device.type != "cuda" or scores.device.type != "cuda":
            raise RuntimeError("Model outputs must remain on CUDA")
        if scores.shape != (1, 5, grid["height"], grid["width"]) or footprint.shape != (1, grid["height"], grid["width"]):
            raise ValueError("Unexpected author output dimensions")
        if not torch.isfinite(scores).all().item() or not torch.isfinite(footprint).all().item():
            raise ValueError("Non-finite model output")
        prediction = torch.where(footprint > .5, scores.argmax(1), 0)[0]
    torch.cuda.synchronize()
    seconds = time.perf_counter() - started
    peak_bytes = torch.cuda.max_memory_allocated()
    prediction = prediction.cpu().numpy().astype(np.uint8)
    score_array = scores[0].cpu().numpy()
    footprint_array = footprint[0].cpu().numpy()
    prediction[~valid] = 255
    score_array[:, ~valid] = np.nan
    footprint_array[~valid] = np.nan
    localization_counts = int(np.count_nonzero(footprint_array[valid] > .5))
    localization_quantiles = np.percentile(footprint_array[valid], [0, 50, 95, 99, 100]).tolist()
    raw_damage_argmax = score_array[:, valid].argmax(0)

    export_raster(args.output / "predicted-damage.tif", prediction, grid)
    export_raster(args.output / "damage-scores.tif", score_array, grid)
    export_raster(args.output / "building-footprint-score.tif", footprint_array, grid)
    polygon_count = export_geojson(args.output / "predicted-damage.geojson", prediction, grid)
    render(args.output / "comparison.png", pre, post, prediction)
    transform = grid["transform"]
    pixel_area = abs(transform.a * transform.e - transform.b * transform.d)
    class_counts = {label: int(np.count_nonzero(prediction == index)) for index, label in CLASSES.items()}
    class_counts["unknown"] = int(np.count_nonzero(prediction == 255))
    versions = {package: importlib.metadata.version(package) for package in ["torch", "torchvision", "torchange", "ever-beta", "timm", "numpy", "rasterio", "safetensors"]}
    outputs = [
        {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(args.output.iterdir()) if path.name in {
            "predicted-damage.tif", "damage-scores.tif", "building-footprint-score.tif", "predicted-damage.geojson", "comparison.png",
        }
    ]
    native_bounds = rasterio.transform.array_bounds(grid["height"], grid["width"], transform)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "experiment": "ahr-2021-changeos-diagnostic",
        "script": {"path": str(Path(__file__)), "sha256": sha256(Path(__file__))},
        "accuracy_evaluated": False, "ground_truth": None, "limitations": LIMITATIONS,
        "model": {"id": MODEL, "revision": REVISION, "model_license": "Apache-2.0", "code_license": "Apache-2.0", "source_url": "https://github.com/Z-Zheng/pytorch-change-models", "weights": weight_asset, "config_asset": config_asset, "effective_config": config, "strict_loading": {"missing_keys": list(incompatible.missing_keys), "unexpected_keys": list(incompatible.unexpected_keys)}},
        "inputs": {"pre": pre_provenance, "post": post_provenance},
        "grid": {"crs": str(grid["crs"]), "height": grid["height"], "width": grid["width"], "transform": list(transform), "pixel_area_m2": pixel_area, "bbox_wgs84": transform_bounds(grid["crs"], "EPSG:4326", *native_bounds)},
        "processing": {"dtype": "float32", "batch_size": 1, "full_image": True, "test_time_augmentation": False, "rgb_mean": mean[:, 0, 0].tolist(), "rgb_std": std[:, 0, 0].tolist(), "rgb_divisor": 255, "channel_order": "pre-RGB, post-RGB", "localization_threshold": .5, "damage_operation": "five-class argmax constrained by predicted localization", "invalid_class": 255, "scores": "uncalibrated author softmax damage scores and sigmoid localization"},
        "cuda": {"device": torch.cuda.get_device_name(), "torch_cuda_runtime": torch.version.cuda, "forward_seconds_synchronized": seconds, "peak_allocated_bytes": peak_bytes, "model_input_output_cuda_asserted": True},
        "runtime_versions": {"python": platform.python_version(), **versions}, "pixel_counts": class_counts,
        "output_diagnostics": {
            "localization_pixels_above_threshold": localization_counts,
            "localization_score_quantiles": dict(zip(["min", "p50", "p95", "p99", "max"], localization_quantiles)),
            "ungated_damage_argmax_pixel_counts": {
                label: int(np.count_nonzero(raw_damage_argmax == index)) for index, label in CLASSES.items()
            },
        },
        "class_areas_m2": {label: count * pixel_area for label, count in class_counts.items()},
        "joint_valid_fraction": float(valid.mean()), "prediction_area_feature_count": polygon_count,
        "outputs": outputs,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output / "report.json"), "cuda": report["cuda"], "counts": class_counts, "valid_fraction": report["joint_valid_fraction"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre", type=Path, default=Path("data/research/ahr-altenahr-vhr-pre-2019.tif"))
    parser.add_argument("--post", type=Path, default=Path("data/research/ahr-altenahr-vhr-post.tif"))
    parser.add_argument("--cache", type=Path, default=Path("data/research/changeos") / REVISION)
    parser.add_argument("--output", type=Path, default=Path("artifacts/research/changeos-ahr-altenahr"))
    run(parser.parse_args())
