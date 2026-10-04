#!/usr/bin/env python3
"""Prepare and optionally benchmark the pinned LADI v2 road-damage model.

By default this command only downloads/verifies the model and a deterministic,
label-blind sample of public test images. Pass ``--run-inference`` explicitly
to run the benchmark on CUDA. All cached inputs and outputs live under the
ignored ``data/damage-research`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import random
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODEL_REPO = "MITLL/LADI-v2-classifier-small-reference"
MODEL_REVISION = "6ba5a0300601284bc6b69dddb46c8991a8ac196c"
DATASET_REPO = "MITLL/LADI-v2-dataset"
DATASET_REVISION = "5f2dbfe8c466d32edafd1bab847ec5252309acdb"
DATASET_CONFIG = "default"
DATASET_SPLIT = "test"
EXPECTED_TEST_ROWS = 1049
SAMPLE_SEED = 42
SAMPLE_SIZE = 100
LABELS = (
    "bridges_any",
    "buildings_any",
    "buildings_affected_or_greater",
    "buildings_minor_or_greater",
    "debris_any",
    "flooding_any",
    "flooding_structures",
    "roads_any",
    "roads_damage",
    "trees_any",
    "trees_damage",
    "water_any",
)
ROAD_DAMAGE_INDEX = 8
THRESHOLD = 0.5
PAGE_SIZE = 100  # Dataset Viewer API maximum.
IMAGE_WORKERS = 6
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def api_json(url: str, *, attempts: int = 5) -> dict[str, Any]:
    """GET JSON with bounded retries and no URL-bearing errors in diagnostics."""
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "FloodBeacon-LADI-research/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError("response was not a JSON object")
            return value
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            status = None
        if attempt + 1 == attempts:
            detail = f"HTTP {status}" if status is not None else "network or JSON error"
            raise RuntimeError(f"Hugging Face metadata request failed ({detail})")
        time.sleep(min(2**attempt, 16))
    raise AssertionError("unreachable")


def verify_hub_revision() -> None:
    """Require the named immutable dataset revision to remain publicly present."""
    revision_url = (
        "https://huggingface.co/api/datasets/"
        f"{DATASET_REPO}/revision/{DATASET_REVISION}"
    )
    revision = api_json(revision_url)
    if revision.get("sha") != DATASET_REVISION:
        raise RuntimeError("Hub did not resolve the pinned dataset revision")
    if revision.get("gated") or revision.get("private"):
        raise RuntimeError("Pinned LADI dataset revision is no longer public")


def fetch_all_test_metadata() -> tuple[list[dict[str, Any]], bool]:
    """Page through the complete test split; never use labels to select rows."""
    all_rows: list[dict[str, Any]] = []
    expected_total: int | None = None
    partial = False
    feature_names: tuple[str, ...] | None = None
    for offset in range(0, EXPECTED_TEST_ROWS, PAGE_SIZE):
        length = min(PAGE_SIZE, EXPECTED_TEST_ROWS - offset)
        params = urllib.parse.urlencode(
            {
                "dataset": DATASET_REPO,
                "config": DATASET_CONFIG,
                "split": DATASET_SPLIT,
                "offset": offset,
                "length": length,
                # The Dataset Viewer currently accepts but does not document
                # this parameter. Returned asset paths are checked below too.
                "revision": DATASET_REVISION,
            }
        )
        page = api_json(f"https://datasets-server.huggingface.co/rows?{params}")
        total = page.get("num_rows_total")
        if not isinstance(total, int) or total != EXPECTED_TEST_ROWS:
            raise RuntimeError(
                f"Expected {EXPECTED_TEST_ROWS} test rows; viewer reports {total!r}"
            )
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise RuntimeError("Test split size changed while paging metadata")

        names = tuple(feature.get("name", "") for feature in page.get("features", []))
        if feature_names is None:
            feature_names = names
            if set(LABELS) - set(feature_names):
                raise RuntimeError("Dataset Viewer response lacks expected LADI labels")
        elif names != feature_names:
            raise RuntimeError("Dataset feature schema changed while paging")

        page_rows = page.get("rows", [])
        wanted_indices = list(range(offset, offset + length))
        found_indices = [row.get("row_idx") for row in page_rows]
        if found_indices != wanted_indices:
            raise RuntimeError(f"Incomplete or out-of-order test metadata at offset {offset}")

        # Do not write the response to disk: image.src contains a temporary
        # signed URL. Keep it only in memory for the immediate image download.
        for item in page_rows:
            row = item.get("row", {})
            image = row.get("image", {})
            src = image.get("src")
            if not isinstance(src, str):
                raise RuntimeError(f"Test row {item['row_idx']} has no image URL")
            if f"/--/{DATASET_REVISION}/--/{DATASET_CONFIG}/{DATASET_SPLIT}/" not in urllib.parse.urlsplit(src).path:
                raise RuntimeError(
                    f"Test row {item['row_idx']} is not served from the pinned revision"
                )
            all_rows.append(
                {
                    "row_idx": item["row_idx"],
                    "row": row,
                    "temporary_src": src,
                }
            )
        partial = partial or bool(page.get("partial", False))
        print(f"Fetched test metadata {offset + len(page_rows)}/{EXPECTED_TEST_ROWS}")

    if len(all_rows) != EXPECTED_TEST_ROWS:
        raise RuntimeError("Did not retrieve every row in the pinned test split")
    return all_rows, partial


def select_rows_without_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose the fixed sample solely from row positions, before reading labels."""
    indices = sorted(random.Random(SAMPLE_SEED).sample(range(len(rows)), SAMPLE_SIZE))
    return [rows[index] for index in indices]


