"""Small, reproducible supervised water baseline; never a destruction detector."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pickle
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

BASE = "https://storage.googleapis.com/sen1floods11/v1.1/"
TRAIN_EVENTS = ("Ghana", "India", "Spain")
HOLDOUT_EVENT = "Bolivia"
SEED = 42
PIXELS_PER_CLASS_PER_CHIP = 8_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(url: str, path: Path) -> dict:
    """Cache complete public inputs; interrupted downloads never become inputs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = path.with_suffix(path.suffix + ".source.json")
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "FloodBeacon-POC/1"})
        with urllib.request.urlopen(request, timeout=90) as response:
            content = response.read()
        temporary = path.with_suffix(path.suffix + ".download")
        temporary.write_bytes(content)
        temporary.replace(path)
        receipt.write_text(json.dumps({"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}, indent=2))
    provenance = json.loads(receipt.read_text()) if receipt.exists() else {"url": url, "retrieved_at": None}
    if provenance["url"] != url:
        raise ValueError(f"Cached source URL mismatch: {path}")
    return {**provenance, "path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}


def _features(vv_db: np.ndarray, vh_db: np.ndarray) -> np.ndarray:
    """Both channels already in dB; preserve units and avoid implicit scaling."""
    return np.column_stack((vv_db.ravel(), vh_db.ravel(), (vv_db - vh_db).ravel())).astype(np.float32)


def predict_water(model: RandomForestClassifier, vv_db: np.ndarray, vh_db: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Return water scores in [0,1], with NaN for invalid/unobserved pixels.

    Scores are classifier vote fractions, not calibrated flood/failure risk.
    RTC linear gamma naught inputs must be converted with 10*log10 upstream.
    """
    vv_db, vh_db, valid = np.asarray(vv_db), np.asarray(vh_db), np.asarray(valid, dtype=bool)
    if vv_db.shape != vh_db.shape or vv_db.shape != valid.shape:
        raise ValueError("VV, VH and valid arrays must have the same shape")
    usable = valid & np.isfinite(vv_db) & np.isfinite(vh_db)
    output = np.full(vv_db.shape, np.nan, dtype=np.float32)
    if not usable.any():
        return output
    classes = list(model.classes_)
    if classes != [0, 1]:
        raise ValueError("Water model must contain classes 0 (land) and 1 (water)")
    features = _features(vv_db[usable], vh_db[usable])
    scores = np.empty(len(features), dtype=np.float32)
    for start in range(0, len(features), 100_000):
        scores[start:start + 100_000] = model.predict_proba(features[start:start + 100_000])[:, classes.index(1)]
    output[usable] = scores
    return output


def load_model(path: Path) -> RandomForestClassifier:
    """Load ONLY a locally trained, trusted model. Pickle executes code."""
    with Path(path).open("rb") as stream:
        model = pickle.load(stream)
    if not isinstance(model, RandomForestClassifier) or list(model.classes_) != [0, 1]:
        raise ValueError("Unsupported FloodBeacon water model")
    return model


def _read_chip(sar_path: Path, label_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    with rasterio.open(sar_path) as sar, rasterio.open(label_path) as labels:
        if sar.count != 2 or labels.count != 1:
            raise ValueError("Expected two SAR channels and one label channel")
        # GeoTIFF serialization can vary at ~1e-18 degrees. Compare corner
        # displacement in pixel units, rejecting real subpixel misalignment.
        mapping = ~sar.transform @ labels.transform
        corners = [(0, 0), (sar.width, 0), (0, sar.height), (sar.width, sar.height)]
        aligned = all(np.allclose(mapping @ corner, corner, rtol=0, atol=1e-6) for corner in corners)
        if sar.crs != labels.crs or not aligned or sar.shape != labels.shape:
            raise ValueError("SAR and label grids do not align")
        bands = sar.read(out_dtype="float32")
        mask = sar.read_masks().all(axis=0) & labels.read_masks(1).astype(bool)
        label = labels.read(1)
        if not set(np.unique(label)).issubset({-1, 0, 1, 255}):
            raise ValueError("Unexpected Sen1Floods11 label classes")
        valid = mask & np.isfinite(bands).all(axis=0) & np.isin(label, (0, 1))
        metadata = {"crs": str(sar.crs), "shape": list(sar.shape), "transform": list(sar.transform),
                    "class_counts": {str(cls): int(np.sum(valid & (label == cls))) for cls in (0, 1)},
                    "unknown_pixels": int(np.sum(~valid))}
    return bands, label, valid, metadata


def _select(rows: list[list[str]], event: str, count: int) -> list[list[str]]:
    eligible = sorted((row for row in rows if row[0].startswith(event + "_")), key=lambda row: row[0])
    if len(eligible) < count:
        raise ValueError(f"Only {len(eligible)} chips available for {event}; requested {count}")
    # Fixed seeded selection without inspecting labels or holdout performance.
    indices = np.random.default_rng(SEED).choice(len(eligible), count, replace=False)
    return [eligible[i] for i in sorted(indices)]


def train_model(data_dir: Path, chips_per_event: int = 3) -> tuple[Path, dict]:
    """Train on bounded real hand labels; Bolivia is an entire-event holdout.

    Returns (local model path, complete run metadata). No network credentials,
    weak/Otsu labels, remote checkpoints or expensive deep-learning framework.
    """
    if not 1 <= chips_per_event <= 15:
        raise ValueError("chips_per_event must be between 1 and 15")
    data_dir = Path(data_dir)
    cache = data_dir / "sen1floods11"
    sources = []
    splits = {}
    for name in ("flood_train_data.csv", "flood_bolivia_data.csv"):
        path = cache / "splits" / name
        sources.append(_download(BASE + "splits/flood_handlabeled/" + name, path))
        splits[name] = list(csv.reader(io.StringIO(path.read_text())))
    event_path = cache / "Sen1Floods11_Metadata.geojson"
    sources.append(_download(BASE + event_path.name, event_path))
    license_path = cache / "label_collection.json"
    license_source = _download(BASE + "catalog/sen1floods11_hand_labeled_label/collection.json", license_path)
    sources.append(license_source)
    declared_license = json.loads(license_path.read_text()).get("license", "unknown")
    events = {feature["properties"]["location"]: feature["properties"] for feature in json.loads(event_path.read_text())["features"]}
    selections = [("train", event, row) for event in TRAIN_EVENTS for row in _select(splits["flood_train_data.csv"], event, chips_per_event)]
    selections += [("holdout", HOLDOUT_EVENT, row) for row in _select(splits["flood_bolivia_data.csv"], HOLDOUT_EVENT, chips_per_event)]
    downloads = [(BASE + "data/flood_events/HandLabeled/" + folder + "/" + filename, cache / folder / filename)
                 for _, _, pair in selections for folder, filename in zip(("S1Hand", "LabelHand"), pair)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources.extend(pool.map(lambda item: _download(*item), downloads))
    train_x, train_y, chips, heldout = [], [], [], []
    rng = np.random.default_rng(SEED)
    for split, event, (sar_name, label_name) in selections:
        bands, label, valid, grid = _read_chip(cache / "S1Hand" / sar_name, cache / "LabelHand" / label_name)
        record = {"split": split, "event": event, "sar_chip": sar_name, "label_chip": label_name,
                  "observation_date": events[event]["s1_date"].replace("/", "-"),
                  "label_optical_observation_date": events[event]["s2_date"].replace("/", "-"), **grid}
        if split == "train":
            sampled = []
            for cls in (0, 1):
                eligible = np.flatnonzero(valid & (label == cls))
                sampled.append(rng.choice(eligible, min(PIXELS_PER_CLASS_PER_CHIP, len(eligible)), replace=False))
            indices = np.concatenate(sampled)
            record["sampled_class_counts"] = {str(cls): int(np.sum(label.ravel()[indices] == cls)) for cls in (0, 1)}
            features = _features(bands[0], bands[1])
            train_x.append(features[indices])
            train_y.append(label.ravel()[indices])
        else:
            heldout.append((bands, label, valid, record))
        chips.append(record)
    x, y = np.concatenate(train_x), np.concatenate(train_y).astype(np.int8)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Selected training chips must contain both water and land")
    model = RandomForestClassifier(n_estimators=80, max_depth=12, min_samples_leaf=20,
                                   max_features=None, random_state=SEED, n_jobs=2)
    model.fit(x, y)
    matrix = np.zeros((2, 2), dtype=np.int64)
    per_chip = []
    for bands, label, valid, record in heldout:
        prediction = predict_water(model, bands[0], bands[1], valid)
        matrix += confusion_matrix(label[valid], prediction[valid] >= 0.5, labels=[0, 1])
        precision, recall, f1, _ = precision_recall_fscore_support(label[valid], prediction[valid] >= 0.5, labels=[1], zero_division=0)
        per_chip.append({"chip": record["sar_chip"], "water_precision": float(precision[0]), "water_recall": float(recall[0]), "water_f1": float(f1[0])})
    tn, fp, fn, tp = map(int, matrix.ravel())
    metrics = {"confusion_matrix_land_water": matrix.tolist(), "valid_pixels": int(matrix.sum()),
               "water_precision": tp / max(tp + fp, 1), "water_recall": tp / max(tp + fn, 1),
               "water_f1": 2 * tp / max(2 * tp + fp + fn, 1), "water_iou": tp / max(tp + fp + fn, 1),
               "threshold": 0.5, "per_chip": per_chip}
    source_fingerprint = hashlib.sha256(json.dumps({"inputs": sorted((s["url"], s["sha256"]) for s in sources),
                                                    "chips": chips, "parameters": model.get_params(),
                                                    "features": ["VV_dB", "VH_dB", "VV_dB_minus_VH_dB"],
                                                    "scikit_learn_version": sklearn.__version__}, sort_keys=True).encode()).hexdigest()
    output = data_dir / "models" / ("water-rf-" + source_fingerprint[:16])
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "model.pkl"
    temp = output / "model.pkl.tmp"
    with temp.open("wb") as stream:
        pickle.dump(model, stream, protocol=pickle.HIGHEST_PROTOCOL)
    temp.replace(model_path)
    details = {"model_id": output.name, "trained_at": datetime.now(timezone.utc).isoformat(),
               "dataset": "Sen1Floods11 v1.1 hand labels", "license": "unresolved",
               "license_declared_in_official_label_catalog": declared_license,
               "license_note": "Authors publish research downloads, but official catalog says proprietary and GitHub issue18 reports missing LICENSE. Do not infer redistribution rights from third-party mirrors.",
               "attribution": "Bonafilia, Tellman, Anderson and Issenberg (2020), Cloud to Street",
               "training_events": list(TRAIN_EVENTS), "holdout_events": [HOLDOUT_EVENT], "chips_per_event": chips_per_event,
               "sample_selection_seed": SEED, "pixels_per_class_per_chip_limit": PIXELS_PER_CLASS_PER_CHIP,
               "training_pixels": len(y), "features": ["VV_dB", "VH_dB", "VV_dB_minus_VH_dB"],
               "training_array_sha256": hashlib.sha256(x.tobytes() + y.tobytes()).hexdigest(),
               "parameters": model.get_params(), "scikit_learn_version": sklearn.__version__,
               "model_sha256": _sha256(model_path), "input_fingerprint": source_fingerprint,
               "chips": chips, "sources": sources, "metrics": metrics,
               "limitations": ["Small geographic holdout subset, not the complete benchmark", "Water includes permanent water and flood water",
                               "Classifier scores are uncalibrated", "Sen1 sigma-naught vs RTC gamma-naught domain shift",
                               "No local Ahr/BC accuracy validation", "No structural-damage or failure-time prediction", "Training-data redistribution license unresolved"]}
    metadata_temp = output / "metadata.json.tmp"
    metadata_temp.write_text(json.dumps(details, indent=2) + "\n")
    metadata_temp.replace(output / "metadata.json")
    return model_path, details


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--chips-per-event", type=int, default=3)
    args = parser.parse_args()
    path, details = train_model(args.data_dir, args.chips_per_event)
    print(json.dumps({"model_path": str(path), "metrics": details["metrics"]}, indent=2))
