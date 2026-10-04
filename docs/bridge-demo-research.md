# A destroyed-bridge demo for FloodBeacon

Research and actual image spot checks, 2026-10-03. The user asked to prioritize
a compelling hackathon demonstration of damaged infrastructure and disrupted
access, including manual image review. Three parallel researchers inspected
the existing cases, Nepal, and other flood events. These are deliberately
selected examples, not a model benchmark or production integration.

## Current implementation

The bridge findings were made by visual review of the retrieved before/after
images. News and agency reports selected likely targets; the scripts retrieve
and crop imagery, draw manual review annotations, and render the viewer. No
pretrained bridge-collapse model generated the findings. Copernicus/UNOSAT
assessments remain separately attributed agency evidence.

The model research did not produce a validated bridge-collapse detector for
these examples. It produced runnable experiments for water, road obstruction
and building damage, with limitations documented in the
[model experiment report](damage-identification-research.md). The bridge viewer
and review points are standalone research artifacts; they have not been
published through the PostgreSQL/FastAPI pipeline.

## Recommendation

Use **Derna, Libya, September 2023** for a satellite-specific demo: a road
crossing is present before the flood and its deck is visibly absent afterward.
Use **Nepomukbrücke in Rech, Germany, July 2021** if keeping the existing event
is more valuable: a missing section is clearly visible in public aerial
orthophotos, with an existing Copernicus destruction assessment. Both support
the same product story: inspect a reported damaged crossing, mark the broken
connection on a map, and show responders why access needs reassessment.

For this small demonstration, manually identify and annotate the missing span.
Label the output **manual image assessment**, preserve agency evidence
separately, and describe automation as intended future functionality. News and
agency reports efficiently select targets; paired high-resolution images then
show what actually changed. A pre-event bridge inventory avoids having to
rediscover an object whose deck has disappeared.

## What we already have

The two production study cases remain Ahr/Germany and BC/Canada, as configured
in `src/floodbeacon/cases.py`. The research artifacts also include BRIGHT Libya
building-damage tiles, U.S. LADI aerial photos, and six SpaceNet 8 Germany
tiles. Those are additional research datasets, not additional published cases.

The Sentinel-1 water-classification pipeline cannot establish destroyed bridge
spans. Its water mask and infrastructure overlay describe exposure. The current
SpaceNet 8 experiment describes water/rubble obstruction, not bridge collapse.

| Candidate | Actual spot-check result | Imagery and target | Demo decision |
| --- | --- | --- | --- |
| Ahr, Rech, July 2021 | Complete crossing before; surviving northern section and missing southern span/connection afterward. Copernicus separately grades this bridge `Destroyed`. | Nepomukbrücke, approximately **50.514104 N, 7.036227 E**. Public RLP aerial orthophotos: pre-event flight 2019-06-27, post-event collection flights 2021-07-24/28/29. Rendered at 0.4 m; pre-event source 0.2 m, post-event source 0.4 m. | **Existing-case recommendation.** Clearly label the images aerial rather than satellite. |
| BC, November 2021 | Existing inputs establish water exposure and inventory context; no matched submeter bridge-destruction pair verified here. | Merritt/Coldwater and Highway 8/Nicola study bounds. Official corridor repair records document severe road losses, but current inventory is not historical damage labels. | Keep for the road-washout story; not the best ready bridge image demo. |
| Derna, Libya, September 2023 | Road bridge decks clearly present before; missing at the inspected crossings afterward. Broad erosion and destroyed approaches provide context. | Middle city crossing, approximately **32.76247 N, 22.64143 E**. Public Maxar GeoEye-1 RGB before 2023-07-01 and after 2023-09-13. | **Satellite-demo recommendation.** Multiple clearly visible road crossings; anonymously retrievable high-resolution imagery. |
| Syabrubesi, Nepal, inspected August 2026 imagery | Suspension footbridge span visible in 2023 and absent in August 2026, with major bank/settlement changes. | Approximately **28.165879 N, 85.342728 E**. Public Vantor GeoEye-1 before 2023-09-17 and WorldView-3 after 2026-08-27. | Strong second satellite example, but a **footbridge**, not a vehicle bridge; the old baseline does not date its loss to the August 2026 event. |
| Syabrubesi road crossing, Nepal | Deck visible in 2023; an intact-looking crossing also appears in a May 2026 Planet image; deck and approaches absent in August 2026. | Approximately **28.16422 N, 85.33999 E**. Same Vantor pair plus actual Planet 3 m image acquired 2026-05-27. Official bridge name and traffic classification unverified. | Useful road-access alternative. Recent reference narrows apparent disappearance to May–August 2026; exact failure date remains unverified. |

Coordinates are WGS84 longitude/latitude in the accompanying manifests. The
table displays latitude then longitude for readability. These are image-review
target locations, not surveyed engineering coordinates. Crop resolution is
not necessarily native sensor resolution; the detailed reports retain both.

## Other sources and events