def download_image(item: dict[str, Any], image_dir: Path) -> dict[str, Any]:
    row_idx = int(item["row_idx"])
    image_dir.mkdir(parents=True, exist_ok=True)
    destination = image_dir / f"{row_idx:04d}.jpg"
    if destination.exists() and destination.stat().st_size > 0:
        return {"row_idx": row_idx, "path": destination, "sha256": sha256_file(destination)}

    request = urllib.request.Request(
        item["temporary_src"],
        headers={"User-Agent": "FloodBeacon-LADI-research/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            image_bytes = response.read(MAX_IMAGE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        status = getattr(error, "code", None)
        detail = f"HTTP {status}" if status is not None else type(error).__name__
        raise RuntimeError(f"Image download failed for test row {row_idx} ({detail})") from None
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"Test row {row_idx} image exceeds the 10 MiB safety bound")
    if not image_bytes.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"Test row {row_idx} did not return a JPEG image")
    verify_image_bytes(image_bytes, item["row"], row_idx)
    temporary = destination.with_suffix(f".jpg.{os.getpid()}.tmp")
    temporary.write_bytes(image_bytes)
    temporary.replace(destination)
    return {"row_idx": row_idx, "path": destination, "sha256": sha256_bytes(image_bytes)}


def verify_image_bytes(image_bytes: bytes, row: dict[str, Any], row_idx: int) -> None:
    from PIL import Image

    try:
        with Image.open(BytesIO(image_bytes)) as decoded:
            decoded.verify()
        with Image.open(BytesIO(image_bytes)) as decoded:
            expected_size = (int(row["image"]["width"]), int(row["image"]["height"]))
            if decoded.format != "JPEG" or decoded.size != expected_size:
                raise RuntimeError(
                    f"Test row {row_idx} image does not match metadata dimensions/format"
                )
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Test row {row_idx} image failed JPEG/dimension validation") from error


def verify_image_file(path: Path, row: dict[str, Any], row_idx: int) -> None:
    verify_image_bytes(path.read_bytes(), row, row_idx)


def prepare_model(model_dir: Path, *, download: bool = True) -> dict[str, Any]:
    try:
        from huggingface_hub import snapshot_download
        from transformers import AutoConfig, AutoImageProcessor
    except ImportError as error:
        raise RuntimeError(
            "Install the repository's damage-research dependency group before preparing LADI"
        ) from error

    model_dir.mkdir(parents=True, exist_ok=True)
    if download:
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_REVISION,
            local_dir=str(model_dir),
            token=False,
        )
    config = AutoConfig.from_pretrained(model_dir, local_files_only=True)
    processor = AutoImageProcessor.from_pretrained(model_dir, local_files_only=True)
    id2label = {int(index): label for index, label in config.id2label.items()}
    expected_order = dict(enumerate(LABELS))
    if id2label != expected_order:
        raise RuntimeError(f"Unexpected model output order: {id2label}")
    if config.problem_type != "multi_label_classification":
        raise RuntimeError("LADI checkpoint does not declare multi-label classification")
    if config.architectures != ["BitForImageClassification"]:
        raise RuntimeError(f"Unexpected LADI architecture: {config.architectures}")
    if tuple(processor.image_mean) != (0.5, 0.5, 0.5) or tuple(processor.image_std) != (
        0.5,
        0.5,
        0.5,
    ):
        raise RuntimeError("Unexpected LADI image normalization values")
    if processor.size.shortest_edge != 448:
        raise RuntimeError("Unexpected LADI image resize recipe")
    if (processor.crop_size.height, processor.crop_size.width) != (448, 448):
        raise RuntimeError("Unexpected LADI center-crop recipe")
    weights_path = model_dir / "model.safetensors"
    if not weights_path.is_file():
        raise RuntimeError("Pinned LADI checkpoint file is missing")
    return {
        "repo": MODEL_REPO,
        "revision": MODEL_REVISION,
        "architecture": config.architectures[0],
        "problem_type": config.problem_type,
        "training_scope": "Author reference model card: trained on train split only (2015-2022); excludes validation and 2023 test split.",
        "labels": list(LABELS),
        "roads_damage_index": ROAD_DAMAGE_INDEX,
        "preprocessing": {
            "convert_rgb": bool(processor.do_convert_rgb),
            "resize_shortest_edge": processor.size.shortest_edge,
            "center_crop": {
                "height": processor.crop_size.height,
                "width": processor.crop_size.width,
            },
            "rescale_factor": processor.rescale_factor,
            "mean": processor.image_mean,
            "std": processor.image_std,
        },
        "weights_file": weights_path.name,
        "weights_bytes": weights_path.stat().st_size,
        "weights_sha256": sha256_file(weights_path),
    }


