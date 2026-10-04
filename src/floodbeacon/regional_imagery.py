"""Prepare compact historical satellite XYZ tiles outside API request handling.

Only the preparation functions import GIS/Pillow libraries. Inputs are public
Maxar COG overviews read by HTTP ranges; raw full scenes are never downloaded.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

STUDY_BOUNDS = [6.88, 50.37, 7.17, 50.59]
WORLD = 20037508.342789244
TILE_SIZE = 256
STATIC = Path(__file__).with_name('static')
OUTPUT = STATIC / 'imagery/ahr-region'
LICENSE_URL = 'https://creativecommons.org/licenses/by-nc/4.0/'
ATTRIBUTION = 'Satellite imagery © Maxar Technologies; Open Data Program; CC BY-NC 4.0'
SOURCES = {
    '2021-02-11': ['10500500C4DD7000', '10500500C4DD7100'],
    '2021-07-18': ['10500500E6DD3C00'],
}


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tile_number(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    return (math.floor((lon + 180) / 360 * n),
            math.floor((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n))


def tile_range(bounds: list[float], zoom: int) -> tuple[int, int, int, int]:
    left, top = tile_number(bounds[0], bounds[3], zoom)
    right, bottom = tile_number(bounds[2], bounds[1], zoom)
    return left, top, right, bottom


def tile_mercator_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    size = 2 * WORLD / (2 ** zoom)
    return (-WORLD + x * size, WORLD - (y + 1) * size,
            -WORLD + (x + 1) * size, WORLD - y * size)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n')


def _source(date: str, scene: str, client) -> dict:
    phase = 'pre-event' if date < '2021-07-15' else 'post-event'
    prefix = f'events/western-europe-flooding21/{phase}/{date}/{scene}/'
    url = f'https://dg-opendata.s3.amazonaws.com/{prefix}{scene}.tif'
    response = client.head(url)
    response.raise_for_status()
    evidence_url = f'https://dg-opendata.s3.amazonaws.com/?list-type=2&prefix={prefix}'
    evidence = client.get(evidence_url)
    evidence.raise_for_status()
    if f'{scene}.tif' not in evidence.text:
        raise ValueError('Scene missing from acquisition-date archive folder')
    return {'catalog_id': scene, 'source_url': url, 'acquired_date': date,
            'acquired_at': None, 'date_precision': 'day; provider archive folder',
            'source_bytes': int(response.headers['content-length']),
            'source_etag': response.headers.get('etag'),
            'source_last_modified': response.headers.get('last-modified'),
            'source_sha256': None,
            'source_checksum_note': 'Full multi-gigabyte object was not downloaded; ETag is an object identity, not a SHA256.',
            'date_evidence_url': evidence_url,
            'date_evidence_sha256': hashlib.sha256(evidence.content).hexdigest(),
            'license': 'CC BY-NC 4.0', 'license_url': LICENSE_URL,
            'license_source': 'https://maxar-marketing.s3.amazonaws.com/files/downloads/119757_opendataprotocol_2020_04.pdf',
            'attribution': ATTRIBUTION}


def _window(source: dict, raw: Path, grid: tuple, width: int, height: int):
    """Retain one coarse, aligned RGB/mask window, never the full remote scene."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
    path = raw / f'{source["catalog_id"]}-z15-window.tif'
    metadata_path = path.with_suffix('.json')
    if path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if (metadata['source_etag'] == source['source_etag'] and
                metadata['width'] == width and metadata['height'] == height and
                metadata['output_transform'] == list(grid)[:6] and
                checksum(path) == metadata['window_sha256']):
            source.update(metadata)
            with rasterio.open(path) as dataset:
                return dataset.read()
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                      GDAL_HTTP_TIMEOUT='90', VSI_CACHE=True, GDAL_CACHEMAX=128 * 1024 * 1024):
        with rasterio.open(source['source_url']) as dataset:
            if dataset.count != 3 or dataset.dtypes != ('uint8',) * 3:
                raise ValueError('Expected three uint8 satellite RGB bands')
            source.update(source_crs=str(dataset.crs), source_transform=list(dataset.transform)[:6],
                          source_bounds=list(dataset.bounds),
                          source_wgs84_bounds=list(transform_bounds(dataset.crs, 4326, *dataset.bounds)),
                          source_shape=[dataset.height, dataset.width],
                          source_overviews=dataset.overviews(1))
        # Opening the overview explicitly is essential: a WarpedVRT around the
        # native source can read original-resolution blocks before downsampling.
        # Factor 8 pre-event and factor 4 post-event closely match this 3 m grid.
        overview_level = 2 if source['acquired_date'] == '2021-02-11' else 1
        source['read_overview_factor'] = 2 ** (overview_level + 1)
        with rasterio.open(source['source_url'], overview_level=overview_level) as overview:
            # These original RGB scenes have no declared nodata tag. Zero nodata
            # avoids turning their black exterior pixels into observed terrain.
            with WarpedVRT(overview, crs='EPSG:3857', transform=grid, width=width,
                           height=height, src_nodata=0, nodata=0,
                           resampling=Resampling.bilinear) as vrt:
                rgb = vrt.read()
    alpha = np.any(rgb != 0, axis=0).astype('uint8') * 255
    result = np.concatenate([rgb, alpha[None]], axis=0)
    with rasterio.open(path, 'w', driver='GTiff', width=width, height=height,
                       count=4, dtype='uint8', crs='EPSG:3857', transform=grid,
                       tiled=True, compress='deflate') as dataset:
        dataset.write(result)
    source.update(window_sha256=checksum(path), window_bytes=path.stat().st_size,
                  width=width, height=height, output_transform=list(grid)[:6],
                  output_crs='EPSG:3857')
    _write_json(metadata_path, source)
    return result


