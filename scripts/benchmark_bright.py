"""Run pinned BRIGHT event-excluded checkpoints on real labeled tiles using CUDA."""

import argparse
import hashlib
import html
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import rasterio
from PIL import Image
import torch

from floodbeacon.research_metrics import CLASSES, pixel_confusion, segmentation_metrics

COMMIT = "59269142f3a3550320513e362692732f46486985"
SOURCE = f"https://raw.githubusercontent.com/ChenHongruixuan/BRIGHT/{COMMIT}/"
CHECKPOINTS = {
    "UNet": (124274886, "21675d18425db0b8b5b3ccfc8f74b30e"),
    "SiamAttnUNet": (243965300, "20459d94aa13fc85aa40d6b90340a98f"),
}
PALETTE = np.array([[255, 255, 255], [70, 181, 121], [228, 189, 139], [182, 70, 69]], dtype=np.uint8)


def download(url, path, max_bytes, md5=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if not path.exists():
        with httpx.stream("GET", url, timeout=90, follow_redirects=True) as response:
            response.raise_for_status()
            total = 0
            temporary = path.with_suffix(path.suffix + ".download")
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Download exceeded the experiment budget")
                    output.write(chunk)
            if md5 and hashlib.md5(temporary.read_bytes()).hexdigest() != md5:
                raise ValueError("Checkpoint checksum mismatch")
            temporary.replace(path)
        receipt_path.write_text(json.dumps({"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}))
    content = path.read_bytes()
    if len(content) > max_bytes or (md5 and hashlib.md5(content).hexdigest() != md5):
        raise ValueError("Cached source size/checksum mismatch")
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    return {"url": url, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
            "retrieved_at": receipt.get("retrieved_at"),
            "retrieval_note": "Original retrieval time was not recorded" if not receipt else None}


def load_tile(root, identifier):
    paths = [root / folder / f"{identifier}_{suffix}.tif" for folder, suffix in (
        ("pre-event", "pre_disaster"), ("post-event", "post_disaster"), ("target", "building_damage"),
    )]
    arrays, grids = [], []
    for path in paths:
        with rasterio.open(path) as raster:
            arrays.append(raster.read())
            grids.append((raster.crs, raster.transform, raster.shape, raster.profile))
    for crs, transform, shape, _ in grids[1:]:
        mapping = ~grids[0][1] @ transform
        corners = [(0, 0), (shape[1], 0), (0, shape[0]), (shape[1], shape[0])]
        # Reject real subpixel shifts while allowing TIFF affine roundoff (~1e-10 px).
        if crs != grids[0][0] or shape != grids[0][2] or not all(
            np.allclose(mapping @ corner, corner, rtol=0, atol=1e-6) for corner in corners
        ):
            raise ValueError(f"Unaligned imagery/label grids: {identifier}")
    pre, post, labels = arrays
    if pre.shape != (3, 1024, 1024) or post.shape != (1, 1024, 1024) or labels.shape != (1, 1024, 1024):
        raise ValueError("Expected original 1024-pixel BRIGHT RGB/SAR/label tiles")
    mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)[:, None, None]
    std = np.array([58.395, 57.12, 57.375], dtype=np.float32)[:, None, None]
    pre_normalized = (pre.astype(np.float32) - mean) / std
    post_normalized = (np.repeat(post, 3, axis=0).astype(np.float32) - mean) / std
    return pre, post, labels[0], pre_normalized, post_normalized, grids[0][3]


def run(args):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this benchmark; no CPU fallback")
    identifiers = args.ids.read_text().splitlines()
    if len(identifiers) != 26 or len(set(identifiers)) != 26:
        raise ValueError("Use the complete official 26-tile Libya test subset")
    manifest = json.loads(args.manifest.read_text())
    for record in manifest:
        path = args.data / record["member"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Input checksum mismatch: {record['member']}")
    if {record["id"] for record in manifest} != set(identifiers) or len(manifest) != 78:
        raise ValueError("Manifest must contain all three modalities for every selected tile")
    sources, panels = [], []
    args.output.mkdir(parents=True, exist_ok=True)
    # Retain the exact receipt used by this run; subsequent retrievals may
    # refresh metadata at the source cache path without changing imagery bytes.
    (args.output / "input-manifest.json").write_bytes(args.manifest.read_bytes())
    sources.append(download(SOURCE + "LICENSE", args.cache / "LICENSE", 20_000))
    sources.append(download(SOURCE + "bda_benchmark/dataset/imutils.py", args.cache / "imutils.py", 100_000))
    # Networks are the inspected native author definitions, pinned to an immutable commit.
    source_path = args.cache / f"{args.model}.py"
    sources.append(download(SOURCE + f"bda_benchmark/model/{args.model}.py", source_path, 100_000))
    spec = importlib.util.spec_from_file_location("bright_author_model", source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = getattr(module, args.model)(6 if args.model == "UNet" else 3, 4)
    size, md5 = CHECKPOINTS[args.model]
    filename = f"ckpt_{args.model}_cross_event_zeroshot_libya-flood.pth"
    checkpoint = args.cache / filename
    sources.append(download(f"https://zenodo.org/api/records/15349462/files/{filename}/content", checkpoint, size, md5))
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True), strict=True)
    model = model.to("cuda").eval()
    assert all(parameter.device.type == "cuda" for parameter in model.parameters())
    torch.cuda.reset_peak_memory_stats()
    matrix, per_tile, seconds = np.zeros((4, 4), dtype=np.int64), [], []
    with torch.inference_mode():
        for identifier in identifiers:
            pre, post, truth, pre_normalized, post_normalized, profile = load_tile(args.data, identifier)
            first = torch.from_numpy(pre_normalized[None]).to("cuda")
            second = torch.from_numpy(post_normalized[None]).to("cuda")
            inputs = (torch.cat((first, second), dim=1),) if args.model == "UNet" else (first, second)
            torch.cuda.synchronize()
            started = time.perf_counter()
            logits = model(*inputs)
            assert logits.device.type == "cuda" and logits.shape == (1, 4, 1024, 1024)
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            prediction = logits.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
            tile_matrix = pixel_confusion(truth, prediction)
            matrix += tile_matrix
            seconds.append(elapsed)
            per_tile.append({"id": identifier, "forward_seconds": elapsed, **segmentation_metrics(tile_matrix)})
            profile.update(count=1, dtype="uint8", nodata=255, compress="deflate")
            with rasterio.open(args.output / f"{identifier}-prediction.tif", "w", **profile) as output:
                output.write(prediction, 1)
            rgb = np.transpose(pre, (1, 2, 0)).astype(np.uint8)
            truth_colors = np.full((*truth.shape, 3), 127, dtype=np.uint8)
            known = truth < 4
            truth_colors[known] = PALETTE[truth[known]]
            for kind, array in (("pre", rgb), ("sar", post[0].astype(np.uint8)), ("truth", truth_colors), ("prediction", PALETTE[prediction])):
                Image.fromarray(array).save(args.output / f"{identifier}-{kind}.png")
            panels.append(f'<article><h3>{html.escape(identifier)}</h3><div>' + "".join(
                f'<figure><img src="{identifier}-{kind}.png" alt="{kind}" loading="lazy"><figcaption>{kind}</figcaption></figure>'
                for kind in ("pre", "sar", "truth", "prediction")
            ) + '</div></article>')
            print(f"{args.model} {identifier}: {elapsed:.3f}s", flush=True)
    report = {
        "experiment": "BRIGHT Libya building damage research benchmark", "model": args.model,
        "generated_at": datetime.now(timezone.utc).isoformat(), "sources": sources,
        "input_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "input_manifest_snapshot": "input-manifest.json",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "selection": "All 26 official standard-test Libya tiles; no selection by labels",
        "split_note": "Author checkpoint is labeled event-excluded zero-shot Libya; authors' complete target-event pool differs from this subset.",
        "classes": list(CLASSES), "metrics": segmentation_metrics(matrix), "per_tile": per_tile,
        "device": torch.cuda.get_device_name(), "torch": torch.__version__, "cuda_build": torch.version.cuda,
        "execution": "CUDA, full 1024x1024 tiles, batch one, FP32, no TTA or tiling",
        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "forward_seconds_total": sum(seconds), "forward_seconds_median": float(np.median(seconds)),
        "limitations": ["Building pixel classification, not bridge/road damage or route passability", "Very-high-resolution optical/SAR, not Sentinel inputs", "One event and small benchmark subset, not operational validation", "Libya optical imagery and associated labels have noncommercial terms; local research only", "Scores are not calibrated damage probabilities"],
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    summary = html.escape(json.dumps(report["metrics"], indent=2))
    (args.output / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>BRIGHT damage benchmark</title><style>body{font:16px system-ui;margin:24px;color:#0f172a}article>div{display:grid;grid-template-columns:repeat(4,1fr)}figure{margin:4px}img{width:100%}pre{white-space:pre-wrap}h3{margin-bottom:6px}</style>' + f'<h1>{args.model} · Libya flood benchmark</h1><p>Background: white; intact: green; damaged: amber; destroyed: red. Building pixels only. Local noncommercial research.</p><details><summary>Metrics</summary><pre>{summary}</pre></details>' + "".join(panels))
    print(json.dumps({"model": args.model, "metrics": report["metrics"], "gpu_peak_allocated_bytes": report["gpu_peak_allocated_bytes"]}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=list(CHECKPOINTS), default="UNet")
    parser.add_argument("--data", type=Path, default=Path("data/research/bright-sample"))
    parser.add_argument("--ids", type=Path, default=Path("data/research/bright-sample/test-ids.txt"))
    parser.add_argument("--manifest", type=Path, default=Path("data/research/bright-sample-manifest.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/damage-research"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/damage-research/bright-unet"))
    run(parser.parse_args())
