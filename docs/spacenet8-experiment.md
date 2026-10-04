# SpaceNet 8 local CUDA reproduction

Executed 2026-10-03 on the RTX 3080 Laptop GPU. The first-place author
HRNet-W48 + OCR flood checkpoint ran on all six preselected Germany tiles.
**Obstructed-road recall was only 31.88%** against the rasterized human vector
reference, with precision 69.82% and F1 43.77%. Most reference obstructed-road
pixels were missed. This is a same-event reproduction diagnostic; Germany is
the checkpoint's training region, and only one sampled tile is flood-positive.
It is not independent Ahr transfer accuracy or a road-safety validation.

## Data and reference meaning

[SpaceNet's official dataset](https://spacenet.ai/sn8-challenge/) supplies
paired Maxar pansharpened RGB imagery, mapping CSVs, human reference vectors,
and annotations. Dataset imagery/labels are CC BY-SA 4.0. The
[author repository](https://github.com/SpaceNetChallenge/SpaceNet8) is
Apache-2.0; the author provides the checkpoint through its README, without a
separate checkpoint license file identified in this check.

The sample is `random.Random(42).sample` of six rows from the 202 official
Germany mapping rows sorted by label filename. `selection.json` was written
before fetching labels or images. Every selected tile remains in the results;
there was no selection based on damage content or predictions. Only the first
mapped post-event image is used when a second image also exists. Five tiles
have no positive obstructed-road reference; `0_27_67` has 29 positive road
vector segments and 43 positive building polygons before rasterization.

Road reference masks are **rasterized human vector annotations, not manually
drawn pixel masks**. `Germany_Training_Public_reference.csv` supplies pixel WKT
highway centerlines and `Flooded` values. The baseline's 3 m buffer is reproduced
in EPSG:32632 UTM meters: 3 m on each side, a nominal 6 m corridor, not a measured
full road-surface footprint. Building polygons use their supplied footprints.
The class order is background, non-flooded building, flooded building,
non-flooded road, flooded road. Buildings take priority at road/building
overlaps, as in the author's four-channel-to-argmax conversion. Empty `Null`
rows represent absent objects; nonempty unknown-status geometry and missing
raster pixels are excluded as 255. One input pixel is unknown on the positive
tile. Raster validity does not detect all clouds/shadows or determine whether
an asset is safe.

The [challenge paper](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf)
defines flooded roads to include water coverage **or rubble obstruction**.
The reference does not identify bridge collapse, structural road destruction,
engineering closure status, a damage mechanism, or boat navigability.

## Native model and adapter

The [first-place code/checkpoint instructions](https://github.com/SpaceNetChallenge/SpaceNet8/tree/main/01-ohhan777/code)
are pinned to repository commit `30ca30c2530c6a234d040f60a99a7366ff62d756`.
The author `best_flood.pt` checkpoint is 513,082,249 bytes, SHA-256
`c7f5ac3fe6da2e3d7536fc432aa8cb7efa6eb9f6f1e183eea091f901afc8df29`.
Its stored epoch is 215 and stored date is `2022-08-21T01:22:26.164555`;
those are training checkpoint metadata, not satellite acquisition times.

The native source architecture and YAML configuration instantiate a fresh
network; all checkpoint state keys load strictly. The legacy author checkpoint
serializes a complete model and a YACS configuration, requiring
`torch.load(..., weights_only=False)` on this exact retained author artifact.
The original source remains unchanged in the cache. A compatible copy replaces
only removed `np.int(...)` with equivalent built-in `int(...)` in channel-count
arithmetic. No layers, learned weights, normalization values, or class heads
were changed. The fresh network keeps author `ALIGN_CORNERS=True` internally.

The adapter uses one GPU, FP32, batch one, full 1300×1300 tiles, no tiling and
no test-time augmentation. SyncBatchNorm uses its stored running statistics
in evaluation mode, so no four-GPU DDP launcher is needed. Author RGB scaling
is division by 255, mean `[0.249566, 0.318912, 0.21801]`, and standard deviation
`[0.12903, 0.11784, 0.10739]`. The five-class flood head is bilinearly upsampled
with `align_corners=False`, softmaxed, and argmaxed. The author's threshold 0.9
converts low-score flooded building/road predictions to the corresponding
non-flooded class; it was not tuned on these labels. Softmax outputs are
uncalibrated scores.

One explicit geospatial correction differs from the original runner. It warps
post-event RGB bilinearly to the **exact pre-event grid**, rather than specifying
only output width/height while retaining the post-image extent. Original post
bounds differ by at most 1.392 pre-event pixels in this sample. Matching CRS,
tile extents within two pixels, three RGB bands and native pre-tile dimensions
are checked before resampling. All output GeoTIFFs use the pre-image WGS84
grid. The exact grid correction means this is an adaptation rather than a
bit-for-bit reproduction of the four-GPU author program.

## Actual results and inspection

| Tile | Human obstructed-road pixels | Predicted obstructed-road pixels | Recall |
| --- | ---: | ---: | ---: |
| `0_39_67` | 0 | 0 | Undefined: no positives |
| `0_20_65` | 0 | 0 | Undefined: no positives |
| `0_15_70` | 0 | 0 | Undefined: no positives |
| `0_43_62` | 0 | 0 | Undefined: no positives |
| `0_27_67` | 54,161 | 24,728 | 31.88% |
| `0_26_63` | 0 | 0 | Undefined: no positives |

Pooled road-class IoU is 28.02%. No positive road predictions occurred on the
five negative tiles; that tiny same-event sample cannot establish low false
alarm rates elsewhere. Pixel results depend on the 3 m reference buffer and
do not measure instance accuracy, road-network APLS, full-event coverage, or
structural failure detection.

CUDA parameters, input tensors and output logits were verified on device.
PyTorch 2.14.1+cu130, CUDA runtime 13.0, Python 3.14.8 were the existing locked
research environment. Peak allocated CUDA memory was 3.324 GiB. Synchronized
forward plus head interpolation/softmax/threshold took approximately 0.680 s
per tile after the first warm-up tile. Decoding, downloading and export are
excluded. The optional latest stable `yacs==0.1.8` was checked against
[official PyPI](https://pypi.org/project/yacs/) before adding it for the legacy
checkpoint/configuration. No production processing, API or database changed.

Open `http://127.0.0.1:8080/damage-research/spacenet8/#tile-0_27_67` directly
at the positive flood tile. Each selected tile has
four full-resolution clickable PNGs: raw before, raw after, human vector
reference over after, and model attribution over after. Red means reference or
model water/rubble road obstruction; blue means non-flooded road. Gold/green
are flooded/non-flooded buildings. Gray means missing/unknown pixels. Clicking
the images enlarges them to inspect the underlying roofs, road corridors,
sediment and river banks. Start with `0_27_67`: muddy river-side areas and road
changes can be inspected directly, while the model overlay visibly misses
parts of the red reference corridors. That is qualitative inspection, not
proof that a specific lane is closed or passable.

The same output directory contains georeferenced pre/post RGB, categorical
truth/prediction TIFFs, uncalibrated flooded-road score TIFFs, all per-tile
confusion matrices and timings in `report.json`, input/source checksums and
retrieval receipts in `input-manifest.json`, and output hashes in
`checksums.json`. `run-script.py` preserves the exact executed runner source
matching the report's script checksum, including when a later edit only improves
the viewing page. Exact pixel acquisition times were absent from the retained
CSV/TIFF metadata and are explicitly unknown; filenames/checkpoint dates are
not substituted for observation time. Working projected CRS and buffer units
are recorded separately from the output EPSG:4326 grid. Inputs, weights and
outputs stay ignored by Git.

## Reproduce

```sh
uv sync --locked --group damage-research
uv run --group damage-research python scripts/prepare_spacenet8.py
uv run --group damage-research python scripts/benchmark_spacenet8.py
uv run --group damage-research python -m pytest tests/test_spacenet8_research.py -q
uv run python -m http.server 8080 --bind 127.0.0.1 --directory artifacts
```

The downloader fetches public individual S3 objects, not the full Germany
tarball. Total retained source/input/weight bytes are 569,793,474 (~543 MiB).
Downloads have per-file bounds; cached bytes are checksummed. The runner
requires CUDA and raises instead of falling back to CPU. Three targeted tests
passed for unknown-pixel exclusion, undefined absent-class recall, meter-based
road buffering, unknown-status geometry and building/road overlap priority.
The positive tile's raw after image, human overlay and model overlay were
visually inspected. This real-data run is separate evidence from those tests.
