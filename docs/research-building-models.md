# Research: identifying existing building damage

Checked 2026-10-03 using author repositories, papers, model cards and host APIs.
This report concerns post-event damage inference, not future failure prediction.
Building research and local evaluation are authorized; adding building predictions
to the product/API still needs a scope decision. CUDA environment installation is
coordinated by the parent task. Availability checks below do not constitute
accuracy verification; the final section separately records actual CUDA execution.

## Recommended evaluation order

1. **BRIGHT's event-excluded Libya UNet** is the best immediate, labeled CUDA
   experiment. Its author checkpoint is small, its architecture requires only
   PyTorch, and public real optical/SAR imagery and damage labels exist. This
   evaluates actual damage classes on a flood event outside the stated training
   event set, rather than relabeling water as damage. It requires submeter imagery.
2. **ETH xBD-S12** is the strongest practical candidate for the eventual freely
   available Sentinel workflow. It is a building damage model, with coarser
   intact/damaged classes. A good labeled benchmark requires original xBD labels;
   the public Sentinel archive alone is insufficient. Match its preprocessing
   before evaluating transfer to Ahr/BC.
3. **ChangeOS Swin-T** is a convenient high-resolution paired-RGB damage baseline
   if lawful xBD samples or appropriate local imagery become available. Public
   author weights are much easier to reproduce than many legacy challenge models.

These are complementary input regimes. A good submeter BRIGHT result does not
establish performance on 10 m Sentinel imagery, and a building detector does not
establish road closure, bridge collapse, or structural safety.

Compare the UNet against **BRIGHT SiamAttnUNet** on exactly the same selected
Libya tiles. This second author model is also torch-only and adds separate
modality encoders and channel attention. It gives a useful architecture comparison
without introducing a custom CUDA kernel or an incompatible input regime.

## Candidates and practical limitations

