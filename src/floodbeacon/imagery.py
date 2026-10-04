"""Curate checked-in bridge imagery and atomically publish metadata, never pixels.

Geospatial dependencies are imported only while rebuilding research TIFF windows.
Publishing an already-curated catalog needs the normal API environment only.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

STATIC = Path(__file__).with_name('static')
CATALOG = STATIC / 'imagery/bridge-catalog/catalog.json'
NC_LICENSE = 'https://creativecommons.org/licenses/by-nc/4.0/'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collection(features: list[dict]) -> dict:
    return {'type': 'FeatureCollection', 'features': features}


def union_bounds(bounds: list[list[float]]) -> list[float]:
    return [min(b[0] for b in bounds), min(b[1] for b in bounds),
            max(b[2] for b in bounds), max(b[3] for b in bounds)]


def observation_id(case_id: str, date: str) -> str:
    return f'{case_id}-{date}'


def review_square(coordinate: list[float], crs: int, size: float = 90) -> dict:
    from pyproj import Transformer
    forward = Transformer.from_crs(4326, crs, always_xy=True)
    reverse = Transformer.from_crs(crs, 4326, always_xy=True)
    x, y = forward.transform(*coordinate)
    half = size / 2
    ring = [list(reverse.transform(x + dx, y + dy)) for dx, dy in
            [(-half, -half), (half, -half), (half, half), (-half, half), (-half, -half)]]
    return {'type': 'Polygon', 'coordinates': [ring]}


def feature(bridge: dict, obs_id: str, date: str, geometry: dict,
            finding: str, status: str) -> dict:
    return {'type': 'Feature', 'id': f'{bridge["id"]}-{date}', 'geometry': geometry,
            'properties': {'bridge_id': bridge['id'], 'name': bridge['name'],
                           'observation_id': obs_id, 'observed_date': date,
                           'finding': finding, 'status': status,
                           'assessment_method': 'manual image review', 'failure_time': None,
                           'annotation': '90 m review square; not a surveyed damage boundary'}}


def _set_run_identity(record: dict) -> None:
    content = {key: value for key, value in record.items() if key != 'run'}
    fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    record['run'] = {'id': f'bridge-imagery-{fingerprint[:16]}',
                     'case_id': record['case']['id'], 'content_sha256': fingerprint}


def _case(case_id: str, name: str, country: str, bridges: list[dict],
          observations: list[dict], limitations: list[str]) -> dict:
    observations.sort(key=lambda obs: obs['acquired_date'])
    bounds = union_bounds([image['bounds'] for obs in observations for image in obs['images']])
    metadata = {'case_id': case_id, 'name': name, 'country': country,
                'bounds': bounds, 'bridges': bridges, 'limitations': limitations}
    record = {'case': {'id': case_id, 'name': name, 'bbox': bounds,
                       'description': 'Retrospective satellite bridge review; manual findings.'},
              'metadata': {'kind': 'bridge_imagery', 'imagery': metadata},
              'observations': observations,
              'layers': {'bridges': collection([f for o in observations for f in o['bridges']['features']])}}
    urls = {image['url'] for obs in observations for image in obs['images']}
    urls.update(bridge['comparison_url'] for bridge in bridges)
    record['assets'] = [{'url': url, 'sha256': digest(STATIC / url.removeprefix('/static/')),
                         'bytes': (STATIC / url.removeprefix('/static/')).stat().st_size}
                        for url in sorted(urls)]
    _set_run_identity(record)
    return record


def _add_regional_imagery(record: dict) -> dict:
    """Attach prepared regional tiles without fetching or processing imagery."""
    path = STATIC / 'imagery/ahr-region/manifest.json'
    if not path.exists():
        return record
    region = json.loads(path.read_text())
    if region['case_id'] != record['case']['id']:
        raise ValueError('Regional imagery case mismatch')
    metadata = record['metadata']['imagery']
    metadata['study_bounds'] = region['bounds']
    metadata['bounds'] = region['bounds']
    metadata['name'] = 'Ahr Valley — regional flood and bridge review'
    metadata['limitations'] = list(dict.fromkeys(metadata['limitations'] + region['limitations']))
    record['case'].update(name=metadata['name'], bbox=region['bounds'])
    dated = {item['acquired_date']: item for item in region['observations']}
    for observation in record['observations']:
        source = dated.get(observation['acquired_date'])
        if source is None:
            continue
        observation['regional_tiles'] = {
            key: source[key] for key in ['url', 'bounds', 'minzoom', 'maxzoom',
                                        'tile_size', 'attribution', 'license',
                                        'license_url', 'provenance']
        }
    extent = path.with_name('flood-extent.geojson')
    extent_source = path.with_name('flood-extent-source.json')
    metadata['flood_extent'] = json.loads(extent.read_text())
    metadata['flood_extent_source'] = json.loads(extent_source.read_text())
    assets = {asset['url']: asset for asset in record['assets'] + region['assets']}
    for file in [path, extent, extent_source]:
        url = '/static/' + file.relative_to(STATIC).as_posix()
        assets[url] = {'url': url, 'sha256': digest(file), 'bytes': file.stat().st_size}
    record['assets'] = [assets[url] for url in sorted(assets)]
    _set_run_identity(record)
    return record


def _rech() -> dict:
    manifest = json.loads((STATIC / 'imagery/rech-satellite/manifest.json').read_text())
    fc = json.loads((STATIC / 'imagery/rech-satellite/bridges.geojson').read_text())
    bridge = {'id': 'rech-nepomuk', 'name': manifest['target'],
              'coordinate': manifest['target_coordinate'], 'failure_time': None,
              'comparison_url': manifest['comparison_url'],
              'before_url': manifest['images'][0]['url'], 'after_url': manifest['images'][1]['url'],
              'agency_evidence': manifest['agency_evidence'], 'limitations': manifest['limitations']}
    observations = []
    for i, source in enumerate(manifest['images']):
        obs_id = observation_id('ahr-2021', source['acquired_date'])
        image = {k: source[k] for k in ['url', 'width', 'height', 'sha256', 'bytes']}
        image.update(id=f'rech-{source["id"]}', bounds=manifest['bounds'],
                     image_coordinates=manifest['image_coordinates'],
                     attribution=manifest['attribution'], license=manifest['license'],
                     license_url=manifest['license_url'],
                     provenance={**source, 'retrieved_at': manifest['retrieved_at'],
                                 'output_crs': manifest['output_crs'],
                                 'output_transform': manifest['output_transform'],
                                 'processing': manifest['processing'],
                                 'dataset': manifest['dataset'], 'license_source': manifest['license_source'],
                                 'publication_time': None, 'availability_time': None})
        observations.append({'id': obs_id, 'acquired_date': source['acquired_date'],
                             'acquired_at': source['acquired_at'],
                             'label': 'Before flood' if i == 0 else 'After flood', 'images': [image],
                             'bridges': collection([feature(bridge, obs_id, source['acquired_date'],
                                                           fc['features'][i]['geometry'],
                                                           fc['features'][i]['properties']['finding'],
                                                           'visible_crossing' if i == 0 else 'missing_span')])})
    return _add_regional_imagery(_case('ahr-2021', 'Ahr Valley — Rech', 'Germany',
                                     [bridge], observations, manifest['limitations']))


def _portable_provenance(source: dict) -> dict:
    """Keep evidence metadata without machine-specific local file paths."""
    return {k: v for k, v in source.items()
            if k not in {'png', 'png_path', 'geotiff', 'geotiff_path', 'stac_path'}}


def _research_image(source: dict, directory: str, image_id: str,
                    license: str, attribution: str, retrieval_time: str | None) -> dict:
    import numpy as np
    from PIL import Image
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds
    tif = Path(source.get('geotiff', source.get('geotiff_path', '')))
    expected = source.get('geotiff_sha256', source.get('sha256', {}).get(tif.name))
    if expected is None or digest(tif) != expected:
        raise ValueError(f'Source TIFF checksum mismatch: {tif.name}')
    destination = STATIC / f'imagery/{directory}/{image_id}.png'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tif) as ds:
        if ds.dtypes[:3] != ('uint8', 'uint8', 'uint8'):
            raise ValueError(f'Expected RGB uint8 source: {tif.name}')
        grid, width, height = calculate_default_transform(ds.crs, 'EPSG:3857', ds.width, ds.height, *ds.bounds)
        rgba = np.zeros((4, height, width), dtype=np.uint8)
        # Avoid interpolating invalid pixels into observed RGB.
        for index in range(3):
            reproject(rasterio.band(ds, index + 1), rgba[index], src_transform=ds.transform,
                      src_crs=ds.crs, src_nodata=ds.nodata, dst_transform=grid,
                      dst_crs='EPSG:3857', resampling=Resampling.bilinear)
        reproject(ds.dataset_mask(), rgba[3], src_transform=ds.transform, src_crs=ds.crs,
                  dst_transform=grid, dst_crs='EPSG:3857', resampling=Resampling.nearest)
        bounds = list(transform_bounds('EPSG:3857', 'EPSG:4326', grid.c,
                                       grid.f + grid.e * height, grid.c + grid.a * width, grid.f))
    Image.fromarray(rgba.transpose(1, 2, 0)).save(destination)
    west, south, east, north = bounds
    provenance = _portable_provenance(source)
    provenance.update(retrieved_at=source.get('retrieved_at', retrieval_time),
                      output_crs='EPSG:3857', output_transform=list(grid)[:6],
                      publication_time=source.get('publication_time'), availability_time=None,
                      processing='Native RGB window warped to Web Mercator; bilinear RGB, nearest source validity mask; no color enhancement.')
    return {'id': image_id, 'url': f'/static/imagery/{directory}/{destination.name}',
            'bounds': bounds, 'image_coordinates': [[west, north], [east, north], [east, south], [west, south]],
            'width': width, 'height': height, 'sha256': digest(destination), 'bytes': destination.stat().st_size,
            'license': license, 'license_url': NC_LICENSE, 'attribution': attribution, 'provenance': provenance}


def _comparison(before: dict, after: dict, coordinate: list[float], destination: Path) -> str:
    """A small, dated visual index; map imagery retains its unannotated pixels."""
    from PIL import Image, ImageDraw
    from pyproj import Transformer
    transform = Transformer.from_crs(4326, 3857, always_xy=True)
    x, y = transform.transform(*coordinate)
    canvas = Image.new('RGB', (720, 390), '#17212f')
    draw = ImageDraw.Draw(canvas)
    for index, record in enumerate([before, after]):
        image = record['images'][0]
        # Caller passes a single bridge patch, not the entire observation.
        png = STATIC / image['url'].removeprefix('/static/')
        a, _, c, _, e, f = image['provenance']['output_transform']
        px, py = (x - c) / a, (y - f) / e
        half = 90 / (abs(a) * math.cos(math.radians(coordinate[1])))
        with Image.open(png) as source:
            crop = source.crop((int(px-half), int(py-half), int(px+half), int(py+half)))
            crop = crop.resize((352, 352), Image.Resampling.NEAREST)
            canvas.paste(crop, (index * 360 + 4, 30))
        draw.text((index * 360 + 10, 10), record['acquired_date'], fill='white')
        draw.rectangle((index*360+92,118,index*360+268,294),outline='#ffdc57',width=2)
    canvas.save(destination)
    return f'/static/{destination.relative_to(STATIC).as_posix()}'


def _research(root: Path, case_id: str, name: str, country: str, directory: str,
              source_relative: str, crs: int) -> dict:
    manifest = json.loads((root / source_relative).read_text())
    limits = ['Exact failure time is unknown.', 'Review squares are annotations, not surveyed damage boundaries.',
              'Manual satellite review does not establish surrounding route passability.',
              'No precision image coregistration or automated damage model was used.']
    if country == 'Nepal':
        limits.append(manifest['interpretation'])
    else:
        limits.append(manifest['reference_caveat'])
    grouped, bridges = {}, []
    for target in manifest['targets']:
        coordinate = target.get('coordinate') or [target['lon'], target['lat']]
        bridge = {'id': target['id'], 'name': target['name'], 'coordinate': coordinate,
                  'failure_time': None, 'agency_evidence': None, 'limitations': limits,
                  'coordinate_source': target.get('coordinate_source', target.get('coordinate_method'))}
        if country == 'Libya':
            bridge['agency_evidence'] = {'source': 'UNOSAT', 'source_url': manifest['independent_reference'],
                                         'grade': 'Destroyed bridges (area assessment)',
                                         'note': manifest['reference_caveat'] + ' Exact inventory identity was not independently matched.'}
        phases = dict(target['images'])
        if 'recent_pre_event_reference' in target:
            phases['recent-reference'] = target['recent_pre_event_reference']
        patch_records = {}
        for phase, source in phases.items():
            acquired = source.get('acquired_at', source.get('acquisition_time_utc')).replace(' ', 'T')
            date = acquired[:10]
            obs_id = observation_id(case_id, date)
            image = _research_image(source, directory, f'{target["id"]}-{phase}',
                                    source.get('license', manifest['license']),
                                    source.get('attribution', manifest['attribution']),
                                    manifest.get('retrieval_time_utc'))
            image['provenance']['license_source'] = manifest.get('license_source', manifest.get('collection_url'))
            if phase == 'recent-reference':
                image['provenance']['license_source'] = 'https://data.source.coop/planet/disasterdata/nepal-flash-flood-2026-08-26/pre-event/planetscope-2026-05-27/collection.json'
            obs = grouped.setdefault(date, {'id': obs_id, 'acquired_date': date, 'acquired_at': acquired,
                                            'label': 'Earlier baseline' if phase == 'before' else
                                                     'After flood' if phase == 'after' else 'Recent 3 m road reference',
                                            'images': [], 'bridges': collection([])})
            obs['images'].append(image)
            status = 'missing_span' if phase == 'after' else 'visible_crossing'
            finding = target['finding'] if phase == 'after' else 'Continuous crossing visible in this image; structural safety unverified.'
            if phase == 'recent-reference':
                finding = source['manual_finding']
                status = 'uncertain'  # Coarse intact-looking visual evidence, not a high-resolution continuity confirmation.
            obs['bridges']['features'].append(feature(bridge, obs_id, date, review_square(coordinate, crs), finding, status))
            patch_records[phase] = {'acquired_date': date, 'images': [image]}
        bridge.update(before_url=patch_records['before']['images'][0]['url'],
                      after_url=patch_records['after']['images'][0]['url'])
        comparison = STATIC / f'imagery/{directory}/{target["id"]}-comparison.png'
        bridge['comparison_url'] = _comparison(patch_records['before'], patch_records['after'], coordinate, comparison)
        bridges.append(bridge)
    return _case(case_id, name, country, bridges, list(grouped.values()), limits)


def build_catalog(root: Path) -> dict:
    cases = [_rech(),
             _research(root, 'derna-2023', 'Derna — Wadi crossings', 'Libya', 'derna-satellite',
                       'data/research/bridge-demo-other/manifest.json', 32634),
             _research(root, 'nepal-2026', 'Syabrubesi — Trishuli crossings', 'Nepal', 'nepal-satellite',
                       'data/research/bridge-demo-nepal/manifest.json', 32645)]
    catalog = {'schema_version': 1, 'cases': cases}
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    for directory, attribution in [('derna-satellite', '© Maxar 2023'),
                                    ('nepal-satellite', 'Vantor Open Data Program; Planet Labs PBC / Planet Crisis Response Program')]:
        (STATIC / f'imagery/{directory}/README.md').write_text(
            f'# Curated bridge imagery\n\n{attribution}. CC BY-NC 4.0.\n\n'
            f'License: {NC_LICENSE}\n\nImages are noncommercial research/demo derivatives. '
            'Source URLs, acquisitions, original and output checksums, source CRS and processing '
            'are recorded per image in ../bridge-catalog/catalog.json. '
            'Web Mercator warps preserve source validity masks. Review comparisons use nearest-neighbour crop zooms. '
            'Manual annotations are not automated detection or surveyed damage extents.\n')
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: dict) -> None:
    """Verify committed bytes and temporal/geometry contract without GIS libraries."""
    for record in catalog['cases']:
        content = {k: v for k, v in record.items() if k != 'run'}
        fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if record['run']['content_sha256'] != fingerprint or record['run']['id'] != f'bridge-imagery-{fingerprint[:16]}':
            raise ValueError('Catalog content does not match immutable run fingerprint')
        for asset in record['assets']:
            path = STATIC / asset['url'].removeprefix('/static/')
            if digest(path) != asset['sha256'] or path.stat().st_size != asset['bytes']:
                raise ValueError(f'Curated asset checksum mismatch: {path.name}')
        seen = set()
        for obs in record['observations']:
            if obs['id'] in seen or not obs['images']:
                raise ValueError('Observation IDs must be unique and have imagery')
            seen.add(obs['id'])
            if obs['id'] != observation_id(record['case']['id'], obs['acquired_date']):
                raise ValueError('Observation date mismatch')
            for image in obs['images']:
                path = STATIC / image['url'].removeprefix('/static/')
                if digest(path) != image['sha256'] or path.stat().st_size != image['bytes']:
                    raise ValueError(f'Curated image checksum mismatch: {image["id"]}')
                if len(image['image_coordinates']) != 4:
                    raise ValueError('Image source requires four WGS84 corners')
            for bridge in obs['bridges']['features']:
                props = bridge['properties']
                if props['observed_date'] != obs['acquired_date'] or props['observation_id'] != obs['id']:
                    raise ValueError('Bridge finding date mismatch')
                if props['failure_time'] is not None:
                    raise ValueError('Reviewed crossings have no known failure time')
                ring = bridge['geometry']['coordinates'][0]
                if ring[0] != ring[-1] or len(ring) != 5:
                    raise ValueError('Review square must be a closed polygon')


def publish_catalog(catalog_path: Path | str | dict | None = None) -> list[dict]:
    from . import db
    catalog = catalog_path if isinstance(catalog_path, dict) else json.loads(Path(catalog_path or CATALOG).read_text())
    validate_catalog(catalog)
    db.init_db()
    published = []
    for record in catalog['cases']:
        run = deepcopy(record['run'])
        existing = db.get_run(run['case_id'], run['id'])
        if existing is not None:
            published.append({'case_id': run['case_id'], 'run_id': run['id'], 'status': 'unchanged'})
            continue
        run.update(generated_at=datetime.now(timezone.utc).isoformat(), metadata=record['metadata'])
        db.publish_run(record['case'], run, record['layers'], record['observations'])
        published.append({'case_id': run['case_id'], 'run_id': run['id'], 'status': 'published'})
    return published
