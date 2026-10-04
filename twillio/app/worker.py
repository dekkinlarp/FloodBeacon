"""Run exactly one worker process: python -m app.worker."""
import json
import logging
import time
from pathlib import Path
from twilio.rest import Client
from .config import Settings
from .conversation import next_question
from .db import connect, initialize, uid
from .extractor import GeminiExtractor, PROMPT_VERSION, validate_evidence

log = logging.getLogger(__name__)


def process_one(settings, extractor):
    now = time.time()
    claim = uid()
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''SELECT * FROM messages m WHERE
            (status='pending' OR (status='processing' AND lease_until < ?))
            AND NOT EXISTS (SELECT 1 FROM messages p WHERE p.conversation_id=m.conversation_id
              AND p.rowid < m.rowid AND p.status IN ('pending','processing'))
            ORDER BY m.rowid LIMIT 1''', (now,)).fetchone()
        if row is None:
            return False
        db.execute("UPDATE messages SET status='processing', attempts=attempts+1, lease_until=?, claim=? WHERE sid=?",
                   (now + 180, claim, row['sid']))
        history = [dict(r) for r in db.execute('''SELECT sid AS message_sid, body, received_at FROM messages
            WHERE conversation_id=? AND rowid <= (SELECT rowid FROM messages WHERE sid=?)
            AND status != 'control' ORDER BY rowid''', (row['conversation_id'], row['sid']))]
        # Include only questions actually submitted to Twilio, or previewed in dry-run.
        for index, message in enumerate(history):
            # A delayed worker must not interpret a reply against a question sent afterwards.
            cutoff = history[index + 1]['received_at'] if index + 1 < len(history) else row['received_at']
            question = db.execute("""SELECT body FROM outbox WHERE message_sid=?
                AND status IN ('sent','preview') AND available_at <= ?""",
                                  (message['message_sid'], cutoff)).fetchone()
            if question:
                message['assistant_followup'] = question['body']
    log.info('Processing message %s with Gemini (attempt %s/3)', row['sid'], row['attempts'] + 1)
    try:
        report = extractor.extract(history)
        validate_evidence(report, history)
        with connect(settings) as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT claim,status FROM messages WHERE sid=?', (row['sid'],)).fetchone()
            if current['claim'] != claim or current['status'] != 'processing':
                return True
            eid = uid()
            payload = report.model_dump_json()
            db.execute('INSERT INTO extractions VALUES (?,?,?,?,?,?)',
                       (eid, row['sid'], payload, settings.gemini_model, PROMPT_VERSION, time.time()))
            # One conversation is an assessment case; its situations remain separate in the report.
            # Multi-location cases cannot be pinned until an operator splits/reviews them externally.
            incident = db.execute('SELECT * FROM incidents WHERE conversation_id=?', (row['conversation_id'],)).fetchone()
            if report.situations:
                if incident is None:
                    iid = uid()
                    db.execute('''INSERT INTO incidents(id,conversation_id,extraction_id,payload,created_at,updated_at)
                                  VALUES (?,?,?,?,?,?)''', (iid, row['conversation_id'], eid, payload, now, now))
                else:
                    iid = incident['id']
                    old = json.loads(incident['payload'])
                    old_addresses = [s['address'] for s in old['situations']]
                    new_addresses = [s.address.model_dump() for s in report.situations]
                    changed = old_addresses != new_addresses or len(report.situations) != 1
                    db.execute('''UPDATE incidents SET extraction_id=?, payload=?, version=version+1,
                        needs_review=1, updated_at=?, verification_status='unverified' WHERE id=?''',
                               (eid, payload, now, iid))
                    if changed:
                        db.execute('''UPDATE incidents SET latitude=NULL,longitude=NULL,location_precision=NULL,
                                      location_source=NULL WHERE id=?''', (iid,))
                after = dict(db.execute('SELECT * FROM incidents WHERE id=?', (iid,)).fetchone())
                db.execute('''INSERT INTO audit(incident_id,actor,reason,before_json,after_json,created_at)
                              VALUES (?,?,?,?,?,?)''',
                           (iid, 'extractor', 'New unverified extraction; operational status unchanged',
                            json.dumps(dict(incident)) if incident else None, json.dumps(after), now))
            conversation = db.execute('SELECT * FROM conversations WHERE id=?', (row['conversation_id'],)).fetchone()
            asked = json.loads(conversation['questions'])
            question = next_question(report, asked)
            if question and not conversation['opted_out']:
                field, body = question
                db.execute('INSERT INTO outbox(id,message_sid,conversation_id,body,created_at) VALUES (?,?,?,?,?)',
                           (uid(), row['sid'], row['conversation_id'], body, now))
                db.execute('UPDATE conversations SET questions=? WHERE id=?',
                           (json.dumps(asked + [field]), row['conversation_id']))
            db.execute("UPDATE messages SET status='extracted', error=NULL, lease_until=NULL WHERE sid=?", (row['sid'],))
        log.info('Gemini report saved for message %s', row['sid'])
    except Exception as exc:
        # Do not log message contents, secrets, or raw provider exceptions.
        with connect(settings) as db:
            retry = row['attempts'] + 1 < 3
            db.execute('''UPDATE messages SET status=?, lease_until=?, error=? WHERE sid=? AND claim=?''',
                       ('processing' if retry else 'failed', time.time() + 30,
                        type(exc).__name__, row['sid'], claim))
        log.warning('Extraction failed for message %s (%s; HTTP=%s; status=%s)',
                    row['sid'], type(exc).__name__, getattr(exc, 'code', 'n/a'),
                    getattr(exc, 'status', 'n/a'))
    return True


def send_one(settings, sender=None):
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''SELECT o.*, c.sender,c.recipient,c.opted_out FROM outbox o
            JOIN conversations c ON c.id=o.conversation_id WHERE o.status='pending'
            ORDER BY o.created_at LIMIT 1''').fetchone()
        if row is None:
            return False
        status = 'suppressed' if row['opted_out'] else ('preview' if settings.sms_dry_run else 'sending')
        db.execute('UPDATE outbox SET status=?,available_at=? WHERE id=?',
                   (status, time.time() if status == 'preview' else None, row['id']))
    if status != 'sending':
        log.info('Follow-up %s: %s', row['id'], status)
        return True
    log.info('Submitting follow-up %s to Twilio', row['id'])
    try:
        if sender is None:
            sender = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        result = sender.messages.create(to=row['sender'], from_=row['recipient'], body=row['body'])
        with connect(settings) as db:
            db.execute("UPDATE outbox SET status='sent',provider_sid=?,available_at=? WHERE id=?",
                       (result.sid, time.time(), row['id']))
        log.info('Follow-up %s accepted by Twilio', row['id'])
    except Exception as exc:
        log.warning('Follow-up %s submission uncertain (%s); inspect Twilio logs', row['id'], type(exc).__name__)
        # Delivery might have succeeded: never blindly retry an ambiguous SMS send.
        with connect(settings) as db:
            db.execute("UPDATE outbox SET status='uncertain',error=? WHERE id=?", (type(exc).__name__, row['id']))
    return True


