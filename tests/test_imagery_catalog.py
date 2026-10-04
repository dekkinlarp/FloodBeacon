"""Curated real-image contract checks; database writes are mocked here."""
from copy import deepcopy
import json
import struct
from unittest.mock import patch

import pytest

from floodbeacon import imagery


def catalog():
    return json.loads(imagery.CATALOG.read_text())


def test_curated_catalog_bytes_dimensions_and_temporal_coverage():
    data = catalog()
    imagery.validate_catalog(data)
    assert {record['case']['id'] for record in data['cases']} == {'ahr-2021', 'derna-2023', 'nepal-2026'}
    for record in data['cases']:
        for obs in record['observations']:
            for image in obs['images']:
                path = imagery.STATIC / image['url'].removeprefix('/static/')
                assert struct.unpack('>II', path.read_bytes()[16:24]) == (image['width'], image['height'])
                assert image['provenance']['output_crs'] == 'EPSG:3857'
                assert image['license_url'].startswith('https://creativecommons.org/')
    nepal = next(record for record in data['cases'] if record['case']['id'] == 'nepal-2026')
    recent = next(obs for obs in nepal['observations'] if obs['acquired_date'] == '2026-05-27')
    assert len(recent['images']) == 1
    assert recent['bridges']['features'][0]['properties']['bridge_id'] == 'syabrubesi-langtang-road-crossing'
    assert recent['bridges']['features'][0]['properties']['status'] == 'uncertain'
    germany = next(record for record in data['cases'] if record['case']['id'] == 'ahr-2021')
    assert all(obs['acquired_at'] is None for obs in germany['observations'])
    assert germany['metadata']['imagery']['bridges'][0]['agency_evidence']['grade'] == 'Destroyed'


def test_germany_catalog_exposes_regional_tiles_and_separate_agency_extent():
    germany = next(record for record in catalog()['cases'] if record['case']['id'] == 'ahr-2021')
    region = json.loads((imagery.STATIC / 'imagery/ahr-region/manifest.json').read_text())
    metadata = germany['metadata']['imagery']
    assert metadata['study_bounds'] == metadata['bounds'] == germany['case']['bbox'] == region['bounds']
    dated = {obs['acquired_date']: obs for obs in region['observations']}
    for obs in germany['observations']:
        tiles = obs['regional_tiles']
        assert tiles['url'] == dated[obs['acquired_date']]['url']
        assert tiles['provenance'] == dated[obs['acquired_date']]['provenance']
        assert tiles['license'] == 'CC BY-NC 4.0'
        assert obs['images'][0]['license'] == 'CC BY-SA 4.0'
    assert {f['properties']['notation'] for f in metadata['flood_extent']['features']} == {'Flooded area', 'Flood trace'}
    assert len(metadata['flood_extent']['features']) == 77
    assert metadata['flood_extent_source']['observed_at'] == '2021-07-18T10:50:00Z'
    urls = {asset['url'] for asset in germany['assets']}
    assert all(asset['url'] in urls for asset in region['assets'])


def test_changed_catalog_metadata_cannot_reuse_run_id():
    data = deepcopy(catalog())
    data['cases'][0]['observations'][0]['acquired_date'] = '2021-02-12'
    with pytest.raises(ValueError, match='fingerprint'):
        imagery.validate_catalog(data)


def test_asset_corruption_fails_before_database_mutation():
    with patch.object(imagery, 'digest', return_value='wrong'), patch('floodbeacon.db.init_db') as init:
        with pytest.raises(ValueError, match='checksum'):
            imagery.publish_catalog()
        init.assert_not_called()


def test_idempotent_publication_and_case_atomic_payload():
    data = catalog()
    with patch('floodbeacon.db.init_db') as init, patch('floodbeacon.db.get_run', return_value=None), \
         patch('floodbeacon.db.publish_run') as publish:
        result = imagery.publish_catalog(data)
        assert len(result) == 3 and all(row['status'] == 'published' for row in result)
        init.assert_called_once()
        assert publish.call_count == 3
        for call in publish.call_args_list:
            case, run, layers, observations = call.args
            assert case['id'] == run['case_id']
            assert run['metadata']['kind'] == 'bridge_imagery'
            assert layers['bridges']['features'] == [feature for obs in observations for feature in obs['bridges']['features']]
    with patch('floodbeacon.db.init_db'), patch('floodbeacon.db.get_run', return_value={'id': 'existing'}), \
         patch('floodbeacon.db.publish_run') as publish:
        result = imagery.publish_catalog(data)
        assert all(row['status'] == 'unchanged' for row in result)
        publish.assert_not_called()
