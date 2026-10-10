"""Render local research results without rerunning inference or contacting sources."""

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image


ROOT = Path("artifacts/damage-research")
COLORS = ["white", "#46b579", "#e4bd8b", "#b64645"]


def percent(value):
    return "undefined" if value is None else f"{100 * value:.4f}%"


def render():
    reports = [json.loads((ROOT / folder / "report.json").read_text()) for folder in ("bright-unet", "bright-siam")]
    if [tile["id"] for tile in reports[0]["per_tile"]] != [tile["id"] for tile in reports[1]["per_tile"]]:
        raise ValueError("Models must use the same complete tile sample")
    # Illustrations are the first two label-positive tiles in official split order.
    # Pooled metrics use all 26 tiles, including background-only and intact tiles.
    examples = [tile["id"] for tile in reports[0]["per_tile"] if sum(
        tile["per_class"][label]["truth_pixels"] for label in ("damaged", "destroyed")
    ) > 0][:2]
    figure, axes = plt.subplots(len(examples), 5, figsize=(15, 7))
    titles = ["Pre-event RGB", "Post-event SAR", "Human damage labels", "Pretrained UNet", "Pretrained SiamAttnUNet"]
    for row, identifier in enumerate(examples):
        sources = [("bright-unet", kind) for kind in ("pre", "sar", "truth", "prediction")] + [("bright-siam", "prediction")]
        for col, (folder, kind) in enumerate(sources):
            with Image.open(ROOT / folder / f"{identifier}-{kind}.png") as source:
                axes[row, col].imshow(source, cmap="gray" if kind == "sar" else None)
            axes[row, col].set_xticks([])
            axes[row, col].set_yticks([])
            if row == 0:
                axes[row, col].set_title(titles[col], fontsize=11)
        axes[row, 0].set_ylabel(identifier, fontsize=8)
    figure.suptitle("Libya flood: pretrained models miss damage on an unseen event", fontsize=15)
    figure.legend([Patch(facecolor=color, edgecolor="#777") for color in COLORS],
                  ["Background", "Intact building", "Damaged building", "Destroyed building"],
                  loc="lower center", ncol=4)
    figure.subplots_adjust(top=.89, bottom=.1, left=.03, right=.99, wspace=.03, hspace=.08)
    figure.savefig(ROOT / "bright-comparison.png", dpi=180)
    plt.close(figure)
    rows = []
    for report, folder in zip(reports, ("bright-unet", "bright-siam")):
        metrics = report["metrics"]
        damage = metrics["damaged_or_destroyed"]
        rows.append(f'<tr><td><a href="{folder}/index.html">{html.escape(report["model"])}</a></td>'
                    f'<td>{percent(metrics["macro_iou_observed_unions"])}</td><td>{percent(damage["recall"])}</td>'
                    f'<td>{percent(damage["f1"])}</td><td>{report["gpu_peak_allocated_bytes"] / 2**30:.2f} GiB</td>'
                    f'<td>{report["forward_seconds_median"]:.3f} s</td></tr>')
    extra = ""
    if (ROOT / "spacenet8" / "index.html").exists():
        extra += '<h2>SpaceNet 8 road experiment</h2><p><a href="spacenet8/#tile-0_27_67">Paired satellite images, human road annotations and model outputs</a>. Six Germany tiles; same-event reproduction, with one positive reference tile. Road annotations are rasterized using a 3 m buffer on each side of centerlines. Labels indicate water/rubble obstruction, not structural collapse.</p>'
    ahr = Path("artifacts/research/changeos-ahr-altenahr/report.json")
    if ahr.exists():
        report = json.loads(ahr.read_text())
        extra += ('<h2>Ahr ChangeOS diagnostic</h2><p>Public pre-event 2019 and late-July 2021 orthophotos. '
                  'Predicted building pixel classes; no matched labels, so accuracy is unknown. '
                  'The two-year baseline and orthophoto/satellite domain shift need review.</p>'
                  '<a href="../research/changeos-ahr-altenahr/comparison.png"><img src="../research/changeos-ahr-altenahr/comparison.png" alt="Ahr before, after and model predictions"></a>'
                  '<p><a href="../research/changeos-ahr-altenahr/report.json">Provenance and CUDA report</a> · '
                  '<a href="../research/changeos-ahr-altenahr/predicted-damage.geojson">Predicted areas (GeoJSON)</a></p>')
    # LADI writes to its own configurable cache; the report below links only
    # explicitly published results supplied to the research-artifact directory.
    if (ROOT / "ladi" / "index.html").exists():
        extra += '<h2>LADI image triage</h2><p><a href="ladi/index.html">All sample images and image-level scores</a>. These tags do not localize a damaged road.</p>'
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FloodBeacon damage research</title>
<style>body{max-width:1300px;margin:32px auto;padding:0 20px;font:17px/1.5 system-ui;color:#142537;background:#fafcfb}h1,h2{line-height:1.2}img{max-width:100%}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:10px;text-align:left;border-bottom:1px solid #ccd7d0}a{color:#12634e}.notice{padding:15px;background:#fff0cf;border-left:5px solid #bc7412}small{color:#4b5a54}</style>
<h1>FloodBeacon · identifying existing damage</h1><p class="notice">Research experiments. Model predictions do not certify damage, bridge safety, route passability or future collapse. Nothing here is published through the production API.</p>
<p><a href="../dataset-viewer/">Inspect raw imagery with synchronized zoom and separate human/model views</a></p>
<h2>Measured result: both BRIGHT models fail this flood transfer test</h2><p>All 26 official standard-test Libya tiles, selected without model or label filtering. Nine tiles contain damaged/destroyed labels. Both author checkpoints are described as excluding Libya from training; that recipe has not been independently audited. 2,359,467 reference damage pixels are present.</p>
<table><tr><th>Model / full gallery</th><th>4-class mean IoU</th><th>Damage recall</th><th>Damage F1</th><th>Peak CUDA memory</th><th>Median forward / tile</th></tr>''' + "".join(rows) + '''</table>
<p>Mean IoU includes background and intact buildings. It hides near-zero damage detection. Damage recall/F1 pool damaged and destroyed classes. FP32, full 1024×1024, batch one, no tiling or test-time augmentation; timing covers synchronized model forward, not retrieval/export.</p>
<img src="bright-comparison.png" alt="Human damage labels contrasted with two pretrained model outputs"><small>Illustrations: first two label-positive tiles in official split order. Metrics use all 26 tiles. Optical imagery/labels: Maxar CC BY-NC 4.0; SAR: CC BY 4.0. Local research only.</small>
''' + extra + '''<h2>Practical next choices</h2><p>SpaceNet 8 offers spatial road-water/rubble attribution; this is disruption evidence. ETH xBD-S12 is a building-damage candidate designed for Sentinel data, but labeled evaluation requires original xBD access. No ready verified bridge-collapse checkpoint was found. Keep engineering/agency evidence for bridge destruction.</p></html>'''
    (ROOT / "index.html").write_text(document)
    files = [path for path in ROOT.rglob("*") if path.is_file() and path.name != "artifact-manifest.json"]
    if ahr.exists():
        files += [path for path in ahr.parent.iterdir() if path.is_file()]
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "illustration_ids": examples,
                "metrics_sample": "All 26 official Libya standard-test tiles", "outputs": [
                    {"path": str(path), "bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)
                ]}
    (ROOT / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(ROOT / "index.html")


if __name__ == "__main__":
    render()
