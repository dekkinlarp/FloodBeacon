# Current road and bridge damage from aerial imagery

Checked 2026-10-03 against primary author, agency, dataset, and model-host
sources. This review concerns **observed current damage or access disruption**.
It does not treat flood exposure or hypothetical footprint expansion as
structural damage. Checkpoint availability below means that a bounded range
request returned bytes; it does not mean that the model was run or validated
on FloodBeacon cases.

## Recommendation

For a map-ready model experiment, start with the pretrained **SpaceNet 8
flood-attribution network** on its original high-resolution Germany imagery.
Its output is a pixel mask tied to roads, and the Germany training AOI comes
from the July 2021 western Germany flood. Its road class means visibly
water-covered **or rubble-obstructed** in the post-event image. This is useful
as a narrow access-disruption signal, but it is not a bridge-collapse or road
structural-damage classifier. SpaceNet 8's Germany imagery is associated with
the Bonn/Dernau region; check exact tile overlap with FloodBeacon's AOI15 before
calling it independent evaluation. A checkpoint trained on the same event and
nearby tiles can support a reproduction demo, not evidence of Ahr transfer
accuracy.

For **bridge structural damage**, keep the agency/engineering evidence as the
source of status. The current best bridge-specific leads are human-assessed Ahr
bridge grades and recent Japanese aerial-imagery research, but neither surfaced
as a ready, openly downloadable model-plus-label package for this project. Do
not infer collapse from a flooded bridge mask.

LADI v2 is the most convenient additional model/data smoke test: its MITLL
small reference checkpoint is public and its image-level `roads_damage` test
labels are from held-out 2023 disasters. However, its reported test F1 for
`roads_damage` is only 0.17, it does not localize a damaged road, it has no
released `bridges_damage` output, and its U.S. low-altitude CAP photos differ
strongly from satellite/orthophoto chips in Ahr and BC. Treat it as a pipeline
and transfer-gap demonstration, not a product result.

## Candidate matrix