| Candidate | Inputs and output | Reproduction/access | Decision |
| --- | --- | --- | --- |
| [BRIGHT author UNet](https://zenodo.org/records/15349462) | Pre-event RGB plus post-event single-band VHR SAR; four pixel classes: background, intact, damaged, destroyed | Native torch-only network; public 124 MB Libya event-excluded weights and real labels | First local CUDA benchmark; no Sentinel transfer claim |
| [ETH xBD-S12](https://github.com/prs-eth/xbd-s12) | Pre/post Sentinel-1 VV/VH and all 12 Sentinel-2 L2A bands; background, intact, damaged | Two small public MIT models; minimal inference can bypass acquisition/GDAL dependencies | Best next candidate for free global imagery |
| [ChangeOS Swin-T](https://huggingface.co/EVER-Z/torchange_example_changeos_swint_on_xview2_best42k) | Six channels: pre/post high-resolution RGB; localization plus no/minor/major/destroyed damage | Public Apache-2.0 safetensors; stable torchange 0.0.4 strictly loads this checkpoint | Reproducible VHR baseline; require matched imagery and independent labels |
| [ChangeMamba/MambaBDA](https://github.com/ChenHongruixuan/ChangeMamba) | VHR paired damage assessment; architecture also adapted to BRIGHT optical/SAR | Public BRIGHT weights, but custom selective-scan CUDA compilation and old timm recipe | More migration work than the plain UNet; not first smoke test |
| [DisasterAdaptiveNet](https://github.com/SebastianHafner/DisasterAdaptiveNet) | VHR pre/post RGB and disaster conditioning; four damage grades | Author Google Drive weights and event-separated splits; legacy Python recipe, no repository license file found | Valuable event-generalization comparator after access/rights checks |
| [HOTOSM DINOv3 damage model](https://huggingface.co/hotosm/earthquake-damage-assessment-model) | Building footprints plus post RGB, optionally aligned pre RGB; four building-level grades | Public ONNX/Lightning weights, ~1.3–1.5 GB each; noncommercial share-alike model terms | Interesting operational output, but larger and benchmark remains in-event |
| [2026 BRIGHT challenge winners](https://github.com/ChenHongruixuan/BRIGHT/blob/master/cvprw26/README.md) | Instance-level VHR optical/SAR: intact, damaged, destroyed | First winning repository returned 404; second was empty at live check | Published method leads, not verified usable checkpoints |

## Exact first experiment: BRIGHT UNet

Use author code pinned to Git commit
`59269142f3a3550320513e362692732f46486985`. The
[model source](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/model/UNet.py)
is a conventional five-level UNet with encoder widths 64, 128, 256, 512, 1024,
double Conv/BatchNorm/ReLU blocks, transposed-convolution upsampling, skip
concatenation and a four-channel final convolution. Instantiate `UNet(6, 4)`;
an SMP UNet is a different architecture and must not be substituted.

The [author dataset loader](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/dataset/make_data_loader.py)
takes the first three pre-event optical channels, replicates the single SAR
post-event band into three channels, normalizes each image, and concatenates
pre then post. The [normalization function](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/dataset/imutils.py)
uses `(pixel - mean) / std`, with mean `[123.675, 116.28, 103.53]` and std
`[58.395, 57.12, 57.375]`. Do not replace this with dB conversion, local contrast
stretching, or per-image statistics. The released post-event SAR is already a
processed image for this recipe, rather than raw Sentinel VV/VH.

The [author inference source](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/script/standard_ML/infer_UNet.py)
loads a plain state dictionary and takes the four-class argmax. Start with
`torch.load(..., weights_only=True, map_location="cpu")`, strict key/shape loading,
`model.to("cuda").eval()`, and `torch.inference_mode()`. Assert CUDA availability,
device of model/input, and record peak GPU memory and synchronized timing. Batch
one in FP32 is the fidelity baseline; reduced precision and tiled inference need
separate checks. No training or runtime image download belongs inside API GETs.

The pinned cross-event
[training source](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/script/cross_event/zero_shot/train_SiamCRNN.py)
removes the target event from both training and validation. It pools that event's
train/validation/test tiles for target testing, trains using the remaining source
events, and selects weights by source validation mIoU. The exact UNet zero-shot
training script/log is not present, so this is evidence for the stated author
protocol, not an independent audit of that particular checkpoint's training.

Select sample IDs before seeing model outputs; keep per-tile confusion matrices
and class support alongside pooled scores. Count false positives outside the
reference footprints. Pixel accuracy alone is misleading because background can
dominate. A handful of tiles is a compatibility and local behavior study, not an
event-wide estimate. Do not alter thresholds based on the same tiles used to
report metrics. Retain geometry, nodata, alignment and acquisition times.

### Second experiment: SiamAttnUNet

The pinned [author class](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/model/SiamAttnUNet.py)
imports torch only. Instantiate `SiamAttnUNet(3, 4)` and call
`model(normalized_pre_rgb, normalized_replicated_post_sar)` with two inputs.
It uses two distinct five-stage encoders, five 1×1 feature fusions, and
decoder-conditioned channel attention. The checkpoint is a plain state dict:
`ckpt_SiamAttnUNet_cross_event_zeroshot_libya-flood.pth`, 243,965,300 bytes,
author MD5 `20459d94aa13fc85aa40d6b90340a98f`, in
[Zenodo record 15349462](https://zenodo.org/records/15349462).

Full 1024×1024 FP32 batch-one inference is the correct first attempt on the
available 16 GB GPU; memory sufficiency remains an estimate until measured.
Use inference mode, not training/autograd. Attention uses global average and
maximum pooling, so tiled inference changes the context and cannot be claimed
equivalent to the full-tile author recipe. If memory requires a different recipe,
report it as a separate experiment. The
[author inference script](https://github.com/ChenHongruixuan/BRIGHT/blob/59269142f3a3550320513e362692732f46486985/bda_benchmark/script/standard_ML/infer_SiamAttnUNet.py)
normally runs without TTA; its unused TTA helper passes concatenated single input
to a two-input model in several branches. Avoid that helper.

[Published Table 10](https://essd.copernicus.org/articles/17/6217/2025/essd-17-6217-2025-t10.xlsx)
reports Derna/Libya zero-shot event mIoU of 33.25% for UNet and 33.76% for
SiamAttnUNet; the corresponding one-shot scores are 38.44% and 42.15%.
DamageFormer and ChangeMamba zero-shot results are 36.27% and 37.02%. These are
author event-level semantic results, not FloodBeacon measurements. The zero-shot
protocol pools all target-event split members, so a small sample or the 26
official standard-test tiles is not the complete author event evaluation.

## ETH xBD-S12 inference details

The [author model class](https://github.com/prs-eth/xbd-s12/blob/ebda30e8c976a71a9062795a278ac398db180148/src/models/unet.py)
imports torch, segmentation-models-pytorch and huggingface-hub. It wraps an SMP
ResNet34 UNet with an extra two-convolution block and separate segmentation head.
The checked seed1 configs use depth 3, decoder widths `[256,128,64]`, no decoder
normalization, 28 input channels and one localization or three damage outputs.
Strictly loading its safetensors will detect modern library architectural drift.
The current author's full environment includes more acquisition/training tools
than this adapter needs; do not copy its old GDAL pin into FloodBeacon.

The [current inference source](https://github.com/prs-eth/xbd-s12/blob/ebda30e8c976a71a9062795a278ac398db180148/src/inference/from_hub.py)
uses 128-pixel patches, 32-pixel border padding and a 64-pixel stride. It normalizes
each band using checkpoint 1st/99th percentiles, clipped to `[0,1]`, concatenates
S1-pre, S2-pre, S1-post, S2-post, and averages logits across seeds. Localization is
sigmoid >0.5; damage is argmax over intact/damaged channels, then masked by
predicted localization. The README names an obsolete file/method; use
`from_hub.py` and `run_inference` or an explicit array adapter.

The [dataset description](https://github.com/prs-eth/xbd-s12/blob/ebda30e8c976a71a9062795a278ac398db180148/DATASET.md)
specifies S1 VV/VH in dB and S2 original reflectance scale. Native Sentinel samples
are interpolated to about 4 m; interpolation does not create submeter detail.
Record orbit direction, cloud validity, coregistration and spectral band order.
Our existing Planetary Computer RTC gamma-naught inputs are not the authors'
GEE GRD preprocessing, and a TCI-only RGB file lacks the required S2 bands.
S2 scale/offset handling must match actual source processing baselines.

The [paper](https://arxiv.org/html/2511.05461v2) evaluates both random tiles and
event-separated splits and merges all three positive damage grades. Random splits
share disasters across training/test; they cannot establish unseen-event accuracy.
Its Palisades example is independent qualitative assessment. Public HF seed cards
do not identify their training split, so do not automatically attach the paper's
event-heldout performance to a downloaded seed checkpoint.

The public [Zenodo archive](https://zenodo.org/records/18960454) contains Sentinel
patches (9,523,531,926 bytes) and original tiles (11,023,654,343 bytes), declared
CC BY 4.0. The [author README](https://github.com/prs-eth/xbd-s12/blob/ebda30e8c976a71a9062795a278ac398db180148/README.md)
requires downloading original xBD labels separately; the Sentinel archive alone
does not produce a labeled damage evaluation. Original xView2 download access
and applicable terms need the user's account if selected.

## ChangeOS and newer alternatives

The checked [ChangeOS card](https://huggingface.co/EVER-Z/torchange_example_changeos_swint_on_xview2_best42k)
reports a 76.91 mixed F1 on `hold`, with per-grade F1 89.39/58.03/72.75/81.25.
These are author results, not FloodBeacon measurements. Training uses
`train+tier3`, selection uses `test`, and final reporting uses `hold`, all from the
xView2 protocol. Input is ImageNet-normalized pre/post RGB, six channels. Its
41.5 M parameter Swin-T model returns a footprint score and five-class damage
scores. Apply the footprint constraint without batch-broadcast mistakes.

Current [torchange source metadata](https://github.com/Z-Zheng/pytorch-change-models/blob/190b07a2eb4c389a5dc3f72802c67f428cdfd6b7/pyproject.toml)
supports Python 3.14 but imports data/metrics modules eagerly; inference installation
therefore pulls datasets, albumentations, ever-beta, timm, torchvision and other
packages. Actual inspection of the latest stable
[torchange 0.0.4 wheel](https://pypi.org/project/torchange/) showed that it contains
the same required ChangeOS architecture and output class. Its HF loading API is
inherited through `ever-beta`'s `ConfigurableMixin`, not a method written directly
on ChangeOS. The checked [ever-beta 0.6.1 wheel](https://pypi.org/project/ever-beta/)
does contain that mixin and the auto-configuration behavior needed by torchange.
There is no established need to install unreleased Git source just for this model.

The author's [HF xView2 copy](https://huggingface.co/datasets/EVER-Z/torchange_xView2)
is ungated and contains masks, but has no explicit dataset license. Its viewer
returned HTTP 501 because a parquet row group exceeded the server size limit.
This is neither a permission grant nor a convenient small-example endpoint.
Prefer the original labeled release with reviewed terms or the BRIGHT experiment.

The [HOTOSM model card](https://huggingface.co/hotosm/earthquake-damage-assessment-model)
describes DINOv3 ViT-L/16 with UperNet, four object-level grades and calibrated
temperature 1.1719. Its validation uses 6,166 buildings and same-event tile splits.
There is also a Nepal flood fine-tuned checkpoint; no separate documented flood
evaluation was found. Calibration on one validation distribution is not guaranteed
after transfer. The card declares CC BY-NC-SA 4.0 for the model itself.

The [2026 challenge outcome paper](https://arxiv.org/abs/2607.22746) reports winner
new-event mAPs 0.182/0.181, far below the best in-domain 0.513. Those instance mAPs
cannot be compared directly to semantic F1. Live repository checks found the
advertised first-place code unavailable and second-place repository empty;
published results do not establish downloadable checkpoints.

## Pinned assets and rights

| Asset | Revision/checksum/size | Access and rights |
| --- | --- | --- |
| BRIGHT Libya zero-shot UNet | Zenodo record 15349462; `ckpt_UNet_cross_event_zeroshot_libya-flood.pth`; MD5 `21675d18425db0b8b5b3ccfc8f74b30e`; 124,274,886 bytes | Public author record declares CC BY 4.0 for weights; code Apache-2.0 |
| ETH localization seed1 | Revision `00cc5ce9db424038d7f6bac62135f69563a19cf1`; host LFS SHA256 `3e3317efb138f5b8cc93ec4b9ba75628418430526aad3234464e36a3841bfcf8`; 92,630,268 bytes | Ungated MIT model card/code |
| ETH damage seed1 | Revision `93c76784f3eac6f67ef19920b6f33fe4428edf5c`; host LFS SHA256 `4b5e3d293db52254f29c851fb57a2ce4a02252f95e88c7bf770269ebd21c94a0`; 92,630,788 bytes | Ungated MIT model card/code |
| ChangeOS Swin-T | Revision `4007dd10c5eaee67161e2d4a45a43da3ead6c722`; 166,117,752 bytes | Ungated Apache-2.0 model/code; data separately licensed |
| HOTOSM ONNX | Revision `7869af2b84a05680d6d55fd212415ce6a586befe`; host LFS SHA256 `056bea7550f82d7d87d376f7843143bbf5e25d570c24eea7ff1aa3267e575e06`; 1,316,955,782 bytes | Ungated CC BY-NC-SA 4.0 model card |

Host checksums are metadata assertions until matched against a complete local
download. Save computed SHA256, URL, revision, retrieval time and preprocessing
alongside actual experiments. The complete ChangeOS checkpoint was subsequently
downloaded for the CUDA experiment below: its computed SHA256 matches
`81ae6386ceebe225ab6c072cb987b57312fdcfdb2a7f72ab9b30e5e8f1041cc4`.

BRIGHT's [author data card](https://huggingface.co/datasets/Kullervo/BRIGHT)
specifies per-event rights: most pre-optical imagery and corresponding labels are
Maxar CC BY-NC 4.0; Hawaii and La Palma have different providers; SAR is CC BY 4.0.
Its umbrella metadata and Zenodo record labels do not erase these component
terms. Libya is appropriate for local noncommercial research, with source
attribution and ignored local artifacts. A commercial production decision needs
explicit review of actual input and model terms. No account was required for the
BRIGHT/HF metadata or model access checks here.

## Ahr and BC implications

Neither the downloaded checkpoints nor benchmark numbers prove performance in
Ahr July 2021 or Merritt November 2021. Sentinel-class inputs can cover both,
but scene-level preprocessing and independent *building* damage references are
needed before any score. Our imported Ahr transportation assessments are useful
for roads/bridges; they are not building ground truth. BC's current bridge inventory
is not a historical damage label set.

For VHR ChangeOS/BRIGHT, verify paired submeter imagery over the study footprint
and post-event acquisition dates before claiming a feasible case transfer. CEMS
derived vectors do not grant access to the analyst's underlying commercial images.
If no suitable imagery/reference pair exists, report that limit and evaluate on
the lawful benchmark first. Road and bridge damage require their own detector,
labels and validation; building model success is not a substitute.

## Additional Ahr paired-RGB experiment recipe

The dataset researcher retrieved a public, matched 1024×1024 0.4 m orthophoto pair
in EPSG:25832, stored locally under `data/research/ahr-vhr-pre-2019.tif` and
`ahr-vhr-post.tif`. The pre-event image is acquired 2019-06-27; the post-event
official mosaic uses late-July 2021 acquisitions. Exact provenance/checksums and
pixel validity belong in the dataset manifest and experiment report. This is
independent real case imagery, not original xBD samples and not submeter satellite
imagery from the checkpoint's training distribution.

For the standalone diagnostic script, use stable torchange 0.0.4 and ever-beta 0.6.1, whose
PyPI registries and wheel contents were verified live. Download model config and
safetensors at revision `4007dd10c5eaee67161e2d4a45a43da3ead6c722`. Explicitly set
`config['encoder']['params']['weights'] = None` before constructing
`ChangeOS(config)`, then restore the complete safetensors with strict loading.
The author `TVSwinTransformer` default passes the `Swin_T_Weights` enum class;
modern torchvision expects a selected enum value or `None`. Supplying `None`
avoids that constructor issue and an unnecessary ImageNet checkpoint download;
strict loading then restores all trained backbone weights.

Read RGB only, preserve a joint alpha/nodata validity mask, use
`(RGB / 255 - [0.485,0.456,0.406]) / [0.229,0.224,0.225]` independently for both
dates, and concatenate pre then post. Verify CUDA model/input placement. The
output already contains sigmoid localization and softmax damage scores; do not
apply softmax again. Localization shape `(B,1,H,W)` should be squeezed to
`(B,H,W)` before masking the damage argmax. Invalid pixels must remain unknown,
not be converted to intact/background.

The [original xBD release paper](https://arxiv.org/abs/1911.09296) was submitted
in 2019, before the Ahr flood. Under the checkpoint's documented xBD-only training
recipe, Ahr 2021 is therefore an unseen disaster event. This is a temporal
inference from the documented recipe, not a forensic audit of the checkpoint.
An orthophoto domain shift and a two-year pre-event gap remain: intervening
construction/demolition can look like damage, and July 2021 images can reflect
cleanup or later changes. Our July 18 agency transportation assessments do not
provide same-time building ground truth for this later acquisition. Prediction
maps can demonstrate inference but cannot establish Ahr building accuracy without
matching independent labels.

### Verified CUDA execution and sampling correction

`scripts/predict_changeos_ahr.py` implements the pinned recipe, requires CUDA,
asserts model/input/output CUDA placement, strictly restores the author checkpoint,
and preserves unknown pixels. It writes projected class/score GeoTIFFs, WGS84
prediction-area GeoJSON, a four-panel image and a provenance report. It does not
publish an API run. Model runtime warnings concern upstream `torch.jit.script`
deprecation under Python 3.14; the actual forward pass completed successfully.

The original crop near 7.069°E, 50.5433°N was inspected visually after inference
and found to be forest without visible buildings. Its final predicted map is
entirely background; this cannot establish building-detection accuracy or a
transfer failure. Retain it as an exploratory background-only crop, rather than
presenting it as the demonstration of damage identification. Raw localization
and damage-head diagnostics are recorded separately from the final class mask.

Run with the existing research environment (avoid altering it while experiments
are active):

```sh
.venv/bin/python scripts/predict_changeos_ahr.py \
  --pre data/research/ahr-vhr-pre-2019.tif \
  --post data/research/ahr-vhr-post.tif \
  --output artifacts/research/changeos-ahr-forest
```

The first full-image FP32 1024×1024 forward took 0.441 seconds with 853,379,584
bytes peak CUDA allocated memory on the NVIDIA GeForce RTX 3080 Laptop GPU.
That is one synchronized local measurement, not a production throughput estimate.
A populated Altenahr crop was then selected at 6.9934°E, 50.5174°N and both dates
were visually inspected for building presence before inference. The metric paired
grid bounds are `[357542.82744040847, 5597878.304765015, 357952.42744040844,
5598287.904765015]` in EPSG:25832, 1024×1024 pixels at 0.4 m. The pre-event
center metadata explicitly dates the flight to 2019-06-28. The post-event center
metadata dates creation to 2021-07-24 and publication to 2021-10-12 07:27:14.024
(timezone unspecified), rather than assigning that creation date as the exact
flight time for each pixel. The statewide special-flight collection describes
late-July acquisitions.

The populated full-image CUDA forward took 0.460 seconds and again used
853,379,584 bytes peak allocated memory. The final map has 154,153 pixels in
predicted no-damage, 4,608 in predicted destroyed, zero minor/major, and 889,815
background; jointly valid raster coverage is 100%. The predicted destroyed pixel
area is about 737.28 m². Its 65 exported contiguous class regions are **not 65
building instances**. Visual inspection shows many roof footprints and localized
red regions near the river. This is a useful qualitative demonstration, with no
matched reference damage labels and no measured damage accuracy. Visible missing
or changed roofs do not by themselves establish the model's grade accuracy.

The standalone script now defaults to this meaningful populated pair:

```sh
.venv/bin/python scripts/predict_changeos_ahr.py
```

Inspect `artifacts/research/changeos-ahr-altenahr/comparison.png` and `report.json`.
The latter contains complete checkpoint/input/output receipts, effective config,
runtime versions, CUDA assertions, separate localization and damage diagnostics,
and processing limitations. Neither road/bridge predictions nor API publication
were added. Independent building labels remain necessary for any accuracy claim.