[Airbus's Derna comparison](https://space-solutions.airbus.com/resources/news/various/libya-floods-seen-by-pleiades-neo/)
explicitly shows destroyed road infrastructure using 30 cm Pléiades Neo imagery.
Its published crops are a useful visual reference. Our downloaded GeoEye-1
pair comes from the separate public Maxar event collection, with its own
recorded dates and license; it is not the same image pair as Airbus's page.
[UNOSAT's 13 September assessment](https://unosat.org/static/unosat_filesystem/3671/UNOSAT_A3_Natural_Portrait_FL20230912LBY_DernaCity_13Sep2023.pdf)
provides another independent agency lead for damaged crossings.

For Nepal, Melamchi 2021 has documented bridge destruction and drone mapping,
but the accessible UNOSAT Sentinel-2 products are too coarse for a clean small
bridge-span close-up. The newer Rasuwa/Bhote Koshi/Trishuli event offers public
submeter before/after images. This is specifically the **26 August 2026** event,
verified against the [government rapid damage report](https://ndrrma.gov.np/mediafiles/rasuwa/Rapid_Damage_and_Needs_Assessment_RDNA_Rasuwa-Bhotekoshi_Flood_2026.pdf)
and [HOT's activation record](https://hotosm.org/en/news/mapping-the-nepal-floods/).
Do not conflate it with other Nepal flood events. A scene-wide high cloud
percentage does not exclude every local crop: the inspected bridge crop is
clear enough to compare.

Nepal also had a July 2025 flood. The 2023-to-2026 image pair alone cannot
attribute a missing bridge to the August 2026 event. An actually retrieved
May 2026 Planet scene provides a more recent, lower-resolution reference for
the road crossing, but the narrow suspension footbridge is too small to judge
confidently in that 3 m image.

Pakistan, Sikkim and other disasters remain possible sources, but we already
retrieved clear bridge examples in three geographies. No additional provider
subscription is needed to make the requested demonstration concrete.

## Bridge recognition versus bridge destruction

Bridge-specific object detectors **do exist**. The authors of
[GLH-Bridge / HBD-Net](https://github.com/Luo-Z13/GLH-Bridge-Code) publish a
very-high-resolution bridge-detection dataset, code, and an advertised
`Oriented_rcnn_HBDNet.pth` checkpoint link. The linked Google Drive landing page
was reachable; the checkpoint was not downloaded or run here. Detecting a
bridge's location is a different task from determining whether its span was
destroyed. The prior bridge-damage research did not establish an openly usable,
tested collapse checkpoint for our flood imagery.

For a handful of selected bridges, news/agency evidence plus pre-event bridge
locations and manual before/after review is the efficient approach. Record a
missing span, remaining section, washed-out approach, or obscured/unknown
status instead of inventing detector scores. A generic change model may be
an experiment later, but the markings delivered here are manual.

## Inspect and reproduce

The local [image viewer](../artifacts/bridge-demo/index.html) collects the
annotated comparisons, findings, source dates, coordinates and provenance
files. Large images and generated outputs remain ignored.

Detailed source/retrieval reports:

- [Existing Ahr and BC cases](bridge-demo-existing-data.md)
- [Derna and other events](bridge-demo-other.md)
- [Nepal](bridge-demo-nepal.md)

Run the standalone retrieval scripts using the existing locked environment,
then render the viewer:

```bash
uv run --group damage-research python scripts/prepare_bridge_demo_existing.py
uv run --group damage-research python scripts/prepare_bridge_demo_derna.py
uv run --group damage-research python scripts/prepare_bridge_demo_nepal.py
uv run python scripts/render_bridge_demo.py
uv run python -m http.server 8080 --bind 127.0.0.1 --directory artifacts
```

Open `http://127.0.0.1:8080/bridge-demo/`. Retrieval scripts read public sources
and write only research artifacts. Source access can change; manifests retain
exact scene IDs, URLs, transforms, dates and local checksums. No account,
API key or new dependency was needed for the retrieved examples.

Actual delivery checks: all three retrieval runners completed; the reviewed
images were opened and visually inspected. The viewer renders seven crossings,
including unannotated image links and WGS84 review points. Its 29 copied image
and provenance files passed checksum verification, all four scripts compiled,
and the in-app browser loaded the gallery and successfully switched between
Derna and Rech. A [viewer screenshot](../artifacts/bridge-demo/viewer-screenshot.png)
records the delivered comparison. These are retrieval/rendering checks, not
automated damage-detection validation.

RLP imagery is `dl-de/by-2-0` with attribution. The selected Maxar/Vantor event
collections declare **CC BY-NC 4.0**; retain the attribution and noncommercial
terms. Public access alone does not make an arbitrary provider press image
freely redistributable. The viewer uses the retrieved event-collection assets,
not copies of newspaper images.

## How to pitch the idea

Show a before/after bridge comparison, a marker reading "missing bridge span —
manual image assessment", and the affected road connection. Explain that
FloodBeacon brings post-disaster imagery and damage evidence into a planning
map. This research does not implement routing, validate detours, or establish
safe passage anywhere else on the map.

Water-covered roads still matter for access. A water mask cannot reveal water
depth, current, or a washed-out road bed below it. The
[National Weather Service](https://www.weather.gov/tsa/hydro_tadd) specifically
identifies hidden washed-out roads as a hazard. The demo can focus on visible
bridge destruction without equating shallow-looking water with driveability.
