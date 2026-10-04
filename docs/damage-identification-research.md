# Identifying already damaged infrastructure

Deep research and local experiments, 2026-10-03. Three parallel researchers
covered building models, road/bridge models, and datasets/access. This is about
post-event identification. It does not predict future structural failure.

## Recommendation

For FloodBeacon's **road-access goal**, the strongest accessible road baseline
is **SpaceNet 8 road disruption segmentation**, combined with agency/engineering
evidence for actual bridge destruction. Its labels identify road pixels visibly
covered by water or rubble; they do not establish structural collapse, a legal
closure, or a safe alternative route. Public winning weights and labeled
high-resolution Germany imagery are available. The Germany event overlaps Ahr,
so reproduce it honestly as a same-event benchmark, then evaluate independent
geography/events before claiming transfer. See the
[road and bridge research](research-roads-bridges.md).
The subsequently approved [six-tile CUDA experiment](spacenet8-experiment.md)
has now run. Its 31.88% obstructed-road recall against rasterized reference
vectors is weak even on this same-event sample. This is a useful research
baseline, not a detector ready for responder use.

For **building damage**, pretrained models exist, but the local flood experiments
show why downloading one is insufficient. Both BRIGHT zero-shot baselines
missed practically all positive damage pixels on the tested Libya subset.
Do not integrate either unchanged. ChangeOS is a practical paired-RGB candidate
for a diagnostic demo; ETH xBD-S12 is designed for the freely available Sentinel
input regime. Neither has established Ahr/BC accuracy here.

For **bridge collapse**, no ready public checkpoint with verified reuse terms,
appropriate overhead flood labels and relevant independent validation was found.
Recent bridge-specific YOLO and orthophoto papers are research leads, not
verified install-and-run models. Generic YOLO object weights and vehicle-camera
pavement models do not supply collapsed-bridge knowledge. Ahr field-study labels
are available by author request; BC's official Highway 8 repair records provide
site evidence. Do not turn inundation into a destruction label.

## What is usable, and what it needs

