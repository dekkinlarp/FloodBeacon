# Rech satellite image assets

Real SpaceNet 8 satellite RGB imagery around Nepomukbrücke, Rech, Germany.
Before: 2021-02-11, scene `10500500C4DD7000`. After: 2021-07-18, scene
`10500500E6DD3C00`. Dates are supported by the original provider's scene/date
folders; exact UTC acquisition times are unknown.

`before.png` and `after.png` are aligned, unannotated RGBA images in a shared
Web Mercator grid. `manifest.json` supplies their URLs, WGS84 corner coordinates,
source checksums, dates, processing details and attribution. `comparison.png`
shows a 180 m close-up with a manually drawn 90 m review square.
`bridges.geojson` carries that square and the separate observation for each date.
The exact bridge failure time is unknown; no damage detector ran.

## Attribution and license

Satellite imagery © Maxar Technologies; SpaceNet Partners.
The published PNG imagery, annotated comparison and derived geographic
annotations are distributed under **Creative Commons Attribution-ShareAlike
4.0 International (CC BY-SA 4.0)**. Preserve attribution and share adapted
imagery under that license.

- Dataset/license declaration: <https://spacenet.ai/sn8-challenge/>
- License terms: <https://creativecommons.org/licenses/by-sa/4.0/>
- Before source: <https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/PRE-event/10500500C4DD7000_0_40_62.tif>
- After source: <https://spacenet-dataset.s3.amazonaws.com/spacenet/SN8_floods/Germany_Training_Public/POST-event/10500500E6DD3C00_0_40_62.tif>

Changes: RGB images were resampled bilinearly into a common EPSG:3857 grid;
observation masks use nearest-neighbour. The comparison crops/enlarges these
images and adds labels and a manual outline. No color enhancement, image
reconstruction or synthetic scene content was applied. This asset license
does not change the license of application code elsewhere in the repository.

Reproduce from the repository root:

```sh
uv run --locked --group processing python scripts/prepare_rech_satellite.py
```

Raw GeoTIFFs remain ignored under `data/research/rech-satellite/`. Only the small
published assets belong in Git. FastAPI serves this directory at
`/static/imagery/rech-satellite/` independently of PostgreSQL.
