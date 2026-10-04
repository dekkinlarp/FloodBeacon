import json
import time
import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from app.config import Settings
from app.db import connect, ingest, initialize
from app.main import create_app
from app.models import Extraction, Situation, Address, Evidence
from app.worker import process_one, send_one


@pytest.fixture
def settings(tmp_path):
    s = Settings(_env_file=None, database_path=str(tmp_path / 'test.sqlite3'),
        operator_api_key='test-operator', twilio_auth_token='test-token',
        twilio_webhook_url='https://intake.example/webhooks/twilio/inbound',
        twilio_phone_number='+15550000001', sms_dry_run=True)
    initialize(s)
    return s


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


AUTH = {'Authorization': 'Bearer test-operator'}


def sms(settings, sid='SM1', body='Help, four people upstairs', sender='+15550000002'):
    ingest(settings, sid, sender, settings.twilio_phone_number, body)


class FakeExtractor:
    def __init__(self, address=None, multiple=False, resolved=False):
        self.address = address or Address()
        self.multiple = multiple
        self.resolved = resolved

    def extract(self, history):
        self.history = history
        last = history[-1]
        s = Situation(summary='Reported need for assistance', people_count=4, address=self.address,
            reported_resolution=self.resolved,
            evidence=[Evidence(field='summary', message_sid=last['message_sid'], quote=last['body'])])
        return Extraction(report_type='rescue_request', situations=[s, s] if self.multiple else [s])


def test_webhook_signature_idempotency_and_dry_run(settings, client):
    data = {'MessageSid': 'SM1', 'From': '+15550000002', 'To': settings.twilio_phone_number, 'Body': 'Help'}
    assert client.post('/webhooks/twilio/inbound', data=data).status_code == 403
    signature = RequestValidator(settings.twilio_auth_token).compute_signature(settings.twilio_webhook_url, data)
    for _ in range(2):
        r = client.post('/webhooks/twilio/inbound', data=data, headers={'X-Twilio-Signature': signature})
        assert r.status_code == 200
        assert '<Message>' not in r.text
    assert len(client.get('/reports', headers=AUTH).json()) == 1


def test_house_number_then_postal_code_and_unknown(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor(Address(street='Example Road', city='Abbotsford')))
    send_one(settings)
    assert 'house/building number' in client.get('/outbox', headers=AUTH).json()[0]['body']
    sms(settings, 'SM2', '123A')
    fake = FakeExtractor(Address(house_number='123A', street='Example Road', city='Abbotsford'))
    process_one(settings, fake)
    assert 'assistant_followup' in fake.history[0]
    send_one(settings)
    assert any('postal/ZIP' in x['body'] for x in client.get('/outbox', headers=AUTH).json())
    sms(settings, 'SM3', 'UNKNOWN')
    process_one(settings, FakeExtractor(Address(house_number='123A', street='Example Road', city='Abbotsford',
        unavailable_fields=['postal_code'])))
    assert len(client.get('/outbox', headers=AUTH).json()) == 2
    incidents = client.get('/incidents', headers=AUTH).json()
    assert len(incidents) == 1
    assert incidents[0]['report']['situations'][0]['address']['house_number'] == '123A'
    assert incidents[0]['report']['situations'][0]['address']['postal_code'] is None
    assert len(client.get('/reports/unlocated', headers=AUTH).json()) == 1


def test_map_auth_manual_location_and_stale_updates(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor())
    assert client.get('/incidents').status_code == 401
    assert client.get('/incidents.geojson').status_code == 401
    assert client.get('/incidents.geojson', headers=AUTH).json()['features'] == []
    i = client.get('/incidents', headers=AUTH).json()[0]
    patch = {'expected_version': 1, 'reason': 'Location checked against address record',
        'latitude': 49.0, 'longitude': -122.0, 'location_precision': 'approximate',
        'location_source': 'operator review', 'verification_status': 'corroborated'}
    assert client.patch('/incidents/' + i['id'], headers=AUTH, json=patch).status_code == 200
    assert client.patch('/incidents/' + i['id'], headers=AUTH, json=patch).status_code == 409
    feature = client.get('/incidents.geojson', headers=AUTH).json()['features'][0]
    assert feature['geometry']['coordinates'] == [-122.0, 49.0]
    assert 'body' not in feature['properties']
    # Correcting an address invalidates a previously assigned map pin.
    sms(settings, 'SM2', 'Actually 99 Other Road')
    process_one(settings, FakeExtractor(Address(house_number='99', street='Other Road')))
    assert client.get('/incidents.geojson', headers=AUTH).json()['features'] == []


