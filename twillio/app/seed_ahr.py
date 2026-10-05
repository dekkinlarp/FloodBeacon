"""Insert clearly fictional, idempotent Ahr Valley dispatcher fixtures without providers."""
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .db import connect, initialize, incident_dict
from .models import Extraction

LABEL = '[SYNTHETIC AHR VALLEY DEMO]'
# Coordinates represent approximate neighbourhood locations, never verified homes.
CASES = [
    ('Rech', 50.5141, 7.0362, 3, 'Water is entering the ground floor; three people need evacuation.', ['rising water'], ['evacuation'], 'urgent', 'new'),
    ('Dernau', 50.533, 7.043, 2, 'Two people are upstairs; one needs a wheelchair-accessible evacuation.', ['flooded entrance'], ['accessible evacuation'], 'urgent', 'assessing'),
    ('Mayschoß', 50.521, 7.019, 4, 'Four people are sheltering upstairs and need drinking water and food.', ['street flooding'], ['drinking water', 'food'], 'routine', 'new'),
    ('Altenahr', 50.517, 6.992, 1, 'One person reports difficulty breathing and needs medical help; the entrance is flooded.', ['flooded entrance', 'reported breathing difficulty'], ['medical assistance', 'evacuation'], 'urgent', 'assessing'),
    ('Altenburg', 50.507, 6.99, 5, 'Five people including two children cannot leave because the street is flooded.', ['street flooding'], ['evacuation', 'shelter'], 'urgent', 'new'),
    ('Ahrbrück', 50.483, 6.974, 2, 'Two people need transport to shelter with their dog after leaving a flooded basement.', ['flooded basement'], ['shelter', 'pet-friendly transport'], 'routine', 'assessing'),
    ('Walporzheim', 50.532, 7.071, 1, 'One person cannot use the stairs without assistance and the elevator has lost power.', ['power outage', 'limited mobility'], ['accessible evacuation'], 'urgent', 'new'),
    ('Ahrweiler', 50.542, 7.095, 6, 'Six people are waiting upstairs for evacuation as water rises outside.', ['rising water'], ['evacuation'], 'urgent', 'new'),
    ('Bad Neuenahr', 50.544, 7.137, 2, 'Two people need medication and drinking water; floodwater blocks their exit.', ['blocked exit'], ['medication assistance', 'drinking water'], 'urgent', 'assessing'),
    ('Insul', 50.44, 6.914, 3, 'Three people report reaching shelter and no longer need evacuation.', [], [], 'routine', 'resolved'),
    ('Ahr Valley — location pending', None, None, 2, 'Two people are trapped upstairs in Ahr Valley; we do not know the street or house number.', ['trapped upstairs'], ['evacuation'], 'urgent', 'new'),
    ('Ahr Valley — location pending', None, None, None, 'A neighbour in Ahr Valley may need evacuation; their address and the number of people are unknown.', ['possible flooding'], ['evacuation'], 'unassigned', 'new'),
]


def seed(settings, now=None):
    initialize(settings)
    now = time.time() if now is None else now
    inserted = skipped = 0
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        for number, (area, lat, lon, people, narrative, hazards, needs, priority, status) in enumerate(CASES, 1):
            iid = f'demo-ahr-{number:03d}'
            cid, sid, eid = f'{iid}-conversation', f'{iid}-message', f'{iid}-extraction'
            if db.execute('SELECT 1 FROM incidents WHERE id=?', (iid,)).fetchone():
                skipped += 1
                continue
            timestamp = now - (number - 1) * 300
            body = f'{LABEL} Fictional exercise in {area}. {narrative}'
            address = {'city': area if lat is not None else None, 'region': 'Rhineland-Palatinate', 'country': 'Germany',
                       'location_detail': 'Fictional exercise in the Ahr Valley, not a historical rescue record; neighbourhood coordinates are illustrative, not a verified address.'}
            if lat is not None:
                address['landmark'] = area
            report = Extraction.model_validate({
                'report_type': 'update' if status == 'resolved' else 'rescue_request',
                'situations': [{
                    'summary': f'{LABEL} {area}: {narrative}',
                    'reporter_relationship': 'third_party' if number == 12 else 'self',
                    'people_count': people, 'address': address,
                    'reported_hazards': hazards, 'assistance_needs': needs,
                    'reported_resolution': status == 'resolved',
                    'evidence': [{'field': 'summary', 'message_sid': sid, 'quote': body}],
                }],
                'missing_information': ['house_number', 'street', 'postal_code'] + (['people_count'] if people is None else []),
                'conflicts': [],
            })
            payload = report.model_dump_json()
            db.execute('INSERT INTO conversations(id,sender,recipient,updated_at,opted_out) VALUES (?,?,?,?,1)',
                       (cid, f'demo:ahr:{number:03d}', 'demo:floodbeacon', timestamp))
            db.execute("INSERT INTO messages(sid,conversation_id,body,received_at,status) VALUES (?,?,?,?,'extracted')",
                       (sid, cid, body, timestamp))
            db.execute('INSERT INTO extractions(id,message_sid,payload,model,prompt_version,created_at) VALUES (?,?,?,?,?,?)',
                       (eid, sid, payload, 'synthetic-fixture', 'ahr-demo-v1', timestamp))
            db.execute('''INSERT INTO incidents(id,conversation_id,extraction_id,payload,
                       response_status,operational_priority,latitude,longitude,location_precision,
                       location_source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (iid, cid, eid, payload, status, priority, lat, lon,
                        'approximate' if lat is not None else None,
                        'Synthetic Ahr Valley demo: illustrative neighbourhood point, not geocoded or verified.' if lat is not None else None,
                        timestamp, timestamp))
            snapshot = incident_dict(db.execute('SELECT * FROM incidents WHERE id=?', (iid,)).fetchone())
            db.execute('INSERT INTO audit(incident_id,actor,reason,after_json,created_at) VALUES (?,?,?,?,?)',
                       (iid, 'synthetic-seeder', 'Fictional Ahr Valley demonstration; priorities and statuses are simulated.', json.dumps(snapshot), timestamp))
            inserted += 1
    return {'inserted': inserted, 'skipped': skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', help='Override DATABASE_PATH; otherwise use the app .env configuration.')
    args = parser.parse_args()
    settings = Settings()
    if args.database:
        settings = settings.model_copy(update={'database_path': args.database})
    path = Path(settings.database_path).resolve()
    if path.exists():
        backup_dir = path.parent / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = backup_dir / f'{path.stem}-before-ahr-{stamp}.sqlite3'
        source = sqlite3.connect(path)
        target = sqlite3.connect(backup)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        print(f'Database backup: {backup}', flush=True)
    result = seed(settings)
    print(f"Ahr Valley demo: {result['inserted']} inserted, {result['skipped']} already present. Database: {path}", flush=True)
    print('No SMS queued or Gemini calls made. All demo cases remain unverified.', flush=True)


if __name__ == '__main__':
    main()
