# Ahr Valley regional satellite playback

The dated bridge close-up now sits inside a larger satellite map covering the
selected Ahr Valley study bounds: `[6.88, 50.37, 7.17, 50.59]`. These are study
bounds, not a measured flood boundary or the whole July 2021 event. The separate
Copernicus EMSR517 AOI15 agency footprint shows reported flooded/flood-trace areas.

The regional imagery uses public Maxar Open Data original scenes from the same
acquisition dates as the accepted Rech comparison. Before: two February 11, 2021
scenes (`10500500C4DD7000`, `10500500C4DD7100`). After: July 18, 2021 scene
`10500500E6DD3C00`. Acquisition dates come from the provider archive folders;
exact UTC times and source-native GSD remain unknown.

The scenes do not cover every study pixel. Transparent areas are unobserved,
not intact, dry, or passable. White cloud patches remain in the actual images.
The coverage GeoJSON and `valid_coverage_fraction` describe RGB availability,
not reliable observation, a cloud mask, or flood extent. Black exterior pixels
have no declared nodata tag in these original files; preparation explicitly
treats all-zero RGB as nodata. The valid-coverage outline is generalized from
the mask at roughly 50 m ground spacing and simplified by 35 projected metres.

The static XYZ WebP tiles cover zoom levels 8–15 with 256-pixel tiles. Zoom 15
has about 3 m ground sampling at this latitude, suitable for regional orientation.
The original inspected high-resolution Rech image remains a separate image
source above the regional tiles for bridge review. Regional downsampling and
lossy WebP compression do not provide new bridge assessments. No imagery or
terrain is fabricated.

## Prepare and publish

Preparation runs once on the processing machine:

```sh
uv run --locked --group processing python scripts/prepare_regional_imagery.py
uv run --locked --group processing python scripts/prepare_bridge_imagery.py
uv run --locked --env-file .env floodbeacon publish-imagery
```

`src/floodbeacon/regional_imagery.py` contains the reusable preparation. It opens
explicit COG overviews (factor 8 before, factor 4 after), then reads only bounded
windows using HTTP ranges. It never downloads the multi-gigabyte full scenes.
Aligned RGB/mask windows and their SHA256 checksums stay ignored under
`data/research/ahr-regional/`. The source full-object SHA256 is explicitly unknown;
source ETags, byte lengths, last-modified times, original grids, overview factors,
date-evidence checksums and retained window checksums are recorded instead.
ETags identify objects and are not claimed to be SHA256 hashes.

The committed static pyramid and manifest are under
`src/floodbeacon/static/imagery/ahr-region/`; every exported file has a SHA256 and
byte length in its manifest. Tiles are served directly by FastAPI; metadata and
agency GeoJSON are published atomically to PostgreSQL. Map GET requests perform
no raster processing. No new serving or processing dependencies are needed.

## Attribution and reproducibility

Regional imagery is © Maxar Technologies, **CC BY-NC 4.0**, under the
[Maxar Open Data protocol](https://maxar-marketing.s3.amazonaws.com/files/downloads/119757_opendataprotocol_2020_04.pdf).
It is distributed here for this noncommercial research/hackathon demo.
The separate SpaceNet Rech close-ups retain their own CC BY-SA 4.0 attribution.
The licenses differ and must remain per source.

Primary original-scene URLs:

- [February 11 western scene](https://dg-opendata.s3.amazonaws.com/events/western-europe-flooding21/pre-event/2021-02-11/10500500C4DD7000/10500500C4DD7000.tif)
- [February 11 eastern scene](https://dg-opendata.s3.amazonaws.com/events/western-europe-flooding21/pre-event/2021-02-11/10500500C4DD7100/10500500C4DD7100.tif)
- [July 18 scene](https://dg-opendata.s3.amazonaws.com/events/western-europe-flooding21/post-event/2021-07-18/10500500E6DD3C00/10500500E6DD3C00.tif)

The approach follows Rasterio's documented
[virtual warping and tiling](https://rasterio.readthedocs.io/en/stable/topics/virtual-warping.html).
`tests/test_regional_imagery.py` checks XYZ adjacency, published dates, no-data
semantics, provenance and checksums. It does not estimate damage-model accuracy.
