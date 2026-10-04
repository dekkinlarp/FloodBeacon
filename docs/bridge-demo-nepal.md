# Nepal destroyed-bridge imagery spot check

Research retrieval and visual inspection completed 2026-10-03 (Vancouver).
This work is separate from the production water model, batch pipeline, and API.

## Result

Nepal offers a strong visual example with anonymous public high-resolution
imagery. Two crossing locations in Syabrubesi were inspected. Clear local
before/after crops show a continuous crossing in the older image and no
continuous crossing in the newer image. These are **manual image
interpretations**, not predictions from a bridge-destruction model.

| Target | Coordinates (longitude, latitude) | Observation |
| --- | --- | --- |
| Syaphru Besi I / Trishuli suspension footbridge | 85.342728, 28.165879 | Narrow continuous span in 2023; span and approaches no longer visible in August 2026. |
| Road crossing near the Langtang confluence; official name unverified | approximately 85.33999, 28.16422 | Road-linked deck visible in 2023; intact-looking diagonal span also visible in a May 2026 Planet image; deck and approaches no longer visible in August 2026. |

The footbridge coordinate comes from the
[Bridgemeister historical inventory](https://www.bridgemeister.com/bridge.php?bid=9351).
The road crossing was localized manually from georeferenced imagery. Its
vehicle use is inferred from its connecting roads; no surveyed asset identity
or authoritative traffic classification was established.

## Actual images and date limits

The [Vantor event collection](https://vantor-opendata.s3.amazonaws.com/events/Nepal-Flooding-Aug-2026/collection.json)
was read directly, then only small COG windows were fetched using HTTP range
reads. No account, API key, subscription, or whole-scene download was needed.

| Scene | Acquisition timestamp, UTC | Sensor and advertised panchromatic GSD | Availability |
| --- | --- | --- | --- |
| `10500100364E8400` | 2023-09-17T05:09:38.085154Z | GeoEye-1, 0.43 m | Metadata `published`: 2026-08-27T17:15:12.287544 |
| `B040001100881410` | 2026-08-27T05:04:50.163085Z | WorldView-3, 0.35 m | Metadata `published`: 2026-08-27T19:54:03.972132 |

Both selected windows are locally clear on visual inspection. The post-event
scene reports **73% cloud over the entire strip**, showing why local spot checks
matter more than rejecting the whole scene. A September 7 scene was also
inspected, but its local window was dark and much less useful.

The primary government
[NDRRMA RDNA](https://ndrrma.gov.np/mediafiles/rasuwa/Rapid_Damage_and_Needs_Assessment_RDNA_Rasuwa-Bhotekoshi_Flood_2026.pdf)
identifies an ice/rock-avalanche-related flood on 26 August 2026. This event is
separate from the 8 July 2025 Rasuwa flood. The
[ICIMOD event explanation](https://www.icimod.org/kyirong-rasuwa-flood-2026-nepal-china-border/)
describes that earlier event and destruction of the Friendship Bridge upstream;
we did **not** establish its effect on these exact Syabrubesi crossings.

Therefore the **2023-to-2026 high-resolution pair alone establishes that a span
is missing by 27 August 2026**. It cannot attribute all change to a particular
flood or date the failure precisely. News
[before/after coverage](https://www.abc.net.au/news/2026-08-28/nepal-tibet-floods-satellite-imagery-shows-destruction/107088372)
helps identify the target but uses a different pre-event image/date from the
actual scene we retrieved; keep those baselines separate.

An additional recent baseline was actually fetched from
[Planet's public pre-event collection](https://data.source.coop/planet/disasterdata/nepal-flash-flood-2026-08-26/pre-event/planetscope-2026-05-27/collection.json):
`20260527_053221_96_254a`, acquired 2026-05-27T05:32:21.964727Z, at 3 m
resolution in EPSG:32645. The locally clear road-crossing crop has an
intact-looking bright diagonal crossing. Together with the August image this
narrows apparent disappearance to **27 May–27 August 2026**. It does not date
failure within that interval or certify structural condition. The narrow
footbridge is too small for a confident continuity judgment at 3 m. A second
Planet item overlapped the coordinate's bounding box but returned no-data at
the target; it was excluded.

## Inspect and reproduce

Run with the existing locked environment; no new dependencies were added:

```bash
uv run --locked --group damage-research python scripts/prepare_bridge_demo_nepal.py
```

The script writes ignored outputs under `data/research/bridge-demo-nepal/`:

- `manifest.json`: exact source URLs, scene IDs, acquisition and publication
  times, retrieval time, coordinates, CRS, affine transforms, resolution,
  manual findings, rights, and SHA-256 checksums.
- `syabrubesi-trishuli-footbridge-comparison.png`: annotated high-resolution pair.
- `syabrubesi-langtang-road-crossing-comparison.png`: annotated high-resolution pair.
- `syabrubesi-langtang-road-crossing-recent-before.png`: May 2026 3 m reference.
- Corresponding cropped GeoTIFFs and individual PNGs; downloaded STAC metadata.

The circles mark approximate crossing locations for attention, not measured
bridge footprints. No precision image coregistration was performed. Distances
and areas were not estimated from the EPSG:4326 crops. Every artifact contains
real retrieved imagery; no synthetic bridge destruction was inserted.

Vantor and Planet collections declare **CC BY-NC 4.0**. Preserve provider
attribution and noncommercial restrictions. Downloads remain ignored local
research artifacts.

## Why not Melamchi 2021 first?

The [ICIMOD 2021 report](https://lib.icimod.org/records/j06m8-z1k87)
documents widespread road/bridge impacts, and an August 1
[local report quoting police](https://kathmandupost.com/province-no-3/2021/08/01/saturday-night-floods-in-melamchi-caused-significant-infrastructure-damage)
identifies the Chanaute motorable and suspension bridges as swept away.
However, the public
[UNOSAT June 24 map](https://unosat.org/static/unosat_filesystem/3234/UNOSAT_A3_Natural_Portrait_FL20210630NPL_Melamchi_Landslide_24062021.pdf)
uses 10 m Sentinel-2 and describes potentially affected bridges. It is not
clear visual proof of a missing deck. A
[Geovation drone assessment](https://storymaps.arcgis.com/stories/5df39824b5604c80be8dfc429be93cfa)
compares Maxar baseline with drone imagery; its ArcGIS metadata was inspected,
but no bridge-focused satellite pair was retrieved from it. Nepal 2026 was a
more efficient source for an actual high-resolution spot check.
