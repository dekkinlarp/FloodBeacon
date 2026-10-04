import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS conversations (
 id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
 updated_at REAL NOT NULL, questions TEXT NOT NULL DEFAULT '[]', opted_out INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
 sid TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 body TEXT NOT NULL, received_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, claim TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS extractions (
 id TEXT PRIMARY KEY, message_sid TEXT UNIQUE NOT NULL REFERENCES messages(sid),
 payload TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, extraction_id TEXT NOT NULL,
 payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 verification_status TEXT NOT NULL DEFAULT 'unverified', response_status TEXT NOT NULL DEFAULT 'new',
 operational_priority TEXT NOT NULL DEFAULT 'unassigned', needs_review INTEGER NOT NULL DEFAULT 1,
 latitude REAL, longitude REAL, location_precision TEXT, location_source TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL, actor TEXT NOT NULL,
 reason TEXT NOT NULL, before_json TEXT, after_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, message_sid TEXT UNIQUE NOT NULL, conversation_id TEXT NOT NULL,
 body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', provider_sid TEXT, error TEXT,
 created_at REAL NOT NULL, available_at REAL
);
CREATE INDEX IF NOT EXISTS message_jobs ON messages(status, received_at);
'''


def uid():
    return str(uuid.uuid4())


@contextmanager
def connect(settings):
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(settings):
    with connect(settings) as db:
        db.executescript(SCHEMA)


def incident_dict(row):
    obj = dict(row)
    obj['report'] = json.loads(obj.pop('payload'))
    obj['needs_review'] = bool(obj['needs_review'])
    obj['location_status'] = 'unresolved' if obj['latitude'] is None else obj['location_precision']
    return obj


def ingest(settings, sid, sender, recipient, body):
    now = time.time()
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM messages WHERE sid=?', (sid,)).fetchone():
            return False
        row = db.execute('SELECT * FROM conversations WHERE sender=? AND recipient=? ORDER BY updated_at DESC LIMIT 1',
                         (sender, recipient)).fetchone()
        command = body.strip().upper()
        # A new conversation never silently changes an earlier operational incident.
        if row is None or command == 'NEW' or now - row['updated_at'] > settings.session_hours * 3600:
            cid = uid()
            db.execute('INSERT INTO conversations(id,sender,recipient,updated_at,opted_out) VALUES (?,?,?,?,?)',
                       (cid, sender, recipient, now, row['opted_out'] if row else 0))
        else:
            cid = row['id']
        status = 'pending'
        if command in {'STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'START', 'UNSTOP', 'NEW'}:
            status = 'control'
            if command != 'NEW':
                db.execute('UPDATE conversations SET opted_out=? WHERE sender=? AND recipient=?',
                           (int(command not in {'START', 'UNSTOP'}), sender, recipient))
        db.execute('INSERT INTO messages(sid,conversation_id,body,received_at,status) VALUES (?,?,?,?,?)',
                   (sid, cid, body, now, status))
        db.execute('UPDATE conversations SET updated_at=? WHERE id=?', (now, cid))
        return True