| Candidate | Actual output | Inputs/data | Verified status and access |
| --- | --- | --- | --- |
| [SpaceNet 8](https://spacenet.ai/sn8-challenge/) / winning HRNet+OCR | Spatial flooded/obstructed road and building attribution | Paired submeter RGB; public Germany/Louisiana labels | Ran native model on CUDA, six Germany tiles, with only one label-positive tile. Same-event reproduction, not independent accuracy. Data public without account, CC BY-SA 4.0; code Apache-2.0. |
| [BRIGHT](https://github.com/ChenHongruixuan/BRIGHT) UNet and SiamAttnUNet | Background, intact, damaged, destroyed **building pixels** | Submeter pre-RGB/post-SAR; all 26 official Libya standard-test tiles downloaded with labels | Both ran on CUDA and failed positive damage detection. Public weights/code; Libya optical/labels CC BY-NC 4.0, SAR CC BY 4.0. Local research artifacts remain ignored. |
| [ChangeOS Swin-T](https://huggingface.co/EVER-Z/torchange_example_changeos_swint_on_xview2_best42k) | Building localization and no/minor/major/destroyed pixel grades | Paired submeter RGB; public Ahr 2019/2021 orthophotos | Strict checkpoint loading and CUDA inference work. No matched independent labels, so no local accuracy claim. Model/code Apache-2.0; Ahr imagery dl-de/by-2-0 with attribution. |
| [ETH xBD-S12](https://github.com/prs-eth/xbd-s12) | Binary building damage, with localization | 28 channels: pre/post Sentinel-1 VV/VH + all 12 Sentinel-2 bands | Public seed checkpoints and Sentinel imagery verified. Original xBD labels require separate registered access/terms. Not run locally. MIT code/model cards; Sentinel archive CC BY 4.0. |
| [MITLL LADI reference](https://huggingface.co/MITLL/LADI-v2-classifier-small-reference) | Image-level damage/flood tags, including `roads_damage`; no damaged-road geometry | Low-altitude U.S. CAP photos, fixed random 100-row test sample | Ran on CUDA; only two positive road-damage examples, insufficient for a robust estimate. MIT model card, CC BY 4.0 dataset card; retain CAP notices. No `bridges_damage` output. |
| [RescueNet](https://pmc.ncbi.nlm.nih.gov/articles/PMC10733412/) | Spatial building damage grades and blocked/clear roads; blockage is water, sand or debris | Post-Hurricane Michael low-altitude UAV photos | Relevant training-label lead, not a ready tested checkpoint. No author weights found; archive byte access unverified and author README/Figshare licenses conflict. Resolve before selecting it. |
| Bridge-specific 2026 research | Bridge/road binary damage or bridge-instance segmentation | Japanese earthquake/tsunami orthophotos | No verified complete openly reusable checkpoint-plus-label package found. Request author data/weights if pursuing this scope. |

Other investigated models include ChangeMamba, DisasterAdaptiveNet, HOTOSM's
DINOv3 model, and 2026 BRIGHT challenge winners. Custom legacy CUDA kernels,
unverified licenses, noncommercial model terms, absent checkpoints, or weak
unseen-event evidence make them less convenient first integrations. These are
specific access/reproduction findings, not proof that the methods are inferior.
The [building-model report](research-building-models.md) records exact recipes,
published metrics, model revisions, package compatibility and exclusions. The
[dataset report](research-damage-datasets.md) records source terms and retrieval.

## Actual CUDA evaluation: BRIGHT Libya flood

The benchmark uses **all 26 tiles in the official standard-test Libya subset**,
chosen without label or model-result filtering. Nine tiles contain damaged or
destroyed buildings; there are 2,359,467 positive reference pixels. These are
human building damage labels, not synthetic fixtures. Author checkpoints are
described as excluding Libya from training. The exact UNet training log is not
available for independent audit; retain that qualification.

Native author networks and preprocessing were used: normalized pre-RGB,
normalized replicated post-SAR, strict state-dictionary loading, full 1024×1024
FP32 tiles, batch one, no TTA and no tiling. Both parameters and outputs ran on
CUDA. Geometry checks allow TIFF serialization roundoff but reject real shifts.
No model, threshold or training change was selected using these test labels.

| Model | Four-class mean IoU | Damaged/destroyed recall | Damaged/destroyed F1 | Peak allocated CUDA memory | Median synchronized forward |
| --- | ---: | ---: | ---: | ---: | ---: |
| UNet | 31.87% | **0.01297%** | 0.02593% | 2.13 GiB | 0.138 s/tile |
| SiamAttnUNet | 32.45% | **0%** | 0% | 3.44 GiB | 0.321 s/tile |

UNet predicted 334 destroyed pixels, of which 306 matched positive labels; it
predicted **zero damaged-class pixels**. SiamAttnUNet predicted no damaged or
destroyed pixels. Background-dominated pixel accuracy (~85%) and the mean IoU
conceal this failure. Neither is suitable as our pretrained flood damage
detector without further training and independent validation.

These are pixel-level metrics on a small single-event subset. They are not
building-instance accuracy or full-event coverage. The authors' published
zero-shot evaluation pools the entire target event's train/validation/test
members; our standard-test subset is different, so this is not an exact
reproduction of their published event-wide scores. Per-tile scores and all
26 visual comparisons remain available beside pooled results.

Environment: Python 3.14.8, PyTorch 2.14.1+cu130, CUDA runtime 13.0,
NVIDIA RTX 3080 Laptop GPU (16 GB). Official release/registry versions were
checked before adding the optional `damage-research` group. The Linux index
uses the official PyTorch CUDA 13.0 wheels, supported by the installed driver.
The original Torch 1.10 / legacy Python recipes were replaced by compatible
current stable packages, while model architectures/weights stayed pinned.

## Actual CUDA evaluation: LADI aerial-image triage

The pinned **small reference** checkpoint uses only the authors' training split;
the similarly named deployment checkpoint includes all splits and must not be
scored on its own test labels. Our fixed seed-42 random sample takes 100 rows
without looking at labels. The pinned Dataset Viewer exposes 1,049 test rows,
versus 1,041 reported in the paper; the unresolved discrepancy is recorded.

At the predeclared independent sigmoid threshold 0.5, `roads_damage` has
**two positive examples**: one true positive and one false negative, with zero
false positives among 98 negatives. Recall is 50%, F1 0.667, but those numbers
have too little positive support to establish performance. The 99% image
accuracy is especially misleading. This U.S. low-altitude image-level task is
not an Ahr/BC satellite transfer evaluation and cannot supply damaged-road
geometry or bridge collapse status.

Actual CUDA batch-8 forwards took 0.758 s for 100 images, with 0.53 GiB peak
allocated memory; decoding/preprocessing/export are excluded from that timing.
All images, per-label support/confusions and per-image scores are inspectable.
The main value here is a reproducible triage baseline and working CUDA runtime,
not evidence of a map-ready damage detector.

## Subsequent CUDA experiment: SpaceNet 8

The user approved this experiment after the initial research. The native
first-place HRNet-W48+OCR flood checkpoint ran on six seed-42 Germany tiles
selected before reading labels/results. One has positive road-obstruction
reference labels; five are negative controls. Against human road centerlines
rasterized with the author's 3 m buffer on each side, obstructed-road precision
was 69.82%, recall 31.88%, F1 43.77% and IoU 28.02%. Most positive reference
pixels were missed. These depend on the reference-buffer geometry and are
not road-instance or network-connectivity scores.

Germany is part of the checkpoint's training region: these are same-event
reproduction diagnostics, not independent transfer accuracy. CUDA FP32 batch
one full 1300-pixel tiles used 3.324 GiB peak allocated memory and median
0.677 s synchronized forward/postprocessing. Only legacy package compatibility
and explicit pre/post grid alignment were adapted. The
[full experiment report](spacenet8-experiment.md) preserves exact source,
checksums, preprocessing, per-tile results and limitations.

Inspect raw paired satellite images, reference vectors and predictions at
`http://127.0.0.1:8080/damage-research/spacenet8/#tile-0_27_67`.
The [raw-data viewer](http://127.0.0.1:8080/dataset-viewer/) provides synchronized
zoom on Ahr/Libya imagery and links to this SpaceNet gallery. Final verification
now passes **56 tests**, including the three SpaceNet safeguards.

## Ahr and BC case feasibility

**Measured runtime, unscored diagnostic:** ChangeOS ran on a visually inspected
populated Altenahr crop: 1024×1024 paired RGB at 0.4 m on matching EPSG:25832
grids, full FP32 CUDA inference, 0.460 s synchronized forward and 0.79 GiB peak
allocated memory. It predicted 154,153 no-damage building pixels and 4,608
destroyed pixels (~737 m²), with zero minor/major pixels. These are candidate
classes, not confirmed destroyed buildings. Its 65 contiguous predicted class
regions are not 65 building instances. There are no matched independent labels
for this crop, so precision/recall are **unknown**. GeoJSON and score rasters
are diagnostic artifacts only. Apparent roof/riverbank changes deserve manual
review, rather than turning visualization into validation.

**Ahr:** public RLP orthophotos provide a lawful before/after RGB route without
a commercial imagery account. The available pre-event source is the 2019
orthophoto collection; post-event imagery comes from special flights on July
24, 28 and 29, 2021. A collection date is not an exact pixel acquisition time.
Center metadata creation/publication fields are preserved separately. A
two-year baseline includes possible unrelated construction/demolition, and
orthophotos differ from the satellite training distribution. The July 18
agency assessment is an earlier observation, not aligned ground truth for
late-July imagery. An initial forest-only crop was rejected as an uninformative
building diagnostic; its all-background prediction is not a transfer failure.

**BC:** no verified open paired submeter imagery plus flood-damage benchmark
was found. Official Highway 8 records report 24 damaged sites and over 7 km of
highway lost. Those records could support a reviewed site-level reference, but
do not automatically provide pixel labels or exact scene alignment. Current
bridge/culvert inventory is contextual, not November 2021 intact/damaged truth.
Free Sentinel access remains feasible, but bridge destruction cannot be resolved
from that fact alone.

**Account/access needs:** everything downloaded for the present BRIGHT, Ahr
and LADI experiments was public without a token. ETH's labeled evaluation needs
the original xBD/xView2 download account and applicable dataset terms. Bridge
labels/checkpoints may require author requests; the user has not authorized
sending those messages. Do not assume CEMS derived vectors grant access to
the underlying commercial imagery.

## Reproduce and inspect

From the repository root, CUDA is mandatory for the inference runners; they
raise rather than silently falling back to CPU. Large inputs, weights and
generated outputs are ignored by Git. The optional group is separate from the
FastAPI runtime. Some declared torchange dependencies are training frameworks,
because its package eagerly imports them even for inference.

```sh
uv sync --locked --group damage-research
uv run --group damage-research python scripts/prepare_bright.py
uv run --group damage-research python scripts/benchmark_bright.py --model UNet --output artifacts/damage-research/bright-unet
uv run --group damage-research python scripts/benchmark_bright.py --model SiamAttnUNet --output artifacts/damage-research/bright-siam
uv run --group damage-research python scripts/prepare_ahr_imagery.py
uv run --group damage-research python scripts/predict_changeos_ahr.py
uv run --group damage-research python scripts/benchmark_ladi.py
uv run --group damage-research python scripts/benchmark_ladi.py --run-inference
uv run --group damage-research python scripts/render_damage_research.py
uv run --group damage-research python -m http.server 8080 --bind 127.0.0.1 --directory artifacts
```

Open `http://127.0.0.1:8080/damage-research/`. The index and per-model galleries
use only local assets. Each runner records CUDA/device, pinned model IDs,
input/weight checksums, processing parameters and limitations. The renderer
adds an output checksum manifest without rerunning models. Ahr predictions
also export georeferenced rasters and WGS84 GeoJSON; contiguous pixel regions
are not individual building instances. Scores are uncalibrated.

Validation passed 53 tests, including real PostgreSQL checks, downloader range/
CRC/cache behavior, ignored-label metrics and multi-label F1 edge cases. These
tests are separate from the real-data model results above. The existing
Starlette/httpx TestClient deprecation warning remains. Research pages and
images returned HTTP 200 from the local server; comparison figures were
visually inspected. Both BRIGHT report hashes match their retained exact input
manifest snapshots. Original source/weight retrieval times predating receipt
capture are explicitly unknown, rather than inferred from file timestamps.

## Product decision still required

The research and diagnostic code do not publish structural predictions to
PostgreSQL or the API. Choose the next product scope explicitly:

1. **Road disruption first (recommended for the stated responder-routing goal):**
   improve and independently evaluate the now-runnable SpaceNet 8 baseline,
   preserve agency-reported bridge damage, and expose disruption as its own
   evidence type. It requires submeter images; a Sentinel-only product cannot
   reuse these weights directly.
2. **Add building damage:** assess ChangeOS on aligned, independently reviewed
   building labels, or evaluate ETH xBD-S12 after obtaining xBD access. Buildings
   add a new map capability but do not resolve bridge collapse or route safety.
3. **Structural roads/bridges first:** prioritize acquiring flood-specific
   bridge/road labels and dated VHR imagery, then train/evaluate a specific model.
   This is longer research work; no ready model was verified here.

Do not invent a performance threshold for responder use without agreement.
Any operational model would need independent flood-event evaluation, meaningful
damage recall/false alarms, unknown-coverage handling and human review. Current
negative experimental results do not demonstrate that the task is impossible.
