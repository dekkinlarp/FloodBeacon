"""Bounded public retrieval of a fixed SpaceNet 8 Germany reproduction sample."""

import argparse
import csv
import hashlib
import io
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from benchmark_bright import download

REVISION = "30ca30c2530c6a234d040f60a99a7366ff62d756"
DATA_URL = "https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/"
CODE_URL = f"https://raw.githubusercontent.com/SpaceNetChallenge/SpaceNet8/{REVISION}/"
WEIGHT_URL = "http://ohhan.net/wordpress/wp-content/uploads/2022/08/best_flood.pt"
WEIGHT_SIZE = 513_082_249
WEIGHT_SHA256 = "c7f5ac3fe6da2e3d7536fc432aa8cb7efa6eb9f6f1e183eea091f901afc8df29"
SOURCE_FILES = (
    "models/seg_hrnet_ocr.py", "models/bn_helper.py", "models/config.py",
    "models/seg_hrnet_ocr_w48_train_512x1024_sgd_lr1e-2_wd5e-4_bs_12_epoch484.yaml",
    "val_best.py", "utils/datasets.py", "baseline/data_prep/create_masks.py",
)


def prepare(root, count=6, seed=42, weights=True):
    root.mkdir(parents=True, exist_ok=True)
    records = []
    mapping_name = "Germany_Training_Public_label_image_mapping.csv"
    mapping = root / mapping_name
    records.append({"path": str(mapping.relative_to(root)), **download(DATA_URL + mapping_name, mapping, 200_000)})
    rows = sorted(csv.DictReader(io.StringIO(mapping.read_text())), key=lambda row: row["label"])
    selection_path = root / "selection.json"
    selected = random.Random(seed).sample(rows, count)
    selection = {"seed": seed, "count": count, "population_count": len(rows),
                 "method": "Random sample of lexically sorted official mapping rows before downloading labels or images",
                 "rows": selected, "selected_at": datetime.now(timezone.utc).isoformat()}
    if selection_path.exists():
        previous = json.loads(selection_path.read_text())
        if previous["rows"] != selected:
            raise ValueError("Refusing to replace a previously declared experiment sample")
        selection = previous
    else:
        selection_path.write_text(json.dumps(selection, indent=2) + "\n")
    print("Predeclared sample: " + ", ".join(row["label"] for row in selected), flush=True)
    reference_name = "Germany_Training_Public_reference.csv"
    reference = root / reference_name
    records.append({"path": reference_name, **download(DATA_URL + reference_name, reference, 15_000_000)})
    for row in selected:
        for folder, field in (("PRE-event", "pre-event image"), ("POST-event", "post-event image 1"), ("annotations", "label")):
            relative = f"{folder}/{row[field]}"
            records.append({"path": relative, "sample_id": Path(row["label"]).stem,
                            **download(DATA_URL + relative, root / relative, 30_000_000)})
    for name in SOURCE_FILES:
        relative = f"source/{name}"
        records.append({"path": relative, **download(CODE_URL + "01-ohhan777/code/" + name, root / relative, 200_000)})
    records.append({"path": "source/LICENSE", **download(CODE_URL + "LICENSE", root / "source/LICENSE", 30_000)})
    if weights:
        record = download(WEIGHT_URL, root / "best_flood.pt", WEIGHT_SIZE)
        if record["bytes"] != WEIGHT_SIZE or record["sha256"] != WEIGHT_SHA256:
            raise ValueError("Official checkpoint does not match the retained pinned size/hash")
        records.append({"path": "best_flood.pt", **record})
    manifest = {"dataset": "SpaceNet 8 Germany_Training_Public", "source_revision": REVISION,
                "license": "SpaceNet dataset CC BY-SA 4.0; repository Apache-2.0",
                "acquisition_time": None,
                "acquisition_note": "Exact tile acquisition times not present in mapping/reference CSV; no invented date from filename",
                "weight_license_note": "Author checkpoint link in Apache-2.0 repository; no separate weight license file identified",
                "selection": selection, "files": records}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained {len(records)} receipts, {sum(r['bytes'] for r in records):,} bytes", flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/research/spacenet8"))
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-weights", action="store_true")
    args = parser.parse_args()
    prepare(args.data, args.count, args.seed, not args.skip_weights)
