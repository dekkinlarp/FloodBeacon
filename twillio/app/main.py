import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from .config import Settings
from .db import connect, incident_dict, ingest, initialize
from .models import GeminiReport, IncidentPatch


# Inherit Uvicorn's console handler and INFO level for immediate webhook visibility.
log = logging.getLogger('uvicorn.error.intake')


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        initialize(settings)
        yield

    app = FastAPI(title='FloodLens rescue report intake', lifespan=lifespan)

    def operator(authorization: str = Header(default='')):
        if not settings.operator_api_key or settings.operator_api_key == 'replace-with-a-long-random-secret':
            raise HTTPException(503, 'Set a non-placeholder OPERATOR_API_KEY')
        if not hmac.compare_digest(authorization, 'Bearer ' + settings.operator_api_key):
            raise HTTPException(401, 'Operator authentication required')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'sms_dry_run': settings.sms_dry_run}

    @app.post('/webhooks/twilio/inbound')
    async def inbound(request: Request):
        if not all((settings.twilio_auth_token, settings.twilio_webhook_url, settings.twilio_phone_number)):
            raise HTTPException(503, 'Configure Twilio webhook settings')
        if len(await request.body()) > 65536:
            raise HTTPException(413, 'Request too large')
        form = await request.form()
        params = dict(form)
        validator = RequestValidator(settings.twilio_auth_token)
        if not validator.validate(settings.twilio_webhook_url, params,
                                  request.headers.get('X-Twilio-Signature', '')):
            raise HTTPException(403, 'Invalid Twilio signature')
        if any(not isinstance(params.get(key), str) or not params[key] for key in ('MessageSid', 'From', 'To', 'Body')):
            raise HTTPException(422, 'MessageSid, From, To and Body are required')
        if params['To'] != settings.twilio_phone_number:
            raise HTTPException(403, 'Unexpected recipient')
        if len(params['Body']) > 10000:
            raise HTTPException(413, 'Message too large')
        fresh = ingest(settings, params['MessageSid'], params['From'], params['To'], params['Body'])
        if fresh:
            log.info('Incoming SMS accepted and saved | message_sid=%s | characters=%s',
                     params['MessageSid'], len(params['Body']))
        else:
            log.info('Duplicate incoming SMS ignored | message_sid=%s', params['MessageSid'])
        reply = MessagingResponse()
        command = params['Body'].strip().upper()
        # Opt-out acknowledgement is handled by Twilio, not a competing app response.
        if fresh and command not in {'STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'START', 'UNSTOP'}:
            if command == 'NEW':
                text = 'New report started. Describe who needs help and their location, including house number and postal/ZIP code if known.'
            else:
                text = 'Report received by this prototype. No rescue has been dispatched. If in immediate danger, contact local emergency services if possible.'
            # Dry run must not send even a synchronous TwiML acknowledgement.
            if not settings.sms_dry_run:
                reply.message(text)
        return Response(str(reply), media_type='application/xml')

    @app.get('/incidents', dependencies=[Depends(operator)])
    def incidents(unlocated: bool = False):
        with connect(settings) as db:
            rows = db.execute('SELECT * FROM incidents ' + ('WHERE latitude IS NULL ' if unlocated else '') + 'ORDER BY updated_at DESC')
            return [incident_dict(r) for r in rows]

    @app.get('/incidents.geojson', dependencies=[Depends(operator)])
    def geojson():
        with connect(settings) as db:
            features = []
            for row in db.execute('SELECT * FROM incidents WHERE latitude IS NOT NULL'):
                # Deliberately exclude original SMS, phone numbers, and extracted free text.
                features.append({'type': 'Feature', 'id': row['id'],
                    'geometry': {'type': 'Point', 'coordinates': [row['longitude'], row['latitude']]},
                    'properties': {k: row[k] for k in ('id', 'verification_status', 'response_status',
                        'operational_priority', 'location_precision', 'updated_at', 'needs_review')}})
            return {'type': 'FeatureCollection', 'features': features}

    @app.get('/reports/unlocated', dependencies=[Depends(operator)])
    def unlocated():
        with connect(settings) as db:
            return [incident_dict(r) for r in db.execute('SELECT * FROM incidents WHERE latitude IS NULL ORDER BY updated_at DESC')]

    @app.get('/incidents/{incident_id}', dependencies=[Depends(operator)])
    def incident(incident_id: str):
        with connect(settings) as db:
            row = db.execute('SELECT * FROM incidents WHERE id=?', (incident_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Incident not found')
            obj = incident_dict(row)
            contact = db.execute('SELECT sender,recipient FROM conversations WHERE id=?',
                                 (row['conversation_id'],)).fetchone()
            obj['contact'] = dict(contact)
            obj['messages'] = [dict(r) for r in db.execute('''SELECT sid, body, received_at,status,error FROM messages
                WHERE conversation_id=? ORDER BY rowid''', (row['conversation_id'],))]
            obj['extractions'] = [dict(r) for r in db.execute('''SELECT e.* FROM extractions e JOIN messages m
                ON m.sid=e.message_sid WHERE m.conversation_id=? ORDER BY e.created_at''', (row['conversation_id'],))]
            obj['history'] = [dict(r) for r in db.execute('SELECT * FROM audit WHERE incident_id=? ORDER BY id', (incident_id,))]
            return obj

    @app.patch('/incidents/{incident_id}', dependencies=[Depends(operator)])
    def update_incident(incident_id: str, patch: IncidentPatch):
        with connect(settings) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM incidents WHERE id=?', (incident_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Incident not found')
            if row['version'] != patch.expected_version:
                raise HTTPException(409, 'Incident changed; refresh and review before updating')
            if patch.latitude is not None and len(json.loads(row['payload'])['situations']) != 1:
                raise HTTPException(422, 'Multi-location cases require splitting before assigning a point')
            changes = patch.model_dump(exclude_none=True, exclude={'reason', 'expected_version', 'clear_location'})
            if patch.clear_location:
                changes.update(latitude=None, longitude=None, location_precision=None, location_source=None)
            changes.update(version=row['version'] + 1, updated_at=time.time())
            if patch.verification_status is not None:
                changes['needs_review'] = int(patch.verification_status in {'unverified', 'disputed'})
            # Column names come exclusively from the validated server schema, never client strings.
            db.execute('UPDATE incidents SET ' + ','.join(k + '=?' for k in changes) + ' WHERE id=?',
                       (*changes.values(), incident_id))
            after = db.execute('SELECT * FROM incidents WHERE id=?', (incident_id,)).fetchone()
            db.execute('''INSERT INTO audit(incident_id,actor,reason,before_json,after_json,created_at)
                          VALUES (?,?,?,?,?,?)''',
                       (incident_id, 'operator', patch.reason, json.dumps(dict(row)), json.dumps(dict(after)), time.time()))
            return incident_dict(after)

    @app.get('/reports', dependencies=[Depends(operator)])
    def reports():
        # Includes pending/failed/unrelated messages even when no incident could be extracted.
        with connect(settings) as db:
            return [dict(r) for r in db.execute('''SELECT sid,conversation_id,body,received_at,status,attempts,error
                                                  FROM messages ORDER BY rowid DESC''')]

    @app.get('/reports/gemini', response_model=list[GeminiReport], dependencies=[Depends(operator)])
    def gemini_reports(
        response: Response,
        conversation_id: str | None = None,
        message_sid: str | None = None,
        help_only: bool = True,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        """Return saved per-message extractions, newest message first; never call Gemini on GET."""
        response.headers['Cache-Control'] = 'no-store'
        conditions = ["m.status != 'control'"]
        params = []
        if conversation_id is not None:
            conditions.append('m.conversation_id=?')
            params.append(conversation_id)
        if message_sid is not None:
            conditions.append('m.sid=?')
            params.append(message_sid)
        if help_only:
            # Pending and failed reports are unclassified, so retain them for visibility.
            conditions.append("(e.id IS NULL OR json_extract(e.payload, '$.report_type') IN ('rescue_request','update'))")
        query = """SELECT m.sid AS message_sid, m.conversation_id, m.received_at,
            m.status AS processing_status, m.error, e.id AS extraction_id,
            e.created_at AS generated_at, e.model, e.prompt_version, e.payload
            FROM messages m LEFT JOIN extractions e ON e.message_sid=m.sid
            WHERE """ + ' AND '.join(conditions) + ' ORDER BY m.rowid DESC LIMIT ? OFFSET ?'
        with connect(settings) as db:
            result = []
            for row in db.execute(query, (*params, limit, offset)):
                item = dict(row)
                payload = item.pop('payload')
                item['report'] = json.loads(payload) if payload is not None else None
                result.append(item)
            return result

    @app.get('/outbox', dependencies=[Depends(operator)])
    def outbox():
        with connect(settings) as db:
            return [dict(r) for r in db.execute('SELECT * FROM outbox ORDER BY created_at DESC')]

    return app


app = create_app()
