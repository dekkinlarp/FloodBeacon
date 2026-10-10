# Supervised water baseline

FloodBeacon trains a small CPU Random Forest on real **hand-labeled**
[Sen1Floods11 v1.1](https://github.com/cloudtostreet/Sen1Floods11) imagery.
[The authors' documentation](https://github.com/cloudtostreet/Sen1Floods11/blob/master/docs/README.md)
distinguishes these labels from Otsu/optical weak labels.
[The published paper](https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPRW_2020_paper.html)
describes the dataset. Attribution: Bonafilia, Tellman, Anderson and Issenberg
(2020), Cloud to Street. The authors publicly provide research downloads, but
the [official label catalog](https://storage.googleapis.com/sen1floods11/v1.1/catalog/sen1floods11_hand_labeled_label/collection.json)
declares `proprietary`, and [the missing-license issue](https://github.com/cloudtostreet/Sen1Floods11/issues/18)
remains unresolved. Third-party mirrors declaring CC-BY-4.0 do not establish
the authors' redistribution terms. Keep raw training data and trained artifacts
local pending clarification before redistributing them.

## Reproduce

```sh
uv run --locked --group processing python -m floodbeacon.ml --data-dir data --chips-per-event 3
```

This fetches 12 chips and their hand labels, two official split CSVs, event
metadata and the source license declaration from the anonymous public GCS bucket. It avoids downloading the full
archive. The cache records source URLs, original retrieval timestamps and SHA256
checksums. Locally generated outputs are `data/models/water-rf-<fingerprint>/`:
`model.pkl` and `metadata.json`. Only load pickle files generated locally by this
command or otherwise explicitly trusted; no remote model checkpoint is used.

The model uses three features: VV dB, VH dB and their difference. It uses 80 trees,
maximum depth 12, minimum leaf size 20, fixed seed 42, and two CPU workers. Each
training chip contributes at most 8,000 randomly selected pixels per class,
without replacement. The resulting class balancing makes vote fractions
**uncalibrated scores** rather than prevalence-corrected probabilities.

## Evaluation and provenance

The official `flood_train_data.csv` supplies training chips from Ghana, India
and Spain. The official `flood_bolivia_data.csv` supplies the geographic holdout.
Chips are selected deterministically using a fixed random seed, without
inspecting labels or scores. All Bolivia chips are excluded from training;
evaluation uses every valid pixel in the selected Bolivia chips, not random
pixels from training scenes. No threshold tuning is done on the holdout.

This bounded sample is a feasibility test, **not the full published benchmark**.
Pixels within chips are spatially correlated; the pixel count does not represent
independent trials. `metadata.json` records exact chip IDs, SAR and optical label
observation dates, CRS/grid, source checksums, class counts, training-array hash,
model parameters, library version and model checksum. It reports the land/water
confusion matrix and water precision, recall, F1 and IoU at score 0.5, including
per-chip metrics. Ahr/BC transfer accuracy is not measured by these metrics.

The initial real-data check (three chips per event) yielded pooled water
precision 0.9056, recall 0.9228, F1 0.9141 and IoU 0.8418 on 669,588 valid
holdout pixels. Confusion matrix (land/water rows and columns):
`[[406325, 23104], [18532, 221627]]`. Per-chip F1 was **0.9379, 0.8862,
and 0.1034** for Bolivia chips 129334, 314919 and 360519 respectively.
The poor third-chip result demonstrates why pooled scores alone are inadequate.
These results do not validate local flood detection or structural damage.

## Units, masks and transfer limitations

The authors document the S1Hand bands as **VV then VH in dB**, derived from
Earth Engine Sentinel-1 GRD. See [Earth Engine preprocessing](https://developers.google.com/earth-engine/guides/sentinel1).
Training excludes label -1/255 (unknown), raster no-data and non-finite channels.
It checks SAR/label grid alignment. Missing pixels remain unknown.

Planetary Computer Sentinel-1 RTC bands are linear **gamma naught**. The case
pipeline must mask invalid/non-positive values and convert valid values using
`10 * log10(value)` before calling `predict_water`. Matching the dB unit does
not make the sources equivalent: Earth Engine sigma naught and terrain-corrected
gamma naught differ, especially in mountainous terrain. Acquisition orbit,
incidence angle, season, snow, speckle and terrain shadow introduce additional
domain shift. Local validation and terrain-quality masks are required before
operational use. SAR water signatures are difficult in urban areas, beneath
vegetation and with rough water; the model uses no structural or hydraulic data.

The output class is **surface water**, which includes permanent water.
Pre/post imagery can identify newly water-like areas, but change alone does not
prove flooding or establish exact flood-peak extent. Classifier scores are not
calibrated flood likelihoods or bridge-failure probabilities. Road exposure is
a separate spatial overlay of candidate water with road approaches; it is not
a trained road-destruction detector. Agency damage grades remain separate.
