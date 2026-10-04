# Additional destroyed-bridge demo research

Research and actual visual review on 3 October 2026 (Vancouver). Production
cases, API and models were not changed. The user authorized small-area manual
satellite interpretation for a hackathon demonstration.

## Recommended: Derna, Libya, September 2023

**Use a real before/after bridge pair from Derna as a satellite demo.** Two
GeoEye-1 road crossings were actually fetched and inspected, rather than merely
identified in a news search. Before, each road has a continuous deck across
Wadi Derna; after, the corresponding deck is absent and the corridor is scoured.
This is a much clearer visual story than a flood mask overlapping a bridge.

[Copernicus's event account](https://mapping.emergency.copernicus.eu/news/flood-in-libya/)
reports destruction of bridges after Storm Daniel and upstream dam failures.
[UNOSAT's city-centre assessment](https://unosat.org/static/unosat_filesystem/3672/UNOSAT_A3_Natural_Portrait_FL20230912LBY_DernaCity_ZoomInRiver_13Sep2023.pdf)
marks three destroyed bridges. It uses 50 cm Pléiades imagery acquired
13 September 2023, 11:39 UTC, and was published 14 September; it explicitly says
its preliminary analysis was not field validated. This provides independent
agency corroboration, not a FloodBeacon model result.

| Manual review target | Approximate deck centre, WGS84 lon/lat | Finding in fetched imagery |
| --- | --- | --- |
| Derna middle Wadi road crossing | 22.641427, 32.762475 | Continuous deck before; corresponding deck absent after, road continuity severed |
| Derna northern Wadi road crossing | 22.643210, 32.764157 | Continuous deck before; crossing absent after with remnants amid scoured channel |

These are descriptive target IDs, not verified official bridge names. The
coordinates were read from georeferenced imagery and are approximate, not
surveyed asset coordinates. Labels are **manual destroyed-bridge candidates**,
corroborated at the event/location level by agency assessment. There is no
trained detector, detector accuracy metric or generalization claim.

### Actual imagery and access

The legacy public S3
[event collection](https://maxar-opendata.s3.amazonaws.com/events/Libya-Floods-Sept-2023/collection.json)
and COG assets returned successfully without credentials. The former Maxar event
website redirects to the current
[Vantor Open Data Program](https://vantor.com/company/open-data-program/), but its
legacy imagery is still publicly readable as of the research run. The
collection's declared license is **CC BY-NC 4.0**; retain **© Maxar 2023** and
license/source attribution for the noncommercial local demo. A future commercial
product needs a compatible imagery license.

| Phase | Acquisition UTC | STAC item | Metadata native GSD |
| --- | --- | --- | --- |
| Before | 2023-07-01 09:07:42Z | `34/120200213130/105005005ADE7C00` | 0.46 m |
| After | 2023-09-13 09:18:09Z | `34/120200213130/10500100363D0900` | 0.42 m |

The RGB visualization GeoTIFF grid is **0.30517578125 m** in both phases; that is
a resampled display grid and does not improve native resolving power. Both use
EPSG:32634 (WGS84 / UTM 34N). Each inspected target is a 350 m square, clipped by
remote COG window reads, with no whole-scene download. The crop preserves the
visual grid and channel values. A PNG scientific figure adds a 50 m radius
circle at the approximate pre-event bridge centre. Different viewing angles and
building parallax remain; a common grid is not proof of perfect coregistration.

Reproduce with the existing locked environment (no new dependencies):

```sh
uv run --group damage-research python scripts/prepare_bridge_demo_derna.py
```

Ignored outputs under `data/research/bridge-demo-other/`:

- `manifest.json`: source URLs/item IDs, UTC acquisition/retrieval times, native
  GSD/display spacing, coordinates, CRS, transforms, manual findings, attribution,
  processing and SHA-256 checksums of crop GeoTIFFs, PNGs and STAC metadata.
- `derna_middle_bridge_before.png` and `_after.png`, and analogous north pair:
  unannotated real satellite crops suitable for a before/after slider.
- `derna_middle_bridge_comparison.png` and `derna_north_bridge_comparison.png`:
  inspected annotated side-by-side comparisons.
- Corresponding `.tif` crops retain georeferencing; item JSONs retain source metadata.

Both figure outputs were opened and inspected after retrieval. Their visible
missing decks are the reason for recommendation; the existing water classifier
played no part in these findings.

An alternative provider reference is
[Airbus's Derna article](https://space-solutions.airbus.com/resources/news/various/libya-floods-seen-by-pleiades-neo/),
published 15 September 2023, which has 30 cm Pléiades Neo comparisons from
18/19 August and 13 September, including infrastructure and coastal-road damage.
Those published pictures are useful references; the reproducible local pairs
above instead use the explicitly licensed Maxar open-data assets.

## Other researched leads

| Event | Evidence and source | Why it is behind Derna |
| --- | --- | --- |
| Chungthang, Sikkim, India, October 2023 | [Official NRSC/ISRO map](https://www.nrsc.gov.in/sites/default/files/pdf/DMSP/17_C3_13_Oct2023_2.pdf) indexes Cartosat-2E, 10 May 2023, versus Cartosat-3, 13 October 2023, and labels collapsed bridges on Gangtok–Chungthang Road and Lachung River | Search index gives bridge-specific agency annotations, but the original PDF returned HTTP 404 during this run. No actual pair was retrieved/inspected and raw imagery access/rights were not established |
| Swat, Pakistan, August 2022 | [Research study](https://nhess.copernicus.org/articles/25/1071/2025/) reports damage to eight bridges on 26 August 2022 | Promising named corridor, but no high-resolution bridge-specific open satellite pair was verified in this work. Madyan must not automatically be called destroyed: [contemporary reporting](https://time.com/6210211/pakistan-floods-cost/) says the replacement bridge survived and reopened |
| Hassanabad, Hunza, Pakistan, May 2022 | [Contemporary reporting](https://www.arabnews.pk/pakistan/glacial-outburst-destroys-strategic-bridge-connecting-pakistan-with-china-2077466) identifies the Karakoram Highway bridge destroyed by a glacial outburst | Clear real collapse, but a different May event from the monsoon dataset. No openly licensed satellite before/after pair was fetched here |
| Valencia region, Spain, October 2024 | [Copernicus EMSR773](https://mapping.emergency.copernicus.eu/news/flood-in-valencia-region-spain/) supplies damage/flood emergency mapping; [official EFAS bulletin](https://european-flood.emergency.copernicus.eu/sites/default/files/bulletins-documents/2024/EFAS_Bimonthly_Bulletin_Oct_Nov2024.pdf) describes impassable or destroyed bridges | Strong disaster mapping, but no bridge-specific publicly licensed VHR pair was actually verified in this work |

No additional service account is needed for the recommended Derna pair. Paid
archive access would mainly help choose an arbitrary bridge or obtain a sharper
scene outside existing open-data footprints; it is unnecessary to proceed with
these inspected targets.

## Bridge recognition versus collapse detection

Bridge-specific object detectors exist. The authors'
[GLH-Bridge/HBD-Net paper](https://arxiv.org/abs/2312.02481) introduces 6,000 VHR
images with 59,737 bridge annotations and a dedicated detector; the
[official implementation](https://github.com/Luo-Z13/GLH-Bridge-Code) is an
appropriate starting point if automated bridge localization is later desired.
Bridge presence/localization is a different task from deciding whether the
structure is destroyed. This research did not establish a ready-made,
validated flood-collapse detector or run such a model. For a few demo assets,
news/agency-guided geolocation plus explicit manual image review is efficient.
