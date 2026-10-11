"""Place the synthetic incidents on real building footprints, clustered toward the river.

Help requests in a flood concentrate in riverside homes, so each site's 20 fictional
incidents are moved from a placeholder grid onto OpenStreetMap buildings, sampled with a
weight that falls off with distance to the nearest river (waterway=river; streams count
at a lower weight) and kept at least MIN_SPACING_M apart. Critical incidents take the
buildings closest to the water. Every other field is unchanged; the records stay fictional
(see each address_note).

Input is an Overpass JSON export per site (buildings + waterways, `out geom`), e.g.:

  [out:json];(way[building](S,W,N,E);way[waterway](S,W,N,E);way[natural=water](S,W,N,E););out geom;

with S,W,N,E = center ± (0.0024, 0.0038). Usage:

  python3 scripts/place-incidents.py ahr-2021 ahr.json
  python3 scripts/place-incidents.py derna-2023 derna.json
  python3 scripts/place-incidents.py nepal-2026 nepal.json

Deterministic: the RNG is seeded with the site id. Map data © OpenStreetMap contributors (ODbL).
"""

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = {
    'ahr-2021': {'center': (50.5141039, 7.03622715), 'file': ROOT / 'data/fake/incidents.json', 'key': None},
    'derna-2023': {'center': (32.7631, 22.6422), 'file': ROOT / 'data/scenarios/derna-2023.json', 'key': 'incidents'},
    'nepal-2026': {'center': (28.1649, 85.341), 'file': ROOT / 'data/scenarios/nepal-2026.json', 'key': 'incidents'},
}
# Visible extent at the default zoom (16), so every pin shows on first load; also clipped to
# the site's satellite imagery bounds (tests/logic/sites.test.ts checks this).
HALF_LAT, HALF_LON = 0.0019, 0.0032
CATALOG = ROOT / 'public/static/imagery/bridge-catalog/catalog.json'
EDGE_MARGIN = 0.00008
MIN_SPACING_M = 35
RIVER_FALLOFF_M = 110
STREAM_WEIGHT = 0.35
SEVERITY_ORDER = ['critical', 'high', 'medium', 'low']


def to_xy(lat, lon, lat0, lon0):
    """Local equirectangular metres around (lat0, lon0)."""
    return ((lon - lon0) * 111_320 * math.cos(math.radians(lat0)), (lat - lat0) * 110_540)


def segment_distance(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def main(site_id, osm_path):
    site = SITES[site_id]
    lat0, lon0 = site['center']
    elements = json.loads(Path(osm_path).read_text())['elements']
    w, s, e, n = next(c for c in json.loads(CATALOG.read_text())['cases'] if c['case']['id'] == site_id)['metadata']['imagery']['bounds']
    south, north = max(lat0 - HALF_LAT, s + EDGE_MARGIN), min(lat0 + HALF_LAT, n - EDGE_MARGIN)
    west, east = max(lon0 - HALF_LON, w + EDGE_MARGIN), min(lon0 + HALF_LON, e - EDGE_MARGIN)

    rivers, streams, buildings = [], [], []
    for el in elements:
        tags, geom = el.get('tags', {}), el.get('geometry') or []
        pts = [to_xy(g['lat'], g['lon'], lat0, lon0) for g in geom]
        if 'building' in tags and len(pts) >= 3:
            lat = sum(g['lat'] for g in geom) / len(geom)
            lon = sum(g['lon'] for g in geom) / len(geom)
            if south <= lat <= north and west <= lon <= east:
                buildings.append((lat, lon, to_xy(lat, lon, lat0, lon0)))
        elif tags.get('waterway') == 'river' or tags.get('natural') == 'water':
            rivers.append(pts)
        elif tags.get('waterway') == 'stream':
            streams.append(pts)

    def nearest(p, lines):
        return min((segment_distance(p, a, b) for line in lines for a, b in zip(line, line[1:])), default=math.inf)

    scored = []
    for lat, lon, p in buildings:
        d_river, d_stream = nearest(p, rivers), nearest(p, streams)
        weight = max(math.exp(-d_river / RIVER_FALLOFF_M), STREAM_WEIGHT * math.exp(-d_stream / RIVER_FALLOFF_M), 0.02)
        scored.append({'lat': lat, 'lon': lon, 'xy': p, 'water_m': min(d_river, d_stream), 'weight': weight})

    data = json.loads(site['file'].read_text())
    incidents = data if site['key'] is None else data[site['key']]
    rng = random.Random(site_id)
    chosen, pool = [], scored[:]
    while len(chosen) < len(incidents):
        pool = [b for b in pool if all(math.dist(b['xy'], c['xy']) >= MIN_SPACING_M for c in chosen)]
        if not pool:
            raise SystemExit(f'{site_id}: only {len(chosen)} buildings fit the spacing rule')
        pick = rng.choices(pool, weights=[b['weight'] for b in pool])[0]
        chosen.append(pick)

    # Most severe cases nearest the water, with a little jitter so it isn't a strict ladder.
    chosen.sort(key=lambda b: b['water_m'] * rng.uniform(0.8, 1.25))
    by_severity = sorted(range(len(incidents)), key=lambda i: SEVERITY_ORDER.index(incidents[i]['severity']))
    for index, place in zip(by_severity, chosen):
        incidents[index]['location'] = {'lat': round(place['lat'], 7), 'lon': round(place['lon'], 7)}

    site['file'].write_text(json.dumps(data, indent=2) + '\n')
    near = sum(b['water_m'] < 150 for b in chosen)
    print(f'{site_id}: {len(buildings)} buildings in view, placed {len(chosen)}, {near} within 150 m of water')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
