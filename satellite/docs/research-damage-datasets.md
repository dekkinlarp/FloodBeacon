# Datasets for identifying existing infrastructure damage

Checked 2026-10-03 using author repositories, official catalogs and actual
anonymous HTTP requests. This is research for already damaged infrastructure,
not a forecast of future structural failure. Model experiments are separate
from production API layers. Dataset availability is not model accuracy.

## Recommended bounded experiment

Use the **BRIGHT Libya flood event with its event-excluded UNet checkpoint**
for the first reproducible damage experiment. It supplies actual building
damage labels and co-registered, georeferenced very-high-resolution inputs.
This tests building damage, including destruction, rather than relabeling
water or road inundation as structural failure. The [author cross-event
protocol](https://github.com/ChenHongruixuan/BRIGHT/blob/master/bda_benchmark/README_cross_event.md)
reserves the target event while training/validating on the other 13 events.

All **26 Libya entries from the official standard test list** were retrieved,
before selecting tiles by label outcome. The first six entries happened to
contain no damaged/destroyed labels; restricting evaluation to those entries
would fail to measure damage detection. Retaining all 26 includes nine tiles
with damaged/destroyed pixels, three background-only tiles, and fourteen with
background/intact buildings. This is the complete Libya subset of that test
list, not the complete 124-tile Libya event or an independent BC/Ahr validation.

Retrieve or integrity-check the sample with:

```bash
uv run python scripts/prepare_bright.py
uv run pytest tests/test_research_downloads.py -q
```

The 78 TIFFs occupy **136,463,704 bytes**. ZIP central directories and individual
compressed member ranges were fetched; the multi-gigabyte archives were not
fully downloaded. All inputs have 1024×1024 grids in EPSG:32634 at approximately
0.35 m spacing. Pre-event imagery has three uint8 RGB bands, post-event SAR one
uint8 band, and target masks one uint8 band. Grids agree within floating-point
roundoff. The label classes are **0 background, 1 intact, 2 damaged,
3 destroyed**. Comments in the author's visualization script use misleading
minor/major names; retain the dataset's actual class semantics.

The author-hosted [Hugging Face release](https://huggingface.co/datasets/Kullervo/BRIGHT)
was pinned to `46f202d9520cb0844a6ca4679d016d0d27a6d58c`. Code/split metadata was
checked at Git revision `59269142f3a3550320513e362692732f46486985`. The local
ignored research artifacts are:

- `data/research/bright-sample/{pre-event,post-event,target}/`: actual TIFFs.
- `data/research/bright-sample-manifest.json`: member names, source URLs,
  SHA-256, bytes, CRS, transforms, dimensions and class counts.
- `data/research/bright-libya-test-ids.txt`: all 26 official test identifiers.
- `data/research/bright-libya-members.json`: pinned archive URLs, sizes,
  compressed member offsets/sizes for reproducible bounded retrieval.
- `data/research/bright-libya-test-class-counts.json`: label support per tile.

First official identifiers are `libya-flood_00000102`, `libya-flood_00000041`,
`libya-flood_00000042`, `libya-flood_00000081`, `libya-flood_00000109` and
`libya-flood_00000108`. Inputs follow
`pre-event/{id}_pre_disaster.tif`, `post-event/{id}_post_disaster.tif`, and
`target/{id}_building_damage.tif`. The [full official test list](https://github.com/ChenHongruixuan/BRIGHT/blob/master/bda_benchmark/dataset/splitname/standard_ML/test_set.txt)
is the source of the remaining identifiers.

The [author checkpoint catalog](https://zenodo.org/records/15349462) lists
`ckpt_UNet_cross_event_zeroshot_libya-flood.pth`, 124,274,886 bytes.
Its API-linked content URL is
`https://zenodo.org/api/records/15349462/files/ckpt_UNet_cross_event_zeroshot_libya-flood.pth/content`.
Use the `api/records` path for `/content`; the otherwise similar
`/records/.../content` path is incorrect. The dataset researcher has not run
this checkpoint; runtime and actual scores belong in the experiment report.

## Dataset and evidence matrix

| Dataset | Inputs and task | Bounded access verified | Reference, split and interpretation | Rights/accounts |
| --- | --- | --- | --- | --- |
| [BRIGHT author release](https://github.com/ChenHongruixuan/BRIGHT) | Pre-event optical plus post-event commercial VHR SAR; building intact/damaged/destroyed segmentation. It is not ordinary Sentinel SAR. | 26 Libya test pairs plus masks actually downloaded, 136 MB raw, with GeoTIFF CRS. Public HTTP ranges worked without login. | Manual image-derived damage references, not structural inspections. Event-excluded checkpoint is preferable to random tile splits. Acquisition dates must still be recovered at source-scene level before historical playback; the event date is not the acquisition time. | Author card's detailed terms take precedence over simplifying a record-wide license: most Maxar optical and associated labels CC BY-NC 4.0; SAR CC BY 4.0. Local noncommercial research is permitted. Commercial use needs a rights review. |
| [xBD / xView2](https://xview2.org/dataset) | Paired sub-meter RGB, building polygons and no/minor/major/destroyed grades. | [ChangeOS author's HF export](https://huggingface.co/datasets/EVER-Z/torchange_xView2) metadata HTTP 200, ungated, 24.26 GB total, parquet shards; labels and RGB are embedded. No full imagery shard downloaded by this researcher. | Original hold/test/train/tier3 splits retained. These are usually within-event spatial splits; an in-event test result does not establish unseen-event transfer. Export columns contain images/masks/name, not explicit geospatial metadata. Original xBD JSON geometry is needed for trustworthy map placement. | Original portal requests registration. Author HF export card has no explicit license. Availability or Apache/MIT model code does not grant imagery redistribution rights. Prefer original authorized access for product integration. |
| [xBD-S12](https://github.com/prs-eth/xbd-s12) | Sentinel-1 VV/VH dB plus all 12 Sentinel-2 bands, before and after; building damage reduced to intact versus damaged. | [Zenodo metadata](https://zenodo.org/records/18960454) HTTP 200: `xbd_s12.tar.gz` 9,523,531,926 bytes; original satellite tiles 11,023,654,343 bytes. No bounded individually labeled sample found in that release. | Public release contains Sentinel imagery/metadata, **not original xBD labels**. Masks must be created from original xBD; those require separate access. Metadata includes event split, source acquisition dates, orbit, cloud score, counts and EPSG:4326 footprint. 128×128 patches at about 4 m spacing are interpolated, not 4 m native sensor detail. | Sentinel-derived Zenodo release CC BY 4.0; original VHR/labels explicitly not redistributable by this author. Public models MIT, no HF account needed in checked requests. Dataset metadata/license does not license original xBD labels. |
| [SpaceNet 8](https://spacenet.ai/sn8-challenge/) | VHR paired RGB; flooded/nonflooded road/building labels, road segmentation and speed context. | Public S3 listing, Germany mapping CSV and per-file metadata HTTP 200 without AWS credentials. Individual ~9.12 MB post TIFFs avoid tarball downloads. | Germany 2021 and Louisiana 2021 flooding. Flooded labels are access/exposure references, not destroyed-road/bridge labels. Released competition winners trained on public Germany/Louisiana-East: those tiles cannot be called independent evaluation of their checkpoints. Test labels require confirmation before claiming scored holdout accuracy. | Dataset CC BY-SA 4.0, official code Apache-2.0; no account for checked public S3 objects. Preserve per-asset notices. |
| [CEMS EMSR517 AOI15](https://mapping.emergency.copernicus.eu/activations/EMSR517/) | Satellite-interpreted vector transportation damage grades and event polygons. | Existing pipeline downloaded 2.865 MB vector ZIP; 762 damaged transportation features and 53 destroyed grades are ingested. | Agency evidence, situation July 18/production July 19. Categories include infrastructure other than bridges; preserve `obj_type`. No original Pleiades imagery grant. Suitable target-case independent annotation, with image-date/object correspondence and uncertain/undetectable classes handled. | Public derived CEMS product with attribution/terms; third-party imagery rights separate. |
| [RLP Ahr special-flight orthophotos](https://www.geoportal.rlp.de/mapbender/php/mod_showMetadata.php?id=73160&languageCode=de&layout=tabs&resource=layer) | Public 40 cm RGB orthophotos after the 2021 event; image source for independent bridge/road appearance research. | Official metadata/INSPIRE service and dataset feeds HTTP 200. Download feed exposes WMS-derived GeoTIFF sections and projected CRS. Small actual TIFF request is separately recorded below. | Flights July 24, 28 and 29, 2021; later than CEMS July 18 and likely after some clearance. Collection-level dates cannot be assigned to every pixel without extra metadata. Historical pre-event orthophotos are a separate product. No automatic damage labels supplied by the images themselves. | Dataset ISO metadata declares free `dl-de-by-2.0`, with required GeoBasis-DE/LVermGeoRP source credit. No registration in checked metadata/feed requests. |
| [DLR ZKI Ahr activation ACT152](https://services.zki.dlr.de/de/activations/items/ACT152/) | Before/after aerial maps and damage extent; selected products from July 16/20 and later interpretation. | Official product listing verified. Download/map products are available, but no complete redistributable raw aerial training release established here. | Strong interpretation/reference context. Map illustrations with overlays and cartographic text are not interchangeable with calibrated image pairs. | Example official illustration has CC BY-NC-ND 3.0. Its derivative restriction needs care for training/cropping/redistribution; do not infer that all raw imagery is open. |
| [BC Highway 8 recovery](https://www2.gov.bc.ca/gov/content/transportation-projects/bc-highway-flood-recovery/2021-flood-road-recovery-projects-highway-8) | Official damaged-site maps, construction/geotechnical reports and response photos. | Public official [site 16 geotechnical memo](https://www2.gov.bc.ca/assets/gov/driving-and-transportation/transportation-infrastructure/contracting-with-the-province/documents/26355-0001/sched_t3-61_-_hwy_8_geotechnical_completion_memos_site_16.pdf) located. | Useful verified site evidence, generally later report dates and site-level descriptions. Base aerial imagery may be pre-event Maxar June 16, 2021; a report background is not post-flood imagery. No open georeferenced paired VHR damage benchmark verified for our BC bbox. Manual extraction should retain location uncertainty, damage type and observation time. | Public report access, with embedded third-party imagery rights separate. BC account alone would not supply a paired commercial scene license. |
| [UNOSAT](https://unosat.org/products/) | Satellite-derived building/infrastructure damage and flood impact products for many activations. | Public catalog and official [Libya comprehensive report](https://unosat.org/static/unosat_filesystem/3687/UNOSAT_Preliminary_Comprehensive_DA_Report_September2023_FL20230912LBY.pdf) verified. | Potential independent reference for Derna, if corresponding vectors and dates are obtained. Some products are inundation, some structural damage; not interchangeable. Image-derived agency damage is not on-site engineering certification. | Read each product's terms and original imagery copyright. A historic UNOSAT flood map declares CC BY-NC-SA 3.0; a universal permissive license cannot be inferred for all current outputs. |

## Small-data retrieval details

BRIGHT supports actual selective retrieval even though release links are ZIPs:
HTTP `Range` reads obtain the ZIP64 end records/central directory, then individual
local headers and compressed TIFF members. Validate HTTP 206 and Content-Range,
member bounds, decompressed size, ZIP CRC and SHA-256. Cache under ignored data,
not Git. Do not reuse offsets across a different archive revision/host.

Pinned HF sizes were `pre-event.zip` **9,901,512,150 bytes**,
`post-event.zip` **3,291,986,721**, and `target.zip` **47,638,868**. The [current
Zenodo record](https://zenodo.org/records/20072020) instead lists pre-event ZIP
7,977,829,095 bytes; its offsets cannot be substituted. Small DFC25 test images
ZIP is 423,318,336 bytes and labels 1,419,887 bytes, but the checked image-member
list does **not** contain Libya, so it is not the proposed flood experiment.

SpaceNet 8 supports easier ordinary per-file HTTP downloads:

```text
https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/Germany_Training_Public_label_image_mapping.csv
https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/PRE-event/{mapped_pre_name}
https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/POST-event/{mapped_post_name}
https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/annotations/{mapped_label_name}
```

S3 `ListObjectsV2` with prefix `spacenet/SN8_floods/` returns object size,
last-modified and ETag. Last-modified is release/storage time, not imagery
acquisition time. Germany's complete tarball is 1,357,293,885 bytes,
Louisiana-East 3,336,023,039, and Louisiana-West test 2,617,320,506. Prefer
individual files to avoid unnecessary bandwidth and archive extraction issues.

RLP Ahr post-event service:

```text
https://geo4.service24.rlp.de/wms/rp_dop40_sonderbefliegung_hochwasser.fcgi
layer: rp_dop40_sonderbefliegung_hochwasser_ahr_2021_rgb
WMS 1.1.1, SRS EPSG:25832, FORMAT image/tiff
```

The [official dataset ISO metadata](https://www.geoportal.rlp.de/mapbender/php/mod_dataISOMetadata.php?outputFormat=iso19139&id=dc9b8a92-aea2-2df4-2177-836e91e39e8a)
records the license and source-credit template. The INSPIRE dataset feed uses
`mod_inspireDownloadFeed.php?id=dc9b8a92-aea2-2df4-2177-836e91e39e8a&type=DATASET&generateFrom=wmslayer&layerid=73160`
at that Geoportal host. Its 115 section links use 2 km projected bboxes,
5000×5000 TIFF grids at 0.4 m; a bounded GetMap can use the same resolution.

The **populated Altenahr pair** is the meaningful building-model research
input. Retrieve it with `uv run python scripts/prepare_ahr_imagery.py` (or
explicit `--sample altenahr`). It uses center longitude 6.9934/latitude
50.5174 and EPSG:25832 bounds
`[357542.82744040847, 5597878.304765015, 357952.42744040844, 5598287.904765015]`.
Both real 1024×1024 RGBA rasters were retrieved and visually inspected before
inference: dozens of buildings, roads, river and bridge structures are visible;
the post image shows riverbank/road/debris changes. This visual description is
not an engineering damage label or a scored model result. Distinct filenames
are `ahr-altenahr-vhr-pre-2019.tif` (734,249 bytes) and
`ahr-altenahr-vhr-post.tif` (2,517,338 bytes), each with JSON provenance. The
center pre-flight metadata gives **2019-06-28**; post-center metadata gives
creation **2021-07-24** and publication **2021-10-12 07:27:14.024** without a
timezone. The same creation/acquisition/availability caveats below apply.

An initial **exploratory forest crop**, unsuitable for evaluating building
damage, used a real 1024×1024, 409.6 m GetMap around longitude 7.069/latitude 50.5433.
It returned HTTP 200 and a nonblank 2,009,644-byte RGBA GeoTIFF in EPSG:25832,
with 0.4 m grid spacing. The ignored `data/research/ahr-vhr-post.tif` and
`ahr-vhr-post.json` preserve the image and exact URL/checksum. Its collection
dates are known; its pixel-specific acquisition date is not yet assigned.

Reproduce the earlier forest pair with
`uv run python scripts/prepare_ahr_imagery.py --sample forest`. This script contains the source
URLs, fixed bounds, source metadata and SHA-256 pins; it does not require any
existing ignored JSON. It downloads only missing TIFFs, verifies existing
files without network requests, checks CRS/pixel alignment and preserves the
original alpha bands. WMS 1.1.1 is retained for the verified exact request
contract; no application/runtime dependency is downgraded. A changed source
checksum requires review rather than silently accepting changed imagery.

The same bounds also returned a nonblank **603,853-byte pre-event RGBA
GeoTIFF** from `https://geo4.service24.rlp.de/wms/rp_hkdop20.fcgi`, layer
`rp_dop20_rgb_2019`. It has the same EPSG:25832 transform and 1024×1024,
0.4 m output grid. Its DOP20 source is rendered to a coarser matching grid,
not claimed to be a native 0.4 m image. A GetFeatureInfo query at the center
on `rp_dop20_info_2019` identifies `dop_32362_5600` and flight date
**2019-06-27**. The ignored `ahr-vhr-pre-2019.tif`, JSON provenance and metadata
HTML preserve those checks. This is an actual anonymous high-resolution
pre/post RGB pair for future inference research, not a damage-model result.
The [official service migration notice](https://lvermgeo.rlp.de/service/aktuelles/detail/vorabinformation)
explains why older historical DOP40 endpoints were retired in 2025; use the
current historical DOP20 service. Verify scene dates and registration before
comparing output with July 18 agency labels.

The post-event `rp_dop10_sonderbefliegung_hochwasser_ahr_2021_info`
GetFeatureInfo at the same center identifies `rgbi_32_363_560`,
**Erstellung (creation) 2021-07-24** and **publication
2021-10-12 07:27:18.609**, without an explicit timezone. Its creation field
is consistent with one collection flight date but is not explicitly labeled
as a flight/acquisition timestamp. Preserve that distinction. The WMS
publication field also does not prove the imagery was unavailable through
all other channels earlier. This source cannot be treated as an input known
on July 18 merely because it depicts the flood aftermath.

## Evaluation and applicability

For the BRIGHT experiment, report the four-class confusion matrix, per-class
precision/recall/F1/IoU, macro metrics with explicit absent-class handling,
binary damaged-or-destroyed versus intact performance, and each tile's scores.
Show RGB, SAR, labels and predictions side by side, plus geospatial bounds.
Overall pixel accuracy alone hides background/intact dominance. Distinguish
joint localization-and-damage performance from classification conditional on
reference building pixels. A damage-only score on perfect reference footprints
is not an end-to-end detector score. Pixel components are not automatically
individual building instances or road closures.

Use the event-excluded checkpoint without tuning thresholds/hyperparameters on
these test labels. If fine-tuning is investigated later, reserve new regions or
whole events for final evaluation; random neighboring tile splits permit spatial
leakage. Test data, checkpoints and predictions must stay out of training.

Spatial resolution and input modality are decisive. ChangeOS/xBD RGB cannot be
given Sentinel RGB upsampled to sub-meter pixels and treated as equivalent data.
BRIGHT's post-event SAR is commercial VHR, whereas our existing flood detector
uses Sentinel RTC at 20 m. xBD-S12 is genuinely designed for Sentinel data but
collapses all damage grades and needs its 28-channel acquisition/normalization
recipe. None of these building datasets supervises bridge collapse or destroyed
road connectivity. A bridge model must have bridge-specific overhead examples,
pre/post alignment, intact negatives and independent damage labels; vehicle
pavement-crack datasets and smartphone bridge photos answer other tasks.

The best immediate **damage-label experiment** is BRIGHT. The best immediately
accessible **road/flood-exposure benchmark** is SpaceNet 8. The most promising
**existing-case VHR research path** is RLP Ahr orthophotos plus agency damage
labels and additional manual review. No verified BC paired VHR benchmark was
found in this research pass. A building experiment is authorized as research
by the latest user request; exporting it as a production damage layer or
changing the product's roads/bridges scope still needs agreement.