def make_manifest_rows(
    selected: list[dict[str, Any]], downloaded: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    samples = []
    for item in selected:
        row_idx = int(item["row_idx"])
        row = item["row"]
        image = downloaded[row_idx]
        truth: dict[str, bool] = {}
        for label in LABELS:
            value = row.get(label)
            if not isinstance(value, bool):
                raise RuntimeError(f"Test row {row_idx} has invalid label {label!r}")
            truth[label] = value
        samples.append(
            {
                "row_idx": row_idx,
                "image_path": f"images/{Path(image['path']).name}",
                "image_sha256": image["sha256"],
                "width": int(row["image"]["width"]),
                "height": int(row["image"]["height"]),
                "ground_truth": truth,
            }
        )
    return samples


def prepare(root: Path) -> tuple[Path, dict[str, Any]]:
    verify_hub_revision()
    model_dir = root / "model"
    model_info = prepare_model(model_dir)
    rows, viewer_partial = fetch_all_test_metadata()

    # The sampling step reads only the row positions. Labels are extracted after
    # the 100 row indices have been fixed.
    selected = select_rows_without_labels(rows)
    selected_ids = [int(item["row_idx"]) for item in selected]
    print(f"Fixed seed {SAMPLE_SEED} selected {len(selected_ids)} test rows without label filtering")

    sample_dir = root / (
        f"test-seed-{SAMPLE_SEED}-n{SAMPLE_SIZE}-{DATASET_REVISION[:12]}"
    )
    image_dir = sample_dir / "images"
    previous_manifest_path = sample_dir / "manifest.json"
    previous_hashes: dict[int, str] = {}
    if previous_manifest_path.is_file():
        try:
            previous = json.loads(previous_manifest_path.read_text())
            if (
                previous.get("dataset", {}).get("revision") == DATASET_REVISION
                and previous.get("sample", {}).get("seed") == SAMPLE_SEED
                and previous.get("sample", {}).get("row_indices") == selected_ids
            ):
                previous_hashes = {
                    int(sample["row_idx"]): sample["image_sha256"]
                    for sample in previous.get("samples", [])
                }
        except (OSError, ValueError, KeyError, TypeError):
            previous_hashes = {}

    to_download = []
    for item in selected:
        row_idx = int(item["row_idx"])
        image_path = image_dir / f"{row_idx:04d}.jpg"
        old_hash = previous_hashes.get(row_idx)
        if image_path.is_file() and old_hash and sha256_file(image_path) == old_hash:
            verify_image_file(image_path, item["row"], row_idx)
            continue
        to_download.append(item)

    downloaded: dict[int, dict[str, Any]] = {}
    for item in selected:
        row_idx = int(item["row_idx"])
        image_path = image_dir / f"{row_idx:04d}.jpg"
        old_hash = previous_hashes.get(row_idx)
        if image_path.is_file() and old_hash and sha256_file(image_path) == old_hash:
            verify_image_file(image_path, item["row"], row_idx)
            downloaded[row_idx] = {
                "row_idx": row_idx,
                "path": image_path,
                "sha256": old_hash,
            }

    if to_download:
        with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as pool:
            futures = {
                pool.submit(download_image, item, image_dir): int(item["row_idx"])
                for item in to_download
            }
            complete = 0
            for future in as_completed(futures):
                result = future.result()
                downloaded[result["row_idx"]] = result
                complete += 1
                if complete % 10 == 0 or complete == len(to_download):
                    print(f"Cached public test images {complete}/{len(to_download)}")

    samples = make_manifest_rows(selected, downloaded)
    manifest = {
        "prepared_at_utc": utc_now(),
        "dataset": {
            "repo": DATASET_REPO,
            "revision": DATASET_REVISION,
            "config": DATASET_CONFIG,
            "split": DATASET_SPLIT,
            "test_rows": EXPECTED_TEST_ROWS,
            "paper_reported_test_rows": 1041,
            "viewer_reported_test_rows": EXPECTED_TEST_ROWS,
            "paper_viewer_row_count_discrepancy": "The paper reports 1,041 test examples; the pinned Hub Dataset Viewer reports 1,049. The cause is unresolved; this run uses every row exposed by the pinned viewer revision and records its row indices.",
            "test_period": "2023 disaster declarations per author paper; disjoint from reference model training years 2015-2022.",
            "metadata_api_partial_flag": viewer_partial,
            "image_terms": "Hugging Face dataset card: CC BY 4.0; retain source attribution.",
            "metadata_api": "https://datasets-server.huggingface.co/rows",
        },
        "model": model_info,
        "sample": {
            "seed": SAMPLE_SEED,
            "selection": "Python random.Random(seed).sample(range(test_rows), sample_size), sorted by row index; no labels used in selection.",
            "size": SAMPLE_SIZE,
            "row_indices": selected_ids,
            "threshold": THRESHOLD,
            "threshold_note": "Predeclared 0.5 sigmoid cutoff; no calibration on this test sample.",
        },
        "images": {
            "width_height_from_dataset_metadata": "1800x1200 when supplied; per-row values recorded below.",
            "sha256": "Computed over exact cached JPEG bytes.",
            "temporary_signed_image_urls_persisted": False,
        },
        "samples": samples,
        "inference": {
            "completed": False,
            "note": "Preparation only. Run with --run-inference when the GPU slot is available.",
        },
    }
    sample_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(previous_manifest_path, manifest)
    return sample_dir, manifest


def load_prepared_cache(root: Path) -> tuple[Path, dict[str, Any]]:
    """Validate an existing pinned experiment without re-fetching Viewer rows."""
    sample_dir = root / f"test-seed-{SAMPLE_SEED}-n{SAMPLE_SIZE}-{DATASET_REVISION[:12]}"
    manifest_path = sample_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "No valid prepared LADI cache found; run without --run-inference to prepare it"
        ) from error

    dataset = manifest.get("dataset", {})
    sample = manifest.get("sample", {})
    expected_rows = sorted(
        random.Random(SAMPLE_SEED).sample(range(EXPECTED_TEST_ROWS), SAMPLE_SIZE)
    )
    if (
        dataset.get("repo") != DATASET_REPO
        or dataset.get("revision") != DATASET_REVISION
        or dataset.get("config") != DATASET_CONFIG
        or dataset.get("split") != DATASET_SPLIT
        or dataset.get("test_rows") != EXPECTED_TEST_ROWS
        or dataset.get("paper_reported_test_rows") != 1041
        or manifest.get("images", {}).get("temporary_signed_image_urls_persisted") is not False
        or sample.get("seed") != SAMPLE_SEED
        or sample.get("size") != SAMPLE_SIZE
        or sample.get("row_indices") != expected_rows
    ):
        raise RuntimeError("Prepared cache manifest does not match the pinned LADI experiment")

    model_info = json.loads(json.dumps(prepare_model(root / "model", download=False)))
    recorded_model = manifest.get("model", {})
    for key in (
        "repo",
        "revision",
        "architecture",
        "problem_type",
        "labels",
        "roads_damage_index",
        "weights_bytes",
        "weights_sha256",
        "preprocessing",
    ):
        if recorded_model.get(key) != model_info.get(key):
            raise RuntimeError(f"Cached manifest model field {key!r} failed verification")
    if recorded_model.get("revision") != MODEL_REVISION:
        raise RuntimeError("Prepared cache checkpoint revision is not the pinned revision")

    samples = manifest.get("samples")
    if not isinstance(samples, list) or [item.get("row_idx") for item in samples] != expected_rows:
        raise RuntimeError("Prepared cache sample records are incomplete or out of order")
    from PIL import Image

    for item in samples:
        truth = item.get("ground_truth", {})
        if set(truth) != set(LABELS) or any(not isinstance(truth[label], bool) for label in LABELS):
            raise RuntimeError(f"Cached labels are malformed for row {item.get('row_idx')}")
        relative = Path(item.get("image_path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Cached image path escaped the experiment directory")
        image_path = sample_dir / relative
        if not image_path.is_file() or image_path.stat().st_size > MAX_IMAGE_BYTES:
            raise RuntimeError(f"Cached image is missing or exceeds size bound: {relative}")
        if sha256_file(image_path) != item.get("image_sha256"):
            raise RuntimeError(f"Cached image checksum mismatch for row {item.get('row_idx')}")
        with Image.open(image_path) as image:
            if image.format != "JPEG" or list(image.size) != [item["width"], item["height"]]:
                raise RuntimeError(f"Cached image metadata mismatch for row {item.get('row_idx')}")
    print("Reused prepared cache after pinned manifest, model, labels, and image SHA checks")
    return sample_dir, manifest


def confusion_metrics(
    truths: list[bool], predictions: list[bool]
) -> dict[str, float | int | None]:
    tp = sum(actual and predicted for actual, predicted in zip(truths, predictions))
    fp = sum((not actual) and predicted for actual, predicted in zip(truths, predictions))
    fn = sum(actual and (not predicted) for actual, predicted in zip(truths, predictions))
    tn = sum((not actual) and (not predicted) for actual, predicted in zip(truths, predictions))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1_denominator = 2 * tp + fp + fn
    f1 = 2 * tp / f1_denominator if f1_denominator else None
    return {
        "support_positive": tp + fn,
        "support_negative": tn + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / len(truths) if truths else math.nan,
    }


def run_inference(sample_dir: Path, manifest: dict[str, Any], batch_size: int) -> None:
    import torch
    from PIL import Image, ImageDraw, ImageFont
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; CPU fallback is disabled for this benchmark")
    device = torch.device("cuda", torch.cuda.current_device())
    model_dir = sample_dir.parent / "model"
    processor = AutoImageProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForImageClassification.from_pretrained(
        model_dir,
        local_files_only=True,
        use_safetensors=True,
    )
    id2label = {int(index): label for index, label in model.config.id2label.items()}
    if id2label != dict(enumerate(LABELS)) or LABELS[ROAD_DAMAGE_INDEX] != "roads_damage":
        raise RuntimeError("Model output order changed; refusing to score labels incorrectly")
    model.eval()
    model.to(device)
    parameter_devices = {str(parameter.device) for parameter in model.parameters()}
    if parameter_devices != {str(device)}:
        raise RuntimeError(f"Model parameters are not all on CUDA: {parameter_devices}")
    model_parameter_count = sum(parameter.numel() for parameter in model.parameters())
    torch.cuda.reset_peak_memory_stats(device)
    torch.cuda.synchronize(device)

    samples = manifest["samples"]
    outputs: list[dict[str, Any]] = []
    forward_seconds: list[float] = []
    input_tensor_device: str | None = None
    logits_device: str | None = None
    for offset in range(0, len(samples), batch_size):
        chunk = samples[offset : offset + batch_size]
        images = []
        for sample in chunk:
            image_path = sample_dir / sample["image_path"]
            if sha256_file(image_path) != sample["image_sha256"]:
                raise RuntimeError(f"Cached image checksum mismatch for row {sample['row_idx']}")
            with Image.open(image_path) as image:
                images.append(image.convert("RGB"))
        tensors = processor(images=images, return_tensors="pt")["pixel_values"].to(device)
        if tensors.device != device:
            raise RuntimeError(f"Input tensors are on {tensors.device}, expected {device}")
        input_tensor_device = str(tensors.device)
        torch.cuda.synchronize(device)
        forward_start = time.perf_counter()
        with torch.inference_mode():
            logits = model(pixel_values=tensors).logits
            torch.cuda.synchronize(device)
            forward_seconds.append(time.perf_counter() - forward_start)
            if logits.device != device:
                raise RuntimeError(f"Model logits are on {logits.device}, expected {device}")
            logits_device = str(logits.device)
            probabilities = torch.sigmoid(logits).cpu().tolist()
        for sample, class_scores in zip(chunk, probabilities):
            scores = {label: float(class_scores[index]) for index, label in enumerate(LABELS)}
            predicted = {label: scores[label] >= THRESHOLD for label in LABELS}
            outputs.append(
                {
                    "row_idx": sample["row_idx"],
                    "image_path": sample["image_path"],
                    "image_sha256": sample["image_sha256"],
                    "ground_truth": sample["ground_truth"],
                    "scores": scores,
                    "predicted": predicted,
                }
            )
        print(f"CUDA inference {min(offset + len(chunk), len(samples))}/{len(samples)}")

    metrics = {
        label: confusion_metrics(
            [item["ground_truth"][label] for item in outputs],
            [item["predicted"][label] for item in outputs],
        )
        for label in LABELS
    }
    torch.cuda.synchronize(device)
    total_forward_seconds = sum(forward_seconds)
    benchmark = {
        "completed_at_utc": utc_now(),
        "device": {
            "name": torch.cuda.get_device_name(device),
            "index": torch.cuda.current_device(),
            "total_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
            "model_parameter_count": model_parameter_count,
            "model_parameter_devices": sorted(parameter_devices),
            "input_tensor_device": input_tensor_device,
            "logits_device": logits_device,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
        },
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "transformers_version": __import__("transformers").__version__,
        "forward_timing": {
            "synchronized_per_batch_seconds": forward_seconds,
            "total_seconds": total_forward_seconds,
            "images_per_second": len(samples) / total_forward_seconds
            if total_forward_seconds
            else None,
        },
        "sample_seed": SAMPLE_SEED,
        "sample_size": SAMPLE_SIZE,
        "threshold": THRESHOLD,
        "score_transform": "sigmoid independently over each multi-label logit; no softmax",
        "metrics_by_label": metrics,
        "sample_note": "Metrics describe this fixed 100-row random slice only; positive support is reported for every class.",
        "undefined_metric_note": "Precision is null when TP+FP is zero; recall is null when TP+FN is zero; F1 is null only when 2*TP+FP+FN is zero.",
    }
    atomic_write_json(sample_dir / "predictions.json", outputs)
    atomic_write_json(sample_dir / "metrics.json", benchmark)
    create_contact_sheet(sample_dir, outputs)

    manifest["inference"] = {
        "completed": True,
        "completed_at_utc": benchmark["completed_at_utc"],
        "device": benchmark["device"],
        "batch_size": batch_size,
        "threshold": THRESHOLD,
        "score_transform": benchmark["score_transform"],
        "metrics_file": "metrics.json",
        "predictions_file": "predictions.json",
        "contact_sheet_file": "contact-sheet-all-100.png",
    }
    atomic_write_json(sample_dir / "manifest.json", manifest)


def validate_completed_outputs(
    sample_dir: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify cached prediction records and recomputed metrics before rendering."""
    if not manifest.get("inference", {}).get("completed"):
        raise RuntimeError("No completed inference is cached; run --run-inference first")
    try:
        metrics = json.loads((sample_dir / "metrics.json").read_text())
        predictions = json.loads((sample_dir / "predictions.json").read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Cached inference outputs are missing or invalid JSON") from error

    samples = manifest.get("samples", [])
    if not isinstance(predictions, list) or len(predictions) != len(samples):
        raise RuntimeError("Cached predictions do not cover the prepared sample")
    for expected, actual in zip(samples, predictions):
        if (
            actual.get("row_idx") != expected.get("row_idx")
            or actual.get("image_path") != expected.get("image_path")
            or actual.get("image_sha256") != expected.get("image_sha256")
            or actual.get("ground_truth") != expected.get("ground_truth")
            or set(actual.get("scores", {})) != set(LABELS)
            or set(actual.get("predicted", {})) != set(LABELS)
        ):
            raise RuntimeError(f"Cached predictions disagree with sample row {expected.get('row_idx')}")
        for label in LABELS:
            score = actual["scores"][label]
            if not isinstance(score, (int, float)) or not 0 <= score <= 1:
                raise RuntimeError(f"Invalid cached probability for {label} in row {actual['row_idx']}")
            if actual["predicted"][label] != (score >= THRESHOLD):
                raise RuntimeError(f"Cached threshold decision mismatch for {label} in row {actual['row_idx']}")

    recomputed = {
        label: confusion_metrics(
            [item["ground_truth"][label] for item in predictions],
            [item["predicted"][label] for item in predictions],
        )
        for label in LABELS
    }
    if metrics.get("metrics_by_label") != recomputed:
        raise RuntimeError("Cached aggregate metrics do not match per-image predictions")
    if metrics.get("threshold") != THRESHOLD or metrics.get("sample_size") != len(samples):
        raise RuntimeError("Cached aggregate metrics do not match the pinned benchmark settings")
    metrics["undefined_metric_note"] = (
        "Precision is null when TP+FP is zero; recall is null when TP+FN is zero; "
        "F1 is null only when 2*TP+FP+FN is zero."
    )
    atomic_write_json(sample_dir / "metrics.json", metrics)
    return metrics, predictions


def publish_local_gallery(sample_dir: Path, artifact_dir: Path) -> None:
    """Copy verified local results into an attributed, self-contained HTML gallery."""
    manifest = json.loads((sample_dir / "manifest.json").read_text())
    metrics, predictions = validate_completed_outputs(sample_dir, manifest)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    image_dir = artifact_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for item in predictions:
        source = sample_dir / item["image_path"]
        destination = image_dir / Path(item["image_path"]).name
        if sha256_file(source) != item["image_sha256"]:
            raise RuntimeError(f"Source image checksum mismatch for row {item['row_idx']}")
        shutil.copyfile(source, destination)
    for name in ("metrics.json", "predictions.json", "manifest.json", "contact-sheet-all-100.png"):
        shutil.copyfile(sample_dir / name, artifact_dir / name)

    road = metrics["metrics_by_label"]["roads_damage"]
    metric_rows = "".join(
        f"<tr><th>{html.escape(str(name))}</th><td>{value if value is not None else 'null'}</td></tr>"
        for name, value in (
            ("positive support", road["support_positive"]),
            ("negative support", road["support_negative"]),
            ("TP", road["tp"]),
            ("FP", road["fp"]),
            ("FN", road["fn"]),
            ("TN", road["tn"]),
            ("precision", road["precision"]),
            ("recall", road["recall"]),
            ("F1", road["f1"]),
            ("accuracy", road["accuracy"]),
            ("threshold", metrics["threshold"]),
        )
    )
    cards = []
    for order, item in enumerate(predictions, start=1):
        row = item["row_idx"]
        truth = bool(item["ground_truth"]["roads_damage"])
        predicted = bool(item["predicted"]["roads_damage"])
        status = "TP" if truth and predicted else "FN" if truth else "FP" if predicted else "TN"
        score = item["scores"]["roads_damage"]
        filename = Path(item["image_path"]).name
        cards.append(
            f'<article class="sample {status.lower()}"><a href="images/{filename}">'
            f'<img loading="lazy" src="images/{filename}" alt="LADI test image, row {row}"></a>'
            f'<div><b>#{order:03d} · row {row}</b><span class="status">{status}</span><br>'
            f'roads_damage: truth={str(truth).lower()}, prediction={str(predicted).lower()}<br>'
            f'sigmoid={score:.4f}</div></article>'
        )
    device = metrics["device"]
    model = manifest["model"]
    dataset = manifest["dataset"]
    forward = metrics["forward_timing"]["total_seconds"]
    total_memory = device["total_memory_bytes"] / (1024**3)
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FloodBeacon LADI v2 road-damage mini-benchmark</title>
<style>body{{font:16px/1.45 system-ui,sans-serif;max-width:1440px;margin:2rem auto;padding:0 1rem;color:#18202a}}h1{{line-height:1.2}}.notice{{background:#fff8dc;padding:1rem;border-left:4px solid #d6a500}}.metrics{{border-collapse:collapse}}.metrics td,.metrics th{{padding:.3rem .7rem;border:1px solid #d5d9df;text-align:left}}.gallery{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}}.sample{{border:1px solid #ccd2da;padding:8px;border-radius:6px}}.sample img{{width:100%;height:150px;object-fit:contain;background:#f2f4f6}}.status{{float:right;font-weight:700}}.tp{{border-color:#268044}}.fn,.fp{{border-color:#b62e2e}}.links a{{margin-right:1rem}}</style></head>
<body><h1>LADI v2 road-damage mini-benchmark</h1>
<p class="notice"><b>Exploratory only:</b> fixed seed-{metrics['sample_seed']} random sample of {metrics['sample_size']} from the pinned public test split, selected without label inspection. Only {road['support_positive']} rows carry a positive <code>roads_damage</code> label. This is not a performance estimate or FloodBeacon case validation. The classifier emits image-level tags, not road locations, washout geometry, closures, or bridge-collapse status.</p>
<h2>Road damage results</h2><table class="metrics">{metric_rows}</table>
<p>GPU: {html.escape(device['name'])} (batch {manifest['inference']['batch_size']}, {total_memory:.1f} GiB total VRAM); synchronized forward total {forward:.3f} s across {metrics['sample_size']} images; peak CUDA allocation {device['peak_allocated_bytes']/1024**2:.1f} MiB. Model weights SHA-256 <code>{model['weights_sha256']}</code>.</p>
<h2>All {len(predictions)} test images</h2><p>Cards follow sorted dataset row index; TP/FP/FN/TN indicate only the image-level <code>roads_damage</code> binary decision. Scores are independent sigmoid outputs. <span class="links"><a href="contact-sheet-all-100.png">Contact sheet</a><a href="metrics.json">Metrics JSON</a><a href="predictions.json">Per-image predictions JSON</a></span></p>
<div class="gallery">{''.join(cards)}</div>
<h2>Dataset and model attribution</h2><p>Images and human labels are from <a href="https://huggingface.co/datasets/{dataset['repo']}">MIT Lincoln Laboratory's LADI v2 dataset</a>; the Hugging Face dataset card declares CC BY 4.0. Retain attribution to the LADI v2 dataset and CAP imagery/label provenance; consult the card for its full license and distribution statement. The checkpoint is the <a href="https://huggingface.co/{model['repo']}">MITLL LADI v2 small reference model</a> (MIT license), pinned at <code>{model['revision']}</code>. Dataset revision: <code>{dataset['revision']}</code>; sample: seed {metrics['sample_seed']}, {len(predictions)} of {dataset['test_rows']} Viewer rows. The paper reports 1,041 test examples; the pinned Viewer reports {dataset['test_rows']} and the discrepancy is unresolved.</p>
<p>Preprocessing uses the pinned model's AutoImageProcessor configuration. Inference used sigmoid per label (no softmax), threshold {metrics['threshold']}, CUDA batch size {manifest['inference']['batch_size']}. Source model trained only on the 2015–22 training split; test declarations are from 2023, but this sample remains geographically and sensor-domain shifted from Ahr/BC satellite/orthophoto imagery.</p>
<small>Locally generated artifact. Source JPEGs are copied unchanged from the ignored research cache; no signed URLs, external image hosts, or remote publication are used.</small></body></html>'''
    (artifact_dir / "index.html").write_text(document)
    print(f"Published local all-image gallery: {artifact_dir / 'index.html'}")


def create_contact_sheet(sample_dir: Path, outputs: list[dict[str, Any]]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    columns = 10
    tile_width = 180
    image_height = 120
    caption_height = 46
    rows = (len(outputs) + columns - 1) // columns
    canvas = Image.new(
        "RGB",
        (columns * tile_width, rows * (image_height + caption_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for order, output in enumerate(outputs):
        row = order // columns
        column = order % columns
        x = column * tile_width
        y = row * (image_height + caption_height)
        image_path = sample_dir / output["image_path"]
        with Image.open(image_path) as opened:
            thumbnail = opened.convert("RGB")
            thumbnail.thumbnail((tile_width, image_height))
            canvas.paste(thumbnail, (x, y))
        actual = int(output["ground_truth"]["roads_damage"])
        predicted = int(output["predicted"]["roads_damage"])
        score = output["scores"]["roads_damage"]
        status = "TP" if actual and predicted else "FP" if predicted else "FN" if actual else "TN"
        draw.text(
            (x + 2, y + image_height + 2),
            f"order={order:02d} row={output['row_idx']} road={status}",
            fill="black",
            font=font,
        )
        draw.text(
            (x + 2, y + image_height + 20),
            f"truth={actual} pred={predicted} score={score:.3f}",
            fill="black",
            font=font,
        )
    canvas.save(sample_dir / "contact-sheet-all-100.png", optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/damage-research/ladi"),
        help="Ignored cache/output directory (default: data/damage-research/ladi)",
    )
    parser.add_argument(
        "--run-inference",
        action="store_true",
        help="Run the prepared benchmark on CUDA; preparation alone never runs inference.",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Revalidate cached benchmark outputs and regenerate the local gallery without inference.",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if args.run_inference and args.render_only:
        raise SystemExit("--run-inference and --render-only cannot be combined")
    sample_dir, manifest = (
        load_prepared_cache(args.data_dir)
        if args.run_inference or args.render_only
        else prepare(args.data_dir)
    )
    print(f"LADI benchmark ready: {sample_dir}")
    print(f"Model checkpoint SHA-256: {manifest['model']['weights_sha256']}")
    print(f"Sample rows: {', '.join(map(str, manifest['sample']['row_indices']))}")
    if args.run_inference:
        run_inference(sample_dir, manifest, args.batch_size)
        print(f"Benchmark outputs: {sample_dir}")
        publish_local_gallery(sample_dir, Path("artifacts/damage-research/ladi"))
    elif args.render_only:
        publish_local_gallery(sample_dir, Path("artifacts/damage-research/ladi"))
    else:
        print("No inference was run. Pass --run-inference to execute the CUDA benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
