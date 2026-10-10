import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { addressLabel, hasMapLocation, intakeRequest, normalizeIncidents,
  type IntakeIncident, type IntakeDetail, type IntakePatch } from '../data/intake';
import { IntakeMap } from '../components/IntakeMap';

const date = (value: number) => new Date(value * 1000).toLocaleString();
const words = (value: string) => value.replace(/_/g, ' ');

export function LiveDispatchPage() {
  const [key, setKey] = useState('');
  const [draft, setDraft] = useState('');
  const [incidents, setIncidents] = useState<IntakeIncident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [lastSync, setLastSync] = useState<number | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      setLoading(true);
      try {
        const rows = await intakeRequest<IntakeIncident[]>(key, '/incidents',
          { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
        if (controller.signal.aborted) return;
        setIncidents(normalizeIncidents(rows)); setLastSync(Date.now()); setError('');
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load reports.');
      } finally {
        if (!controller.signal.aborted && mounted.current) {
          setLoading(false); timer = setTimeout(load, 5000);
        }
      }
    };
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [key, refresh]);

  const disconnect = () => { setKey(''); setDraft(''); setIncidents([]); setSelectedId(null); setLastSync(null); setError(''); };
  const selected = incidents.find(i => i.id === selectedId);
  const onSelect = useCallback((id: string) => setSelectedId(id), []);
  const connect = (event: FormEvent) => { event.preventDefault(); setKey(draft.trim()); setDraft(''); };

  return <div className={`dispatch intake-dispatch ${selected ? 'dispatch--detail' : ''}`}>
    <header className="topbar intake-header">
      <div className="topbar__brand"><span className="topbar__logo" aria-hidden="true" /><span>
        <strong>FLOODBEACON</strong><small>Dispatch · live SMS reports</small>
      </span></div>
      <dl className="topbar__stats">
        <div className="stat"><dt>Open</dt><dd>{incidents.filter(i => i.response_status !== 'resolved').length}</dd></div>
        <div className="stat"><dt>Unreviewed</dt><dd>{incidents.filter(i => i.needs_review).length}</dd></div>
        <div className="stat"><dt>Unlocated</dt><dd>{incidents.filter(i => !hasMapLocation(i)).length}</dd></div>
      </dl>
      <div className="intake-header-actions">
        <span className="source">{!key ? 'Disconnected' : error ? 'Connection issue — feed may be stale' : lastSync ? 'Live SMS feed' : 'Connecting…'}</span>
        {key && <><button className="btn" onClick={() => setRefresh(v => v + 1)} disabled={loading}>Refresh</button>
          <button className="btn" onClick={disconnect}>Disconnect</button></>}
        <a className="btn" href="?demo=1">Synthetic demo</a>
      </div>
      {!key && <form className="intake-connect" onSubmit={connect}>
        <label htmlFor="operator-key">Operator API key</label>
        <input id="operator-key" type="password" autoComplete="off" required value={draft} onChange={e => setDraft(e.target.value)} />
        <button className="btn btn--primary" type="submit">Connect live feed</button>
        <small>Use OPERATOR_API_KEY from twillio/.env. Kept only in this tab’s memory.</small>
      </form>}
      {error && <p role="alert" className="text-danger">{error} Showing last successfully loaded reports, if any.</p>}
    </header>
    <nav className="queue" aria-label="Live incident feed">
      <h2 className="panel-title">Reports <span className="panel-title__count">{incidents.length} cases</span></h2>
      {incidents.length === 0 && <p className="empty">{!key ? 'Connect to view incoming help requests.' : loading && !lastSync ? 'Loading reports…' : error ? 'Feed unavailable.' : 'No extracted help requests yet. Send a test SMS and keep the Gemini worker running.'}</p>}
      <ol className="queue__list">{incidents.map(i => <li key={i.id}>
        <button type="button" className={`qrow ${i.id === selectedId ? 'qrow--selected' : ''}`} aria-current={i.id === selectedId} onClick={() => setSelectedId(i.id)}>
          <span className="qrow__line"><strong>SMS · {i.id.slice(0, 8)}</strong><span className={`pill pill--${i.response_status}`}>{words(i.response_status)}</span></span>
          <span className="intake-summary">{i.report.situations.map(s => s.summary).join(' ')}</span>
          <span className="muted">{i.report.situations.length === 1 ? addressLabel(i.report.situations[0]!.address) : `${i.report.situations.length} reported situations — review separately`}</span>
          <span className="qrow__line qrow__meta">{!hasMapLocation(i) && <span className="tag">Unlocated</span>}
            <span>{words(i.verification_status)}</span><time>{date(i.updated_at)}</time></span>
        </button>
      </li>)}</ol>
    </nav>
    <main className="mapzone"><IntakeMap incidents={incidents.filter(i => i.response_status !== 'resolved')} selectedId={selectedId} onSelect={onSelect} /></main>
    {selected && <LiveDetail key={`${key}:${selected.id}`} incident={selected} apiKey={key}
      onClose={() => setSelectedId(null)} onSaved={updated => {
        setIncidents(rows => normalizeIncidents([...rows, updated]));
        setRefresh(v => v + 1);
      }} />}
    <footer className="bottom intake-bottom">
      <strong>{incidents.filter(i => i.response_status !== 'resolved').length} open cases</strong>
      <span>{incidents.filter(i => !hasMapLocation(i)).length} awaiting coordinates</span>
      <span>Last sync: {lastSync ? new Date(lastSync).toLocaleTimeString() : '—'}</span>
      <span>Refreshes every 5 seconds. Follow-up texts update the same case.</span>
    </footer>
  </div>;
}

