# Existing-case bridge demo: actual Ahr spot checks

Checked 2026-10-03 Vancouver time (retrieval timestamps are UTC).

**The Ahr event already satisfies a visibly destroyed-bridge demonstration.**
Anonymous, openly licensed **aerial orthophotos** show real missing bridge spans
and decks. These are not satellite images and these markings are manual visual
interpretation, not output from the Random Forest or SpaceNet model. No account
or paid imagery service was needed for these spot checks. BC remains a weaker
choice with the currently downloaded sources because we have no verified
before/after submeter BC image pair.

## What was actually inspected

Targets were selected from the existing CEMS AOI15 bridge geometries whose
agency grade is `Destroyed`. The layer contains 34 features specifically labelled
`2141-Bridges and elevated highways`: 15 Destroyed, 5 Damaged, 8 Possibly damaged,
5 No visible damage, and 1 Not Analysed. These counts describe agency features,
not independently verified outcomes or necessarily 34 unique physical bridges.
We fetched three small aligned image pairs and visually inspected all three.

| Target | WGS84 longitude, latitude | Before/after visual finding | Demo suitability |
| --- | --- | --- | --- |
| Nepomukbrücke, Rech | 7.03622715, 50.51410390 | Continuous full crossing before; surviving northern section after with southern span/connection missing and a widened river channel. | Strongest named example. High confidence in the visible missing section; partial collapse, not a claim that every arch vanished. |
| Karl-von-Ehrenwall-Allee footbridge, Ahrweiler | 7.090980575, 50.5387828095 | Continuous narrow diagonal deck before; crossing deck absent after, with isolated small remnants in the river. | Very clear complete crossing gap. High confidence in the visual change. Agency feature name retained; not independently established as the formal bridge name. |
| Josefstraße bridge, Dernau | 7.08041305, 50.52958695 | Northern deck survives; southern end has irregular exposed remnants and its former connection is interrupted. | Usable additional example; moderate confidence in the precise lost connection because trees partly obscure the earlier southern edge. |

The site observations establish visible missing structures/physical access
interruptions at the pictured crossing. They do not establish the safety of
surviving components, a collapse mechanism, all nearby route conditions, or the
exact failure time. Rech also has a nearby crossing visible in the post-event
scene: marking the original bridge does not imply that every alternate route is
unavailable.

The Rech interpretation has independent corroboration: the
[Kreis Ahrweiler statement](https://kreis-ahrweiler.de/denkmalrechtliche-genehmigung-fuer-den-abbruch-der-nepomuk-bruecke-in-rech/)
describes three arches remaining after the flood; the
[DRK diver reconnaissance](https://www.kv-aw.drk.de/leichte-sprache/aktuelles-presse/aktuelle-informationen/meldung/pressemitteilung-07-22-drk-wasserwacht-rheinland-pfalz-uebt-in-der-ahr-wasserwachttaucher-begutachten-fundament-der-nepomukbruecke-in-rech.html)
reports destruction and observed undermining of foundations. These reports are
corroboration, not model-generated labels. The surviving arches were later
removed in July 2023, so current imagery would conflate the flood with later
clearance.

## Images, dates and rights

Each request returns a 1,024×1,024 original RGBA GeoTIFF in EPSG:25832 covering
409.6×409.6 m. The matching output grid has 0.4 m pixels. The pre-event source is
DOP20 (native 0.2 m) rendered to that grid; post-event DOP40 is native 0.4 m.
Original TIFF alpha/no-data is retained. Rech and Ahrweiler pairs have complete
alpha coverage; Dernau pre-event has six invalid edge pixels outside the
central demo crop. Observation coverage is not a structural reliability mask.

The per-chip before-image metadata explicitly assigns flight date
**2019-06-27**. Post-event center metadata says creation (`Erstellung`)
**2021-07-24**; this is not asserted to be the exact flight date. The collection
has flights **2021-07-24, 2021-07-28, 2021-07-29**. Post WMS publication metadata
is **2021-10-12** with unspecified timezone. These pairs support retrospective
comparison; they do not prove the images were available to responders on July
18. CEMS source scene time is 2021-07-18T10:50:00Z and product date is July 19,
so it is an earlier, separate agency observation.

| Target | Before source item | Post source item | Post WMS publication value |
| --- | --- | --- | --- |
| Rech | dop_32360_5596 | rgbi_32_360_559 | 2021-10-12 07:27:32.2 |
| Ahrweiler | dop_32364_5600 | rgbi_32_364_560 | 2021-10-12 07:27:38.404 |
| Dernau | dop_32362_5598 | rgbi_32_363_559 | 2021-10-12 07:27:33.687 |

The live [RLP layer metadata](https://www.geoportal.rlp.de/mapbender/php/mod_showMetadata.php?id=73160&languageCode=de&layout=tabs&resource=layer)
confirms 40 cm RGB orthophotos, no public access limitations and
[dl-de/by-2-0](https://www.govdata.de/dl-de/by-2-0). That license allows
presentation, processing and redistribution with attribution, dataset/license
links and a notice that data were edited. Use:

> ©GeoBasis-DE / LVermGeoRP 2026, dl-de/by-2-0, www.lvermgeo.rlp.de [Daten bearbeitet]

The demo panels crop the real imagery to 144×144 m around each agency centroid,
enlarge pixels using nearest-neighbour and add a rectangle around the full
crossing. The rectangle and captions are manual markings. No pixels are
reconstructed, filled or generated. Raw RGB PNGs and original TIFFs remain
available for independent review. Add the metadata and license links when
embedding the panel in the frontend or presentation.

## Reproduction and artifacts

Run with the existing locked environment and existing CEMS input:

```bash
uv run --group damage-research python scripts/prepare_bridge_demo_existing.py
```

Optional bounded selection:

```bash
uv run --group damage-research python scripts/prepare_bridge_demo_existing.py --targets rech ahrweiler
```

Each `data/research/bridge-demo-existing/<target>-manifest.json` contains the
exact CEMS geometry and original grade, coordinates, service URLs, source item
IDs, timestamps, CRS/grid, TIFF/PNG/panel SHA-256 checksums, license, evidence
links, manual interpretation and confidence. Source TIFF checksums are pinned
in the script and verified before regeneration. This script reuses the
repository's already verified WMS request protocol rather than changing an API
version. All downloaded and generated outputs are ignored by Git under `data/`.

The actual three pair retrievals succeeded anonymously; six image TIFFs were
opened and grids checked; source metadata HTML was fetched; all six images and
the three annotated comparison panels were visually reviewed. The pinned-cache
reproduction command also passed. No ML inference or damage-detector accuracy
measurement was performed in this spot check.

## Existing data inventory implications

BC and Ahr are the two configured production case studies. Existing ignored
research also includes BRIGHT Libya imagery and LADI U.S. disaster photographs,
while the current SpaceNet 8 experiment uses six Germany tiles. Thus the
repository's exploratory data is already broader than BC and Germany, but
those research samples were not yet a bridge-targeted demo. The six current
SpaceNet imagery footprints do not contain the Rech target; no additional
SpaceNet data were downloaded for this check.

For the hackathon, use a manually marked image comparison with attributed
agency status to show the intended bridge-monitoring workflow. Explain that
automatic bridge-damage localization is future work. A separate true-satellite
demo such as Derna can complement this existing-case aerial example.
