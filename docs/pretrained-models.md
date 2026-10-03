# Pretrained models for identifying damage

Checked 2026-10-03 against author repositories, papers and model hosts. No model
in this document has been installed or evaluated in FloodBeacon. Checkpoint
availability means a small byte-range request succeeded, not verified inference
or verified accuracy on the two case studies.

Pretrained damage models exist. The best verified candidates currently assess
**buildings**. Flooded-road models are relevant to access, but their labels do
not establish a destroyed road or bridge. Our search did not establish a
downloadable, appropriately licensed model validated for collapsed bridges from
Sentinel imagery. This is a search outcome, not a claim that such a model cannot
be developed.

## Candidate comparison

| Candidate | Task and inputs | Access checked | Fit for FloodBeacon |
| --- | --- | --- | --- |
| [ChangeOS Swin-T author checkpoint](https://huggingface.co/EVER-Z/torchange_example_changeos_swint_on_xview2_best42k) | Building localization and four damage grades: no damage, minor, major, destroyed. Paired pre/post RGB concatenated into six channels. | Public, ungated Apache-2.0 model card. `model.safetensors` range GET returned HTTP 206; file size 166,117,752 bytes. | Strong candidate for an actual building-damage demo if that scope is approved and suitable high-resolution paired imagery is available. Does not identify bridge destruction. |
| [ETH Zurich xBD-S12 models](https://huggingface.co/collections/prs-eth/xbd-s12) | Building localization and binary damaged/intact classification using paired Sentinel-1 VV/VH plus all 12 Sentinel-2 L2A bands. Separate localization and damage models, three seeds each. | Public MIT model cards; localization and damage seed1 safetensors range GET verified, both HTTP 206. | Most relevant candidate when using freely available Sentinel imagery, if building damage is approved. No separate destroyed class and no bridge labels. |
| [SpaceNet 8 winning solutions](https://github.com/SpaceNetChallenge/SpaceNet8) | Flooded roads/buildings from paired high-resolution optical imagery. Segmentation models include Siamese U-Net and HRNet; these are task-specific pretrained networks. | First-place author's building, road and flood `.pt` links returned HTTP 206. Tested second-place Dropbox links returned HTML rather than checkpoint archives. | A verified pretrained road-inundation option. Cannot be relabeled structural destruction. Requires high-resolution images and adapting the legacy inference pipeline. |
| [xView2 first-place ensemble](https://github.com/DIUx-xView/xView2_first_place) | Building damage from paired high-resolution optical imagery. | MIT code; advertised author S3 weight ZIP returned HTTP 403 in this environment. | A credible published alternative, currently less convenient than the directly downloadable ChangeOS checkpoint. Original training environment is old. |

The [original xBD paper](https://arxiv.org/pdf/1911.09296) targeted imagery below
0.8 m ground sample distance for damage grading. Upsampling Sentinel pixels does
not reproduce those visual details. The high-resolution requirements apply to
the xBD-trained RGB candidates, rather than every damage model.

## Sentinel damage assessment is a real option

The [xBD-S12 paper](https://arxiv.org/html/2511.05461v2) explicitly studies
building damage at Sentinel resolution. It merges minor, major and destroyed
into one damaged class. Inputs are resampled to 128×128 patches at roughly
4 m spacing; this interpolation does not create 4 m sensor detail. It evaluates
event-separated splits because random tile splits can exaggerate generalization.
Published building-damage results do not validate route closure or bridge
collapse in Germany or BC.

The [author dataset description](https://github.com/prs-eth/xbd-s12/blob/main/DATASET.md)
specifies Sentinel-1 in dB and Sentinel-2 reflectance values. A three-band TCI
preview is insufficient for its 28-channel paired input. Acquisition dates,
orbit direction, preprocessing, co-registration and normalization must match
the checkpoint recipe. The [actual inference source](https://github.com/prs-eth/xbd-s12/blob/main/src/inference/from_hub.py)
should be used: the README currently names an inference filename that returns
404 and uses an old method name; the current class exposes `run_inference`.
For our historical cases, independently validate scene coverage and damage
references before displaying predictions as measured performance.

## YOLO and bridge-specific research

[Official YOLO pretrained models](https://docs.ultralytics.com/datasets/detect/coco)
are trained on common object classes. They are suitable starting weights for
custom training; they do not arrive trained to recognize collapsed bridges.
The architecture name alone does not resolve the need for relevant damage
labels and imagery.

[RoadDamageDetector](https://github.com/sekilab/RoadDamageDetector) is based on
road-surface inspection images, including smartphone images captured from cars.
Its cracks and pavement defects are a different visual task from flood washout
in overhead satellite imagery. Likewise, the author
[UAV bridge monitoring project](https://github.com/Jeongseon-Park-1/Long-term-monitoring-of-damage-progression)
uses YOLO segmentation for cracks, spalling and leakage on visible bridge
surfaces. These models should not be applied to Sentinel tiles as bridge-collapse
detectors without new training and validation.

A closer task match is the September 2026 paper
[Automated detection of bridge and road damage in orthophotos](https://link.springer.com/article/10.1007/s43503-026-00108-7).
It reports binary damage classification on orthophotos from the 2011 Japanese
earthquake. Its [author repository](https://github.com/ZhengStone/Bridge-and-Road-Damage-Detection)
contains training/testing code, but our recursive file inventory found no
trained checkpoint or license file. The paper links external data/results
archives; their checkpoint content and reuse terms remain unverified. This is
a research lead requiring author/archive follow-up, rather than an immediately
verified pretrained integration.

## Accounts, rights and runtime

- ChangeOS and the checked ETH Hugging Face checkpoints are ungated; their
  small range downloads required no account or token. Model-card licenses are
  Apache-2.0 and MIT respectively, and their code repositories carry the same
  respective licenses. Preserve the notices and attribution.
- xBD training imagery/labels have separate terms. The
  [ETH repository](https://github.com/prs-eth/xbd-s12) explicitly says it cannot
  redistribute the original VHR imagery and labels. The
  [official xView2 baseline](https://github.com/DIUx-xView/xView2_baseline)
  instructs users to register/login for data. We did not verify current dataset
  terms through its JavaScript-only portal. A code/model license must not be
  treated as permission to redistribute all training imagery.
- [SpaceNet 8](https://spacenet.ai/sn8-challenge/) provides public imagery without
  an AWS account and identifies a CC BY-SA 4.0 dataset license. Its code has
  Apache-2.0 licensing. Neither public data nor public source code guarantees
  that an old pretrained checkpoint link still works.
- [PyPI Torch metadata](https://pypi.org/pypi/torch/json) reports stable Torch
  2.14.1 and Python 3.14 wheels. This removes an interpreter-level reason to
  downgrade FloodBeacon. No GPU or end-to-end model runtime has been checked.
- The current [torchange source metadata](https://github.com/Z-Zheng/pytorch-change-models/blob/main/pyproject.toml)
  declares Python 3.14 support. Its PyPI 0.0.4 distribution has older dependency
  metadata, so verify that the selected distribution contains the model-card
  API before adding it. The original ChangeOS repository pins Torch 1.10;
  those legacy instructions are not a suitable direct install recipe here.
- The [ETH source metadata](https://github.com/prs-eth/xbd-s12/blob/main/pyproject.toml)
  accepts Python ≥3.12 but includes an old GDAL 3.6.2 pin and acquisition/training
  dependencies. A minimal inference adapter should identify the actual imports
  required before copying the entire environment. Python 3.14 end-to-end
  compatibility remains unverified.

## Reproducible checkpoint checks

| Checkpoint | Revision | Result |
| --- | --- | --- |
| `EVER-Z/torchange_example_changeos_swint_on_xview2_best42k` | `4007dd10c5eaee67161e2d4a45a43da3ead6c722` | Ungated; config and safetensors returned HTTP 206 for `Range: bytes=0-63`. |
| `prs-eth/xbd-s12_loc_seed1` | `00cc5ce9db424038d7f6bac62135f69563a19cf1` | Ungated; safetensors returned HTTP 206, 92,630,268 bytes total. |
| `prs-eth/xbd-s12_dmg_seed1` | `93c76784f3eac6f67ef19920b6f33fe4428edf5c` | Ungated; safetensors returned HTTP 206, 92,630,788 bytes total. |

The [first-place SpaceNet 8 README](https://github.com/SpaceNetChallenge/SpaceNet8/blob/main/01-ohhan777/code/README.md)
links `best_building.pt`, `best_road.pt` and `best_flood.pt` under
`http://ohhan.net/wordpress/wp-content/uploads/2022/08/`. Each returned HTTP 206
for the same byte-range check without credentials. Their legacy code describes
four-GPU inference; actual CPU/GPU performance and modern dependency compatibility
remain unchecked.

Pin a verified revision and checksum the full weights when implementing.
Only 64-byte samples were retrieved; full checkpoint checksums are not available
yet.

The recommended next choice is whether to add **automated building damage**
using ChangeOS or xBD-S12, or retain **roads/bridges** as the exclusive damage
scope and pursue bridge-specific imagery, labels and author checkpoints. That
changes the product scope and needs the user's decision. It does not require
replacing the existing flood exposure layers or agency damage evidence.
