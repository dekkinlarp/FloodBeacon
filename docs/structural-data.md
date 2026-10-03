# Bridge inventory and structural-data limits

Research checked 2026-10-03. This note separates **where a structure is**, **what
an inventory says about it**, and **what an event assessment observed**. Those
are different records with different dates and meanings.

## Approved case studies

### Ahr Valley, Germany: EMSR517 AOI 15

The public [Rheinland-Pfalz ATKIS BasisDLM simplified service](https://www.geoportal.rlp.de/spatial-objects/354)
offers transport-structure points, lines and polygons (`ax_bauwerkimverkehrsbereich_*`)
with monthly freshness. Its metadata lists use as fee-based. This is useful
base geometry, not a bridge-engineering inventory; the spatial objects do not
provide deck elevation, foundation type/depth, design discharge, inspection
condition, scour readings or load capacity.

The [Rheinland-Pfalz road authority's inspection description](https://lbm.rlp.de/themen/bruecken/bauwerkspruefung)
describes a three-year alternating inspection cycle and condition grades. It
also cautions that an overall grade does not specify the damage type/severity
or establish structural stability. We did not find an open, structured archive
of Ahr-area bridge records or pre-event inspections. Requesting engineering
files from the responsible bridge owner would be a separate data-acquisition
step; availability and release terms are unknown.

[CEMS EMSR517 AOI 15](https://mapping.emergency.copernicus.eu/activations/EMSR517/)
does offer post-event interpretation in its vector product: transportation
features and `damage_gra` labels such as `Destroyed`, `Damaged`, `Possibly
Damaged`, `No visible damage`, and `Not Analysed`, plus separate observed flood
polygons. These are agency assessments based on event imagery, not a historic
engineering inspection and not FloodBeacon detector output. A no-visible-damage
grade does not prove sound structure or route passability. See [CEMS terms](https://mapping.emergency.copernicus.eu/terms-and-conditions/)
and [citation guidance](https://mapping.emergency.copernicus.eu/about/citation-guidelines/);
the interpreted vector product and original third-party imagery have distinct
rights.

### British Columbia: November 2021

The [Cascades District road-safety page](https://www2.gov.bc.ca/gov/content/industry/natural-resource-use/resource-roads/local-road-safety-information/cascades-road-safety-information)
links its **Flood Recovery November 2021 Impacted Routes and Structures Map**,
a DCS bridge inspection report, a district repair summary, a bridge KMZ, and a
2017 “Load Rated Structure Inventory Detailed Report.” The historical impact
map is useful route/structure evidence, but it is a static map (metadata date
May 2022), not a closure time series, bridge-by-bridge structural database, or
complete damage-label feed. The page's current road notices and closure statuses
change over time and must not be applied to November 2021.

The linked 2017 district load-rated report supplies fields such as structure
and site identifiers, road/crossing name, superstructure class, structure
length, coordinates, and rated load. It predates the flood and does not expose
deck elevation, design drawings, foundation dimensions, or measured scour.
The DCS inspection report exists at that official page, but its contents and
reuse terms have not been machine-verified here.

BC's [Ministry of Forests Bridges and Major Culverts public ArcGIS layer](https://delivery.maps.gov.bc.ca/arcgis/rest/services/whse/bcgw_pub_whse_forest_tenure/MapServer/38)
is queryable as point geometry in JSON/GeoJSON. The [catalogue record](https://catalogue.data.gov.bc.ca/dataset/df943320-9e31-421c-8ada-d4df80518684)
describes the public layer. The layer provides asset, road, location, structure
type and some current status/inspection attributes. It is a **present-day
inventory snapshot** when downloaded, not a 2021 snapshot. The public endpoint
alone does not settle redistribution rights; check the catalogue conditions.

ECCC's [daily hydrometric API](https://api.weather.gc.ca/collections/hydrometric-daily-mean?f=html)
and [daily climate API](https://api.weather.gc.ca/collections/climate-daily?f=html)
provide open query endpoints for the historical window. The selected
`08LG010` Coldwater River at Merritt daily series is gauge-level/discharge
context, not a water depth or velocity at any bridge. Daily climate stations
are filtered by the case bounding box and may have missing values and quality
flags. Preserve both. See the [HYDAT archive information](https://www.canada.ca/en/environment-climate-change/services/water-overview/quantity/monitoring/survey/data-products-services/national-archive-hydat.html)
for product context and Government of Canada terms.

## What a broader bridge benchmark can add

The US Federal Highway Administration's [National Bridge Inventory archive](https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm)
is a useful **transferability/reference source**, not a replacement for either
approved event. Public annual snapshots include 2021 and earlier years. Legacy
fields describe bridge location, material/type, dimensions and clearances,
load rating/posting, inspection date, deck/superstructure/substructure
condition (Items 58–60), channel condition (61), and scour-critical appraisal
(113). New [SNBI definitions and crosswalks](https://www.fhwa.dot.gov/bridge/snbi/datacrosswalk.cfm)
include more explicit scour condition, vulnerability and plan-of-action fields.
The NBI does not generally provide foundation dimensions, design drawings or
event-time bridge failure records.

FHWA warns that the annual NBI should not be used for route-clearance decisions:
inspection can be as infrequent as 24 months and the displayed clearance can
be stale. It is not a historical route-closure archive. State DOT 511 records,
incident logs or post-event reports would have to be acquired per event and
jurisdiction. NBI is publicly downloadable; retain FHWA/source attribution and
check any reuse conditions before republishing.

## Modeling implications

No machine learning is needed to parse these inventories, reproject geometries,
join agency labels to assets, or generate provenance. The useful baseline is
data integration plus a transparent exposure/access analysis. Keep distinct:

- **Reported condition:** the exact agency grade and source/date.
- **Observed flood:** an agency polygon or independently derived satellite mask.
- **Asset inventory:** a structure location/type/rating with its own snapshot date.
- **Exposure or scenario risk:** a model estimate with inputs, assumptions, and
  uncertainty; not observed structural damage.

An imagery model can help produce candidate flood masks or flag possible visual
change for review. It cannot infer that a bridge has failed from a nearby flood
mask, rain total, or current load rating. Bridge-specific collapse prediction
needs dated engineering/inspection and hydraulic attributes, scour/foundation
information, event-time conditions, and representative failure/non-failure
labels. Such data are not currently available in the public sources above.
Without them, show access-risk scenarios and explain the evidence; do not claim
a calibrated collapse probability or a “will fail in two days” forecast.