def test_extraction_failure_retained_and_bounded_retry(settings, client):
    class Broken:
        def extract(self, history):
            raise RuntimeError('provider failure containing sensitive data')
    sms(settings)
    for _ in range(3):
        assert process_one(settings, Broken())
        with connect(settings) as db:
            db.execute('UPDATE messages SET lease_until=0')
    report = client.get('/reports', headers=AUTH).json()[0]
    assert report['status'] == 'failed'
    assert report['body'] == 'Help, four people upstairs'
    assert report['error'] == 'RuntimeError'
    assert not process_one(settings, Broken())


def test_false_evidence_rejected(settings, client):
    class Hallucinated:
        def extract(self, history):
            return Extraction(report_type='rescue_request', situations=[Situation(summary='Invented',
                evidence=[Evidence(field='summary', message_sid='SM1', quote='not in the original')])])
    sms(settings)
    process_one(settings, Hallucinated())
    assert client.get('/incidents', headers=AUTH).json() == []


def test_stop_suppresses_queued_question(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor())
    sms(settings, 'SM2', 'STOP')
    send_one(settings)
    assert client.get('/outbox', headers=AUTH).json()[0]['status'] == 'suppressed'


def test_multiple_locations_stay_unlocated(settings, client):
    sms(settings, body='Help at two houses')
    process_one(settings, FakeExtractor(multiple=True))
    i = client.get('/incidents', headers=AUTH).json()[0]
    assert len(i['report']['situations']) == 2
    assert client.get('/outbox', headers=AUTH).json() == []
    response = client.patch('/incidents/' + i['id'], headers=AUTH, json={
        'expected_version': 1, 'reason': 'test', 'latitude': 49, 'longitude': -122,
        'location_precision': 'address', 'location_source': 'manual'})
    assert response.status_code == 422


def test_reported_resolution_does_not_dispatch_or_close(settings, client):
    sms(settings, body='We got out safely')
    process_one(settings, FakeExtractor(resolved=True))
    i = client.get('/incidents', headers=AUTH).json()[0]
    assert i['response_status'] == 'new'
    assert i['operational_priority'] == 'unassigned'
    assert i['report']['situations'][0]['reported_resolution'] is True
    assert client.get('/outbox', headers=AUTH).json() == []


def test_sms_failure_is_not_retried(settings, client):
    class FailingSender:
        @property
        def messages(self):
            return self
        def create(self, **kwargs):
            raise TimeoutError()
    sms(settings)
    process_one(settings, FakeExtractor())
    settings.sms_dry_run = False
    assert send_one(settings, FailingSender())
    assert not send_one(settings, FailingSender())
    assert client.get('/outbox', headers=AUTH).json()[0]['status'] == 'uncertain'


def test_new_starts_separate_case(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor())
    sms(settings, 'SM2', 'NEW')
    sms(settings, 'SM3', 'Another household needs help')
    process_one(settings, FakeExtractor())
    assert len(client.get('/incidents', headers=AUTH).json()) == 2


def test_delayed_question_not_used_to_interpret_earlier_reply(settings):
    sms(settings)
    sms(settings, 'SM2', '4')  # Arrived before our worker even asked for a house number.
    process_one(settings, FakeExtractor())
    send_one(settings)
    fake = FakeExtractor()
    process_one(settings, fake)
    assert 'assistant_followup' not in fake.history[0]


def test_successful_outbound_sms_submitted_once(settings, client):
    from types import SimpleNamespace
    class Sender:
        calls = []
        @property
        def messages(self):
            return self
        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(sid='SMOUT1')
    sms(settings)
    process_one(settings, FakeExtractor())
    settings.sms_dry_run = False
    sender = Sender()
    assert send_one(settings, sender)
    assert not send_one(settings, sender)
    assert len(sender.calls) == 1
    assert sender.calls[0]['to'] == '+15550000002'
    assert client.get('/outbox', headers=AUTH).json()[0]['provider_sid'] == 'SMOUT1'


def test_invalid_coordinates_rejected(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor())
    i = client.get('/incidents', headers=AUTH).json()[0]
    r = client.patch('/incidents/' + i['id'], headers=AUTH, json={
        'expected_version': 1, 'reason': 'test', 'latitude': 91, 'longitude': 0,
        'location_precision': 'approximate', 'location_source': 'test'})
    assert r.status_code == 422


def test_live_ack_does_not_claim_dispatch(settings):
    settings.sms_dry_run = False
    with TestClient(create_app(settings)) as client:
        data = {'MessageSid': 'SM1', 'From': '+15550000002', 'To': settings.twilio_phone_number, 'Body': 'Help'}
        signature = RequestValidator(settings.twilio_auth_token).compute_signature(settings.twilio_webhook_url, data)
        r = client.post('/webhooks/twilio/inbound', data=data, headers={'X-Twilio-Signature': signature})
        assert 'No rescue has been dispatched' in r.text
        r = client.post('/webhooks/twilio/inbound', data=data, headers={'X-Twilio-Signature': signature})
        assert '<Message>' not in r.text