| Candidate | What the label actually says | Data and split | Weights/access | FloodBeacon fit |
| --- | --- | --- | --- | --- |
| [SpaceNet 8 winning solution, first place](https://github.com/SpaceNetChallenge/SpaceNet8/tree/main/01-ohhan777/code) | Per-pixel flooded/non-flooded building and road attribution. The challenge paper defines a flooded road as visibly covered by water **or rubble**; it includes a depicted partially destroyed road, but labels do not encode a damage mechanism, road closure, bridge class, or collapse grade. | Paired pre/post pansharpened Maxar RGB, 0.3–0.8 m. Germany (near Bonn/Dernau) and Louisiana-East have public training labels; Louisiana-West is the public test set and hidden AOI was challenge-blind. Dataset chunks are 1,300×1,300 px on an area-matched grid. The challenge paper describes 202 training tiles for Germany. | Author README advertises `best_flood.pt`, `best_road.pt`, `best_building.pt`. Range GETs to each returned HTTP 206; flood checkpoint 513,082,249 bytes and road/building checkpoints 513,082,313 bytes each. Public links required no credentials in the bounded checks. | Best verified starting point for spatial road disruption. The flood checkpoint is the relevant one. It is a large legacy model and its README specifies four GPUs for inference; one RTX 3080 Laptop 16 GB may be enough for a single network with suitable tiling, but this was not tested. |
| [SpaceNet 8 official data](https://spacenet.ai/sn8-challenge/) and [author baseline](https://github.com/SpaceNetChallenge/SpaceNet8) | Four-channel mask: flooded/non-flooded buildings and flooded/non-flooded roads, with separate pre-event road/building extraction. | German flood imagery was acquired during the same July 2021 event. Official train bundles: Germany 1,357,293,885 bytes and Louisiana-East 3,336,023,039 bytes. Louisiana-West public test bundle: 2,617,320,506 bytes. | All three public S3 tarball URLs returned HTTP 206 for a 64-byte range. SpaceNet states no AWS account is required. Dataset license is CC BY-SA 4.0; baseline repository is Apache-2.0. | The cleanest reproducible route mask benchmark, but Germany overlap makes it unsuitable as independent Ahr transfer evidence. Image acquisition, resolution, and visibility limit comparison with BC's open road/bridge inventory. |
| [LADI v2 small reference](https://huggingface.co/MITLL/LADI-v2-classifier-small-reference) | Image-level multi-label tags, including `roads_damage`, `flooding_any`, `water_any`, `debris_any`, and `bridges_any`. `roads_damage` is not a road-segment mask or an explicit closure label. The released v2a classifier omits `bridges_damage`; the authors removed that class because positive examples were too few. | 9,963 CAP aerial images in the paper: 8,030 train, 892 validation, 1,041 test. The pinned Hub Dataset Viewer currently reports 1,049 test rows at dataset revision `5f2dbfe8c466d32edafd1bab847ec5252309acdb`; the 8-row paper/viewer discrepancy is unresolved. Train/validation use disaster declarations 2015–22; test uses 2023 events. Each image received triplicate labels from trained CAP volunteers with majority vote. Mixed nadir/oblique views, geotagged in image EXIF; not satellite imagery. Default HF config supplies 1,800×1,200 resized images. | Small checkpoint is public, ungated, MIT model card; `model.safetensors` returned HTTP 206 for bytes 0–63, total 94,116,688 bytes. Dataset Hub card lists CC BY 4.0; retain CAP provenance and distribution statement. Use the `-reference` model for test evaluation: main `-small` used all splits, including test. | Easiest lightweight reference-model inference on the laptop GPU. Useful for testing the runtime and a broad image triage workflow; weak for spatial route outputs and geographic transfer. The paper reports large-model `roads_damage` F1 0.17 on test and 0.44 on validation, so do not present its road damage score as reliable detection. |
| [Bridge-and-Road-Damage-Detection (Li et al., 2026)](https://github.com/ZhengStone/Bridge-and-Road-Damage-Detection) | Binary sample-level road-or-bridge damage. The paper's examples combine obstruction, submersion, missing segments, and collapse. It does not separate bridge from road results or damage mechanisms. | 820 orthophoto samples from the 2011 Tohoku earthquake: 410 marked undamaged and 410 damaged; 600/220 train/test. Image GSD and geographic-disjoint split are not specified in the paper. All examples are from the same disaster. | The paper links a dataset share and a results share on ScienceDB, but both returned JavaScript application HTML in direct requests; no downloadable archive object or license was verifiable. The author repo's recursive tree has code and empty data/results stubs, but no model checkpoint, release, license file, or dataset CSV. Its `test_run.py` points to a missing `model_params.pkl`. | A promising mixed-disruption/collapse research lead, but not an install-and-run model. The small same-event split may overstate transfer if patches are spatially related. Verify the archives, labels, terms, image GSD and split grouping before use. |
| [Bridge segmentation and shape analysis (Kubo, Zheng & Chun, 2026)](https://doi.org/10.1680/jfoen.25.00025) | Bridge-instance segmentation plus binary damaged/undamaged status. Damage includes severe visual change such as collapse, washout, or significant deck debris. | Aerial photos after 2024 Noto and 2011 Tohoku earthquakes. Training uses 34 damaged Noto bridge images and 468 damaged Tohoku images after augmentation; validation is 41 damaged and 34 undamaged Tohoku images from other regions. Inputs are resized to 600×600. | Article reports fine-tuning a pretrained YOLOv8x segmentation model, but no author checkpoint or dataset download was located in the primary-source search. | A closer bridge-collapse task than SpaceNet 8, but earthquakes/tsunami and training scale remain a domain shift from Ahr/BC floods. Follow up for original data and checkpoint if structural bridge classification becomes approved work. |
| [CAU-RoadDamage](https://doi.org/10.1016/j.jag.2024.103985) | Pixel-level damaged-road segmentation from high-resolution satellite imagery after earthquake. | Author paper proposes the satellite-image road-damage dataset. The sources checked did not establish a public downloadable pretrained checkpoint, public labels, and terms in a single reusable package. | Unverified for download/license in this review. | Worth revisiting for satellite geometry, but earthquake-road failures do not directly validate flood washout, and available model/data status is unresolved. |
| Vehicle-camera datasets such as [RDD2022](https://arxiv.org/abs/2209.08538) | Pavement cracks, potholes, and surface defects from close-range road images. | Thousands of ground-level images from multiple countries; not overhead post-disaster imagery. | Public dataset/research exists, but the camera angle and label semantics do not fit this use. | Exclude as a transfer model for bridge collapse or flood washouts. |

### RescueNet: promising UAV labels, unresolved data access and license

[RescueNet](https://pmc.ncbi.nlm.nih.gov/articles/PMC10733412/) is a useful
spatial-label complement to SpaceNet 8. It contains 4,494 post-Hurricane
Michael UAV images at 3,000×4,000 pixels, with pixel-level classes for four
building states (no/minor/major/total destruction) and road-clear/road-blocked.
The paper defines blocked roads as obstructed by floodwater, sand, or debris;
this is an access-obstruction label, not a structural road-washout class. It
is closer to current access disruption than image-level LADI tags, but low-
altitude drone views remain a sensor/scale shift from satellite or orthophoto
imagery. The paper's 80/10/10 split is allocated by image-level damage strata
and does not document geographic grouping, so spatially adjacent views may
cross splits. FloodNet is also UAV scene segmentation, but its cited labels
distinguish flooded/non-flooded areas rather than road obstruction or building
damage grades.

The authors' [GitHub repository](https://github.com/BinaLab/RescueNet-A-High-Resolution-Post-Disaster-UAV-Dataset-for-Semantic-Segmentation)
contains MIT-licensed segmentation source and training/evaluation code; its
36-file tree contains no `.pt`, `.pth`, `.ckpt`, or safetensors weights. The
[Figshare collection](https://springernature.figshare.com/collections/RescueNet_A_High_Resolution_UAV_Semantic_Segmentation_Benchmark_Dataset_for_Natural_Disaster_Damage_Assessment/6647354/1)
lists segmentation train/validation/test archives (18.70 GB, 2.37 GB, and
2.39 GB) and an image-classification descriptor. Figshare item metadata
declares CC0, while the authors' dataset README says CC BY-NC-ND; this license
conflict is unresolved. Metadata lists public archive assets, but direct HTTP
HEAD checks of all three archive URLs returned 403, so byte-level access was
not verified. The paper text is CC BY 4.0, which does not resolve the dataset
license conflict. Do not download or integrate this dataset until the authors
clarify the applicable data terms; no pretrained author checkpoint was found
for immediate inference.

### Bounded access checks

The direct checks on 2026-10-03 requested only bytes 0–63; no large imagery or
archives were fetched. The three first-place SpaceNet checkpoint links and
three SN8 data archives all returned HTTP 206 with byte-range lengths above.
The MITLL small-reference checkpoint returned HTTP 206 (94,116,688 bytes).
Hugging Face model API reports `MITLL/LADI-v2-classifier-small-reference`
revision `6ba5a0300601284bc6b69dddb46c8991a8ac196c`; its public model and data
APIs did not request a token. The ScienceDB links did not expose direct archive
files through bounded requests, so availability beyond the share-page shells
remains unverified.

The first-place SpaceNet links used were:

- `http://ohhan.net/wordpress/wp-content/uploads/2022/08/best_flood.pt`
- `http://ohhan.net/wordpress/wp-content/uploads/2022/08/best_road.pt`
- `http://ohhan.net/wordpress/wp-content/uploads/2022/08/best_building.pt`

The data links used were the official S3 objects:

- `https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Germany_Training_Public.tar.gz`
- `https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Louisiana-East_Training_Public.tar.gz`
- `https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/tarballs/Louisiana-West_Test_Public.tar.gz`

## LADI reference model details and reproducible mini-test

The small reference model uses `BitForImageClassification` (BiT-50),
23.5 million parameters, RGB input, and multi-label sigmoid outputs. Its
Hugging Face `config.json` fixes this output order:

| Index | Label |
| ---: | --- |
| 0 | `bridges_any` |
| 1 | `buildings_any` |
| 2 | `buildings_affected_or_greater` |
| 3 | `buildings_minor_or_greater` |
| 4 | `debris_any` |
| 5 | `flooding_any` |
| 6 | `flooding_structures` |
| 7 | `roads_any` |
| 8 | `roads_damage` |
| 9 | `trees_any` |
| 10 | `trees_damage` |
| 11 | `water_any` |

The matching `preprocessor_config.json` converts to RGB, resizes the shortest
edge to 448 px, center-crops 448×448, rescales byte values by 1/255, then
normalizes each channel with mean and standard deviation 0.5. Use the
Transformers `AutoImageProcessor` from the same pinned revision rather than
reimplementing these transforms.

The Hub's public `/rows` API can retrieve test images and labels without
downloading the roughly 10 GB full dataset. Its pinned test view reports 1,049
rows, versus 1,041 in the paper; the reason for the count difference is
unresolved. The benchmark script checks that all row indices 0–1048 are
returned and that each cached image URL path carries the expected dataset
revision. The API returns temporary signed image URLs; the script uses them
only in memory and never writes them into metadata or logs.

The earlier inspected 10-row slice (rows 204–213) had one `roads_damage=true`
label at row 209 and nine negatives. The reproducible benchmark does not use
that slice: it selects 100 row indices with seed 42 from the full test split,
without label-based filtering, then stores exact labels and SHA-256 hashes for
that fixed sample. The small sample is not a meaningful performance estimate;
all per-class support counts and the selected row IDs are recorded.

### Reproducible LADI benchmark preparation

[`scripts/benchmark_ladi.py`](../scripts/benchmark_ladi.py) prepares the pinned
small-reference checkpoint and seed-42 sample. Run it from the repository root
with the optional `damage-research` environment:

```sh
./.venv/bin/python scripts/benchmark_ladi.py
```

Preparation downloads the 94 MB model snapshot, pages through all 1,049 test
metadata rows, chooses 100 positions independently of their labels, and caches
the selected public JPEGs under ignored `data/damage-research/ladi/`. Its
manifest records model and dataset revisions, class order, author preprocessing
recipe, row IDs, image hashes, and human labels; temporary signed URLs are not
stored. The runner defaults to preparation only. `--run-inference` opts into
CUDA inference, applies independent sigmoids with a predeclared 0.5 threshold,
and writes every sample's scores, per-class confusion metrics/support, and a
contact sheet of all 100 images. Precision and recall are null when their
denominators are zero; F1 is null only when `2*TP+FP+FN` is zero. After a
successful inference, the runner publishes the local all-image gallery and
copies the metrics, predictions, manifest, contact sheet, and 100 JPEGs into
`artifacts/damage-research/ladi/`. Regenerate and revalidate that local output
without another model run with:

```sh
./.venv/bin/python scripts/benchmark_ladi.py --render-only
```

Once prepared, the inference flag reuses the
manifest and locally cached files: it checks the pinned dataset/model identifiers,
model config, weight SHA-256, fixed row selection, labels, and each JPEG SHA-256
without paging the slow Dataset Viewer again. To run it when a CUDA slot is
available, use `./.venv/bin/python scripts/benchmark_ladi.py --run-inference`.
The CUDA run completed on an NVIDIA GeForce RTX 3080 Laptop GPU (16 GB), with
model parameters, inputs, and logits verified on `cuda:0`. Batch size was 8;
the measured synchronized forward passes took 0.758 seconds total (131.9
images/s) and peaked at 573,697,536 allocated bytes. This timing excludes image
decode and processor work.

On this fixed random 100-row sample, only 2 examples are positive for
`roads_damage`: TP=1, FP=0, FN=1, TN=98, precision=1.00, recall=0.50, F1=0.667,
and accuracy=0.99. The apparently high precision is based on a single predicted
positive; the two positive examples make these figures highly uncertain and
not a performance estimate. They do not replace the paper's reported full-test
F1 of 0.17 for its larger model. See the [local all-100 image gallery and
metrics](../artifacts/damage-research/ladi/index.html), its [contact
sheet](../artifacts/damage-research/ladi/contact-sheet-all-100.png), or the
[per-image predictions](../artifacts/damage-research/ladi/predictions.json).
The gallery includes local copies of the 100 source images and license
attribution; no URLs or images are served remotely.

The paper reports the test set is 2023-only and its reference model uses only
the training split, so the test labels are not in that checkpoint's training
data. The reference-model card explicitly says training split only; its 2015–22
train period is separate from the 2023 test period. Do not evaluate with the main small model: the model card says that
deployment model was trained on all three splits. Also preserve the authors'
reported limitation: LADI supports only image-level multi-label
classification, its imagery is U.S.-specific, and its test distribution shifts
by event, geography, camera, and hazard type.

## Current-event evidence for the approved cases

### Ahr Valley, Germany

FloodBeacon's configured case is `[6.88, 50.37, 7.17, 50.59]` and uses
Copernicus EMS activation EMSR517 AOI15. The configured vector product is
`EMSR517_AOI15_GRA_PRODUCT_r1_RTP01_v1_vector.zip`, with product metadata dated
2021-07-19 and map scene time 2021-07-18T10:50Z. Keep these as agency
assessments and observe the time limitations in the product; they are not model
outputs.

The independent RWTH bridge study mapped 114 Ahr bridges and defines five
grades: D0 intact, D1–D3 damaged at increasing severity, D4 destroyed or later
demolished. It draws on satellite/aerial imagery, bridge-operator records,
2021 field inspections, and more detailed inspections in March/April 2022.
Fifteen bridges could not be examined in detail due to destroyed bridges and
access restrictions. The study's data statement says its bridge data are
available from the corresponding author upon reasonable request. This is a
valuable independent label lead, but spatially match bridge IDs and inspection
dates to AOI15 and imagery before evaluating a model. Do not treat all bridges
outside the survey as intact.

### Merritt / Highway 8, British Columbia

The Province reports the November 2021 atmospheric river damaged 24 sites along
Highway 8 between Spences Bridge and Merritt. The Ministry's corridor
reinstatement plan states that over 7 km of the two-lane highway was completely
lost. Those are strong agency facts for a road-disruption demonstration; they
do not establish a public, pixel-aligned training label set. The records are
repair/site reports, not a validated bridge-collapse image benchmark. Keep the
bridge inventory as map context and attribute any repair observations to the
Province.

## Suggested experiment boundaries

1. **Road disruption baseline:** reproduce the pretrained SpaceNet 8
   flood-attribution prediction on its published Germany tiles, compare masks
   against held-out contiguous geography where available, and separately score
   the public human road labels. Report road-water-or-rubble attribution, not
   structural failure. Pin and checksum the full checkpoint only when this
   experiment is selected.
2. **Ahr transfer check:** overlay predictions only after proving exact source
   tile/date coverage for EMSR517 AOI15 and documenting whether the pretrained
   checkpoint's training used those same AOI tiles. Treat the EMSR product and
   RWTH bridge grades as retrospective agency/field references with their own
   observation times.
3. **BC evidence check:** use the official Highway 8 damaged-site records and
   dated imagery as a small manually reviewable case set. First confirm imagery
   resolution and dates cover the listed sites. Keep unknown/occluded sites
   unknown. A flood exposure signal alone must not become a damage or closure
   label.
4. **Bridge collapse model:** seek data/checkpoint access from the 2026
   orthophoto and bridge-segmentation authors, and request permission/access to
   RWTH's Ahr bridge-level grades. Before adapting either model, require
   geographically separated evaluation and explicit flood-specific labels.
   Available research evidence does not yet justify adding a pretrained bridge
   collapse detector to FloodBeacon.

These are research recommendations only. They do not add a damage model to the
current implementation or authorize changing the product's label semantics.

## Primary sources

- SpaceNet 8: [official challenge and data access](https://spacenet.ai/sn8-challenge/), [author baseline and Apache-2.0 code](https://github.com/SpaceNetChallenge/SpaceNet8), [CVPR EarthVision paper](https://openaccess.thecvf.com/content/CVPR2022W/EarthVision/papers/Hansch_SpaceNet_8_-_The_Detection_of_Flooded_Roads_and_Buildings_CVPRW_2022_paper.pdf), and [first-place checkpoint instructions](https://github.com/SpaceNetChallenge/SpaceNet8/blob/main/01-ohhan777/code/README.md).
- LADI: [MITLL dataset overview](https://github.com/LADI-Dataset/ladi-overview), [LADI v2 paper](https://arxiv.org/html/2406.02780), [small reference model card](https://huggingface.co/MITLL/LADI-v2-classifier-small-reference), and [public labelled dataset](https://huggingface.co/datasets/MITLL/LADI-v2-dataset).
- Bridge-and-road orthophoto classification: [2026 paper](https://link.springer.com/article/10.1007/s43503-026-00108-7), [author code repository](https://github.com/ZhengStone/Bridge-and-Road-Damage-Detection), [linked source-data share](https://www.scidb.cn/s/bURze2), and [linked result share](https://www.scidb.cn/s/UfUBz2).
- Bridge segmentation after Japanese earthquakes: [Kubo, Zheng & Chun, 2026](https://doi.org/10.1680/jfoen.25.00025).
- Ahr bridge evidence: [Burghardt et al. (RWTH author-hosted open paper)](https://publications.rwth-aachen.de/record/987861/files/987861.pdf) and [Ahr field-survey dataset metadata](https://research.tudelft.nl/en/datasets/post-flood-field-survey-of-the-ahr-valley-germany/). The TU Delft photo survey documents buildings and water levels, not bridge damage labels.
- British Columbia: [Highway 8 flood-recovery records](https://www2.gov.bc.ca/gov/content/transportation-projects/bc-highway-flood-recovery/2021-flood-road-recovery-projects-highway-8) and [Ministry corridor reinstatement plan](https://www2.gov.bc.ca/assets/gov/driving-and-transportation/transportation-infrastructure/contracting-with-the-province/documents/26355-0001/sched_t3-3_-_highway_8_corridor_re-instatement_water_management_plan.pdf).
- Satellite road damage lead: [CAU-RoadDamage, Journal of Applied Geoinformation](https://doi.org/10.1016/j.jag.2024.103985).