function LiveDetail({ incident, apiKey, onClose, onSaved }: {
  incident: IntakeIncident; apiKey: string; onClose: () => void; onSaved: (updated: IntakeIncident) => void;
}) {
  const [detail, setDetail] = useState<IntakeDetail | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [reason, setReason] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setDetail(null); setError('');
    intakeRequest<IntakeDetail>(apiKey, `/incidents/${encodeURIComponent(incident.id)}`,
      { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) })
      .then(d => { if (!controller.signal.aborted) setDetail(d); })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load source messages.'); });
    return () => controller.abort();
  }, [apiKey, incident.id, incident.version]);
  const update = async (change: Omit<IntakePatch, 'expected_version' | 'reason'>) => {
    if (!reason.trim()) { setError('Enter a reason for this operational update.'); return; }
    setSaving(true); setError('');
    try {
      const updated = await intakeRequest<IntakeIncident>(apiKey, `/incidents/${encodeURIComponent(incident.id)}`, { method: 'PATCH',
        signal: AbortSignal.timeout(12000), body: JSON.stringify({ ...change, expected_version: incident.version, reason: reason.trim() }) });
      setReason(''); onSaved(updated);
    } catch (e) { setError(e instanceof Error ? e.message : 'Update failed.'); }
    finally { setSaving(false); }
  };
  return <aside className="detail">
    <header className="detail__header"><div><h2>SMS report · {incident.id.slice(0, 8)}</h2><span>Updated {date(incident.updated_at)}</span></div>
      <button className="btn" onClick={onClose}>Close</button></header>
    <div className="detail__body">
      <p className="flag flag--warn">Gemini-extracted claims · {words(incident.verification_status)} · priority {incident.operational_priority}</p>
      {incident.report.situations.map((s, index) => <section className="section" key={index}>
        <h3>Situation {index + 1}</h3><p>{s.summary}</p>
        <dl className="facts"><div><dt>People reported</dt><dd>{s.people_count ?? 'Unknown'}</dd></div>
          <div><dt>Reporter</dt><dd>{words(s.reporter_relationship)}</dd></div>
          <div className="facts__wide"><dt>Address</dt><dd>{addressLabel(s.address)}</dd></div>
          <div><dt>House number</dt><dd>{s.address.house_number ?? 'Unknown'}</dd></div>
          <div><dt>Postal/ZIP code</dt><dd>{s.address.postal_code ?? 'Unknown'}</dd></div>
          <div className="facts__wide"><dt>Location detail</dt><dd>{s.address.location_detail ?? 'Unknown'}</dd></div>
          <div className="facts__wide"><dt>Reported hazards</dt><dd>{s.reported_hazards.map(words).join(', ') || 'Not reported'}</dd></div>
          <div className="facts__wide"><dt>Assistance needs</dt><dd>{s.assistance_needs.map(words).join(', ') || 'Not reported'}</dd></div></dl>
        {s.reported_resolution && <p className="flag">Reporter says they are safe/rescued — requires operator confirmation.</p>}
        <details><summary>Source evidence ({s.evidence.length})</summary>{s.evidence.map((e, n) => <blockquote className="quote" key={n}>{e.quote}<small>{e.field} · {e.message_sid}</small></blockquote>)}</details>
      </section>)}
      {incident.report.conflicts.length > 0 && <section className="section"><h3>Conflicting information</h3>{incident.report.conflicts.map((c, n) => <p key={n}>{c}</p>)}</section>}
      <section className="section"><h3>Operational review</h3><p>Changes are saved to the intake backend. No team dispatch or SMS is triggered.</p>
        <label>Reason<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} /></label>
        <div className="intake-controls">
          <button className="btn" disabled={saving} onClick={() => void update({ verification_status: 'responder_verified' })}>Mark verified</button>
          <button className="btn" disabled={saving} onClick={() => void update({ response_status: 'assessing' })}>Assessing</button>
          <button className="btn" disabled={saving} onClick={() => void update({ response_status: 'resolved' })}>Mark resolved</button>
        </div>{error && <p role="alert" className="text-danger">{error}</p>}
      </section>
      <section className="section"><h3>Original messages</h3>{!detail ? <p>Loading source messages…</p> : detail.messages.map(m => <blockquote className="quote" key={m.sid}>{m.body}<small>{date(m.received_at)} · {m.status}</small></blockquote>)}</section>
    </div>
  </aside>;
}
