"""Checks the published regional tiles and XYZ geometry, not damage detection."""
import hashlib
import json
from pathlib import Path

import pytest

from floodbeacon.regional_imagery import (OUTPUT, STUDY_BOUNDS, WORLD,
                                          tile_mercator_bounds, tile_number, tile_range)


def test_xyz_coordinates_cover_study_and_share_edges():
    assert tile_number(0, 0, 0) == (0, 0)
    assert tile_mercator_bounds(0, 0, 0) == (-WORLD, -WORLD, WORLD, WORLD)
    west, north, east, south = tile_range(STUDY_BOUNDS, 15)
    assert west < east and north < south
    tile = tile_mercator_bounds(west, north, 15)
    neighbor = tile_mercator_bounds(west + 1, north, 15)
    assert tile[2] == pytest.approx(neighbor[0])
    assert tile[1] == neighbor[1] and tile[3] == neighbor[3]


def test_published_regional_tiles_dates_masks_and_integrity():
    manifest_path = OUTPUT / 'manifest.json'
    if not manifest_path.exists():
        pytest.skip('Regional source preparation has not finished')
    manifest = json.loads(manifest_path.read_text())
    assert manifest['bounds'] == STUDY_BOUNDS
    assert {o['acquired_date'] for o in manifest['observations']} == {'2021-02-11', '2021-07-18'}
    assert len(manifest['sources']) == 3
    for source in manifest['sources']:
        assert source['source_sha256'] is None
        assert source['source_etag'] and source['window_sha256']
        assert source['read_overview_factor'] in (4, 8)
        assert source['license'] == 'CC BY-NC 4.0'
    for observation in manifest['observations']:
        assert observation['acquired_at'] is None
        assert 0 < observation['valid_coverage_fraction'] < 1
        assert observation['minzoom'] == 8 and observation['maxzoom'] == 15
        assert observation['tile_size'] == 256
        assert observation['coverage']['type'] == 'FeatureCollection'
        assert len(observation['coverage']['features']) == 1
        assert '{z}/{x}/{y}.webp' in observation['url']
    for asset in manifest['assets']:
        path = OUTPUT.parents[1] / asset['url'].removeprefix('/static/')
        assert path.stat().st_size == asset['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset['sha256']
    assert sum(asset['bytes'] for asset in manifest['assets']) < 100 * 2**20