def prepare_region(raw: Path, output: Path = OUTPUT, maxzoom: int = 15) -> dict:
    """Build dated WebP XYZ pyramids and provenance with explicit no-data gaps."""
    import httpx
    import numpy as np
    from PIL import Image
    from rasterio.features import shapes
    from rasterio.transform import from_bounds
    from rasterio.warp import transform_bounds
    from shapely.geometry import shape, mapping, box
    from shapely.ops import transform, unary_union
    from pyproj import Transformer

    if maxzoom != 15:
        raise ValueError('The current published preparation grid is fixed at zoom 15')
    raw.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = tile_range(STUDY_BOUNDS, maxzoom)
    left, _, _, top = tile_mercator_bounds(x0, y0, maxzoom)
    _, bottom, right, _ = tile_mercator_bounds(x1, y1, maxzoom)
    width, height = (x1 - x0 + 1) * TILE_SIZE, (y1 - y0 + 1) * TILE_SIZE
    grid = from_bounds(left, bottom, right, top, width, height)
    clip_bounds = transform_bounds(4326, 3857, *STUDY_BOUNDS)
    xs = left + (np.arange(width) + .5) * grid.a
    ys = top + (np.arange(height) + .5) * grid.e
    study_mask = ((xs[None] >= clip_bounds[0]) & (xs[None] <= clip_bounds[2]) &
                  (ys[:, None] >= clip_bounds[1]) & (ys[:, None] <= clip_bounds[3]))
    sources, observations, assets = [], [], []
    retrieve_time = datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for date, scenes in SOURCES.items():
            rgba = np.zeros((4, height, width), dtype='uint8')
            date_sources = []
            for scene in scenes:
                source = _source(date, scene, client)
                window = _window(source, raw, grid, width, height)
                valid = window[3] > 0
                rgba[:, valid] = window[:, valid]
                sources.append(source)
                date_sources.append(scene)
                print(f'{date} read overview window {scene}', flush=True)
            rgba[3, ~study_mask] = 0
            valid = rgba[3] > 0
            coverage_fraction = float(valid[study_mask].mean())
            image = Image.fromarray(rgba.transpose(1, 2, 0))
            # Coverage is a coarse source-data availability outline, not an
            # inundation/cloud/reliability mask. Simplify in projected metres.
            stride = 16
            mask = valid[::stride, ::stride].astype('uint8')
            small_grid = grid * grid.scale(stride, stride)
            polys = [shape(geom) for geom, value in shapes(mask, mask=mask.astype(bool), transform=small_grid) if value]
            footprint = unary_union(polys).simplify(35).intersection(box(*clip_bounds))
            to_wgs = Transformer.from_crs(3857, 4326, always_xy=True).transform
            coverage = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
                        'geometry': mapping(transform(to_wgs, footprint)),
                        'properties': {'observation_id': f'ahr-2021-{date}',
                                       'meaning': 'Source RGB available; not a flood, cloud or reliability mask'}}]}
            coverage_path = output / f'{date}-coverage.geojson'
            _write_json(coverage_path, coverage)
            preview = image.copy()
            preview.thumbnail((1400, 1600), Image.Resampling.LANCZOS)
            preview_path = output / f'{date}-overview.webp'
            preview.save(preview_path, 'WEBP', quality=80, method=6)
            for zoom in range(8, maxzoom + 1):
                scale = 2 ** (maxzoom - zoom)
                level = image if scale == 1 else image.resize(
                    (width // scale, height // scale), Image.Resampling.LANCZOS)
                for x in range(tile_range(STUDY_BOUNDS, zoom)[0], tile_range(STUDY_BOUNDS, zoom)[2] + 1):
                    for y in range(tile_range(STUDY_BOUNDS, zoom)[1], tile_range(STUDY_BOUNDS, zoom)[3] + 1):
                        px0, py0 = x * TILE_SIZE - x0 * TILE_SIZE // scale, y * TILE_SIZE - y0 * TILE_SIZE // scale
                        tile = level.crop((px0, py0, px0 + TILE_SIZE, py0 + TILE_SIZE))
                        path = output / date / str(zoom) / str(x) / f'{y}.webp'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        tile.save(path, 'WEBP', quality=80, method=4)
            print(f'{date}: available RGB {coverage_fraction:.1%} of study pixels; pyramid written', flush=True)
            observations.append({'id': f'ahr-2021-{date}', 'acquired_date': date,
                'acquired_at': None, 'url': f'/static/imagery/ahr-region/{date}/{{z}}/{{x}}/{{y}}.webp',
                'tile_size': TILE_SIZE, 'minzoom': 8, 'maxzoom': maxzoom,
                'bounds': STUDY_BOUNDS, 'valid_coverage_fraction': coverage_fraction,
                'coverage': coverage,
                'coverage_url': f'/static/imagery/ahr-region/{coverage_path.name}',
                'overview_url': f'/static/imagery/ahr-region/{preview_path.name}',
                'source_catalog_ids': date_sources, 'license': 'CC BY-NC 4.0',
                'license_url': LICENSE_URL, 'attribution': ATTRIBUTION,
                'resolution_note': 'Zoom 15 is about 3 m ground sampling at this latitude; the Rech bridge detail uses the separately reviewed high-resolution crop.'})
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            assets.append({'url': '/static/' + path.relative_to(STATIC).as_posix(),
                           'sha256': checksum(path), 'bytes': path.stat().st_size})
    for observation in observations:
        observation['provenance'] = {'retrieved_at': retrieve_time,
            'sources': [source for source in sources if source['catalog_id'] in observation['source_catalog_ids']],
            'valid_coverage_fraction': observation['valid_coverage_fraction'],
            'coverage': observation['coverage'], 'coverage_url': observation['coverage_url'],
            'overview_url': observation['overview_url'],
            'output_crs': 'EPSG:3857', 'tile_scheme': 'XYZ',
            'processing': 'HTTP-range COG overviews, bilinear RGB, transparent zero exterior nodata, WebP quality 80. No fabricated pixels.'}
    manifest = {'case_id': 'ahr-2021', 'bounds': STUDY_BOUNDS,
                'name': 'Ahr Valley regional satellite imagery', 'output_crs': 'EPSG:3857',
                'tile_scheme': 'XYZ', 'observations': observations, 'sources': sources,
                'retrieved_at': retrieve_time, 'assets': assets,
                'processing': 'HTTP-range COG overview windows; common Web Mercator zoom-15 grid; bilinear RGB; zero exterior nodata; WebP quality 80; lower zooms Lanczos; no fabricated pixels.',
                'limitations': ['Transparent gaps are unobserved; they do not establish intact assets or passable routes.',
                    'Coverage outlines show RGB availability, not flood extent or complete cloud/shadow reliability.',
                    'Provider does not declare a nodata tag; all-zero RGB is treated as exterior nodata.',
                    'Exact UTC acquisition times and source-native GSD are not established.',
                    'The regional tiles are for orientation; structural bridge findings use reviewed high-resolution patches.',
                    'The study bounds are selected research coverage, not the whole-event flood boundary.']}
    _write_json(output / 'manifest.json', manifest)
    print(f'{len(assets)} assets, {sum(asset["bytes"] for asset in assets) / 2**20:.2f} MiB', flush=True)
    return manifest
