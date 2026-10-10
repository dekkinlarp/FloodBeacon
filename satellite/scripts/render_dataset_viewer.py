"""Make a local naked-eye data viewer using existing verified research inputs."""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def render():
    output = Path("artifacts/dataset-viewer")
    output.mkdir(parents=True, exist_ok=True)
    for name, filename in (("before", "ahr-altenahr-vhr-pre-2019"), ("after", "ahr-altenahr-vhr-post")):
        source = Path("data/research") / f"{filename}.tif"
        metadata = json.loads(source.with_suffix(".json").read_text())
        if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError("Ahr image does not match source provenance")
        with rasterio.open(source) as raster:
            rgb = np.moveaxis(raster.read([1, 2, 3]), 0, -1)
        Image.fromarray(rgb).save(output / f"ahr-{name}.png")
        Image.fromarray(rgb).resize((512, 512)).save(output / f"ahr-{name}-inline.jpg", quality=84)
        shutil.copyfile(source, output / f"ahr-{name}.tif")
        shutil.copyfile(source.with_suffix(".json"), output / f"ahr-{name}-source.json")
    with rasterio.open("artifacts/research/changeos-ahr-altenahr/predicted-damage.tif") as raster:
        prediction = raster.read(1)
    colors = np.zeros((*prediction.shape, 4), dtype=np.uint8)
    colors[prediction == 4] = [182, 70, 69, 170]
    Image.fromarray(colors).save(output / "ahr-candidate-destroyed.png")
    ids = Path("data/research/bright-sample/test-ids.txt").read_text().splitlines()
    raw = output / "raw"
    raw.mkdir(exist_ok=True)
    for identifier in ids:
        for folder, suffix, kind in (("pre-event", "pre_disaster", "pre"), ("post-event", "post_disaster", "post")):
            shutil.copyfile(Path("data/research/bright-sample") / folder / f"{identifier}_{suffix}.tif", raw / f"{identifier}-{kind}.tif")
    template = Path(__file__).with_name("dataset_viewer.html").read_text()
    (output / "index.html").write_text(template.replace("__IDS__", json.dumps(ids)))
    print(output / "index.html")


if __name__ == "__main__":
    render()