def test_gemini_sdk_structured_output_adapter():
    import httpx
    from google import genai
    from google.genai import types
    from app.extractor import GeminiExtractor
    captured = []
    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'candidates': [{
            'content': {'role': 'model', 'parts': [{'text': json.dumps({
                'report_type': 'other', 'situations': [], 'missing_information': [], 'conflicts': []})}]},
            'finishReason': 'STOP'}]})
    http = httpx.Client(transport=httpx.MockTransport(respond))
    sdk = genai.Client(api_key='fake-test-key', http_options=types.HttpOptions(httpx_client=http))
    extractor = GeminiExtractor.__new__(GeminiExtractor)
    extractor.client, extractor.model = sdk, 'gemini-3.5-flash'
    result = extractor.extract([{'message_sid': 'SM1', 'body': 'hello'}])
    assert result.report_type == 'other'
    assert captured[0]['generationConfig']['responseMimeType'] == 'application/json'
    assert 'responseSchema' not in captured[0]['generationConfig']
    schema = captured[0]['generationConfig']['responseJsonSchema']
    assert schema['additionalProperties'] is False
    assert schema['$defs']['Address']['additionalProperties'] is False
    assert 'additional_properties' not in json.dumps(captured[0])
    assert 'systemInstruction' in captured[0]
    sdk.close()


def test_gemini_reports_auth_and_empty_list(client):
    assert client.get('/reports/gemini').status_code == 401
    assert client.get('/reports/gemini', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    response = client.get('/reports/gemini', headers=AUTH)
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers['cache-control'] == 'no-store'


def test_gemini_reports_preserve_per_message_snapshots(settings, client):
    sms(settings)
    process_one(settings, FakeExtractor())
    sms(settings, 'SM2', '123A Example Road')
    process_one(settings, FakeExtractor(Address(house_number='123A', street='Example Road')))
    response = client.get('/reports/gemini', headers=AUTH)
    assert response.status_code == 200
    rows = response.json()
    assert [r['message_sid'] for r in rows] == ['SM2', 'SM1']
    assert rows[0]['report']['situations'][0]['address']['house_number'] == '123A'
    assert rows[1]['report']['situations'][0]['address']['house_number'] is None
    assert rows[0]['extraction_id'] != rows[1]['extraction_id']
    assert rows[0]['conversation_id'] == rows[1]['conversation_id']
    assert rows[0]['model'] == settings.gemini_model
    assert rows[0]['generated_at'] is not None
    assert 'sender' not in rows[0] and 'body' not in rows[0]
    # Narrow by SID; return the same list shape even for one item.
    assert client.get('/reports/gemini?message_sid=SM1', headers=AUTH).json() == [rows[1]]
    assert client.get('/reports/gemini?message_sid=missing', headers=AUTH).json() == []


def test_gemini_reports_pending_failed_other_and_control(settings, client):
    class Other:
        def extract(self, history):
            return Extraction(report_type='other')
    sms(settings, 'SM1', 'hello')
    process_one(settings, Other())
    sms(settings, 'SM2', 'STOP')
    sms(settings, 'SM3', 'Help')
    sms(settings, 'SM4', 'Help elsewhere')
    with connect(settings) as db:
        db.execute("UPDATE messages SET status='failed',error='TimeoutError' WHERE sid='SM3'")
    rows = client.get('/reports/gemini', headers=AUTH).json()
    assert [r['message_sid'] for r in rows] == ['SM4', 'SM3']
    assert rows[0]['processing_status'] == 'pending' and rows[0]['report'] is None
    assert rows[1]['processing_status'] == 'failed' and rows[1]['error'] == 'TimeoutError'
    assert rows[1]['extraction_id'] is None
    all_rows = client.get('/reports/gemini?help_only=false', headers=AUTH).json()
    assert [r['message_sid'] for r in all_rows] == ['SM4', 'SM3', 'SM1']
    assert all_rows[-1]['report']['report_type'] == 'other'


def test_gemini_reports_pagination_and_conversation_filter(settings, client):
    sms(settings, 'SM1')
    sms(settings, 'SM2', sender='+15550000003')
    rows = client.get('/reports/gemini', headers=AUTH).json()
    cid = rows[1]['conversation_id']
    assert client.get('/reports/gemini', params={'conversation_id': cid}, headers=AUTH).json() == [rows[1]]
    assert client.get('/reports/gemini?limit=1&offset=1', headers=AUTH).json() == [rows[1]]
    assert client.get('/reports/gemini?offset=100', headers=AUTH).json() == []
    for query in ('limit=0', 'limit=501', 'offset=-1'):
        assert client.get('/reports/gemini?' + query, headers=AUTH).status_code == 422
    assert client.get('/reports/gemini', params={'conversation_id': "' OR 1=1 --"}, headers=AUTH).json() == []