def log_status(settings):
    with connect(settings) as db:
        messages = dict(db.execute('SELECT status, COUNT(*) FROM messages GROUP BY status').fetchall())
        outbox = dict(db.execute('SELECT status, COUNT(*) FROM outbox GROUP BY status').fetchall())
    log.info(
        'Worker running | reports: pending=%s processing/retrying=%s extracted=%s failed=%s '
        '| SMS: queued=%s sending=%s accepted=%s preview=%s suppressed=%s uncertain=%s',
        *(messages.get(key, 0) for key in ('pending', 'processing', 'extracted', 'failed')),
        *(outbox.get(key, 0) for key in ('pending', 'sending', 'sent', 'preview', 'suppressed', 'uncertain')),
    )


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
    log.info('Starting rescue-report worker...')
    settings = Settings()
    initialize(settings)
    extractor = GeminiExtractor(settings)
    if not settings.sms_dry_run and not all((settings.twilio_account_sid, settings.twilio_auth_token)):
        raise RuntimeError('Twilio credentials required for outbound SMS')
    log.info('Listening for queued reports in %s (polling every second)', Path(settings.database_path).resolve())
    log.info('SMS mode: %s', 'DRY RUN (no messages sent)' if settings.sms_dry_run else 'LIVE')
    log.info('Keep the API and tunnel running to receive webhooks. Ctrl+C stops this worker.')
    log_status(settings)
    next_status = time.monotonic() + 30
    try:
        while True:
            processed = process_one(settings, extractor)
            sent = send_one(settings)
            if time.monotonic() >= next_status:
                log_status(settings)
                next_status = time.monotonic() + 30
            if not processed and not sent:
                time.sleep(1)
    except KeyboardInterrupt:
        log.info('Worker stopped.')


if __name__ == '__main__':
    main()
