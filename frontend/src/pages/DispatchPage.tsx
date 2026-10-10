import { useMemo, useState } from 'react';
import { sortIncidents } from '../logic/sortIncidents';
import { evaluateTeams, suggestTeams } from '../logic/suggest';
import type { DemoScript } from '../logic/demo';
import { formatCheckInAge, missedCheckIns } from '../logic/safety';
import { boardSummary } from '../logic/summary';
import { activeAssignmentsForIncident, initialDispatchState } from '../logic/dispatch';
import { loadFakeData } from '../data/fakeData';
import { useDispatchStore } from '../state/DispatchStore';
import { useClock, useNow } from '../state/Clock';
import { TopBar } from '../components/TopBar';
import { DemoBar } from '../components/DemoBar';
import { IncidentMap } from '../components/IncidentMap';
import { IncidentList } from '../components/IncidentList';
import { IncidentCard } from '../components/IncidentCard';
import { IncidentDispatchPanel } from '../components/IncidentDispatchPanel';
import { TeamBoard } from '../components/TeamBoard';
import { EventLog } from '../components/EventLog';

const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Bangkok', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

export function DispatchPage({ demoScript }: { demoScript: DemoScript }) {
  const now = useNow();
  const clock = useClock();
  const store = useDispatchStore();
  const { incidents, health, teams, assignments, events, travelTimes, alerts } = store.data;
  const openAlerts = alerts.filter((a) => a.acknowledged_at === null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fresh fake data whose newest timestamp sits just before `at`.
  const freshData = (at: Date) => initialDispatchState(loadFakeData({ shiftTo: at }));

  const sorted = useMemo(() => sortIncidents(incidents, now), [incidents, now]);
  const selected = incidents.find((i) => i.id === selectedId);

  // Suggestions only; the dispatcher assigns through the confirm dialog.
  const evaluations = useMemo(
    () => (selected ? evaluateTeams(selected, teams, travelTimes, now) : []),
    [selected, teams, now, travelTimes],
  );
  const suggestions = useMemo(
    () => (selected ? suggestTeams(selected, teams, travelTimes, now) : []),
    [selected, teams, now, travelTimes],
  );
  const excluded = useMemo(
    () => new Map(evaluations.filter((e) => !e.eligible).map((e) => [e.team.id, e.reasons])),
    [evaluations],
  );
  // Highlight a "best" team only while the incident still needs one.
  const needsTeam = !!selected && activeAssignmentsForIncident(store.data, selected.id).length === 0;
  const missed = missedCheckIns(teams, now);
  const hasAlerts = missed.length > 0 || openAlerts.length > 0 || !!store.error;

  return (
    <div className={selected ? 'dispatch dispatch--detail' : 'dispatch'}>
      <TopBar summary={boardSummary(incidents, teams, now)} now={now} mode={clock.mode} source={store.source}>
        <DemoBar
          script={demoScript}
          data={store.data}
          demoLog={store.demoLog}
          demoDone={store.demoDone}
          now={now}
          onStartDemo={(simStart) => {
            store.reset(freshData(simStart));
            clock.enterDemo(simStart.getTime());
            setSelectedId(null);
          }}
          onReset={() => {
            if (!clock.clock) return;
            const simStart = new Date(clock.clock.simStart);
            clock.resetClock();
            store.reset(freshData(simStart));
            setSelectedId(null);
          }}
          onExit={() => {
            clock.exitDemo();
            store.reset(freshData(new Date()));
            setSelectedId(null);
          }}
        />
      </TopBar>

      <IncidentList incidents={sorted} selectedId={selectedId} onSelect={setSelectedId} now={now} />

      <main className="mapzone">
        <IncidentMap incidents={incidents} selectedId={selectedId} onSelect={setSelectedId} now={now} />
        {hasAlerts && (
          <div className="alerts" aria-label="Alerts">
            {missed.map(({ team, minutesSince }) => (
              <div key={team.id} className="alertrow alertrow--danger" role="alert">
                <span className="alertrow__kind">Check-in</span>
                <span className="alertrow__text">
                  {team.name} missed check-in · last {formatCheckInAge(minutesSince)}
                </span>
                <button type="button" className="btn btn--tiny" onClick={() => store.checkIn(team.id)}>
                  Log check-in
                </button>
              </div>
            ))}
            {openAlerts.map((a) => (
              <div key={a.id} className="alertrow alertrow--warn" role="alert">
                <span className="alertrow__kind">Route</span>
                <span className="alertrow__text">
                  <span className="mono">{timeFormat.format(new Date(a.created_at))}</span> {a.message}
                </span>
                <button type="button" className="btn btn--tiny" onClick={() => store.acknowledgeAlert(a.id)}>
                  Ack
                </button>
              </div>
            ))}
            {store.error && (
              <div className="alertrow alertrow--error" role="alert">
                <span className="alertrow__kind">Refused</span>
                <span className="alertrow__text">{store.error.join(' ')}</span>
                <button type="button" className="btn btn--tiny" onClick={store.clearError}>
                  Dismiss
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {selected && (
        <IncidentCard
          incident={selected}
          health={health.find((h) => h.incident_id === selected.id)}
          now={now}
          onClose={() => setSelectedId(null)}
          onConfirmHealth={() => store.confirmHealth(selected.id)}
        >
          <IncidentDispatchPanel
            state={store.data}
            incident={selected}
            now={now}
            suggestions={suggestions}
            onAssign={(teamId, backup) => store.assign(selected.id, teamId, backup)}
            onStatus={(to) => store.setIncidentStatus(selected.id, to)}
            onRecall={store.recall}
          />
        </IncidentCard>
      )}

      <div className="bottom">
        <TeamBoard
          teams={teams}
          assignments={assignments}
          now={now}
          bestTeamId={needsTeam ? (suggestions[0]?.team.id ?? null) : null}
          excluded={selected ? excluded : undefined}
          onRecall={store.recall}
          onStatus={store.setTeamStatus}
          onCheckIn={(teamId) => store.checkIn(teamId)}
        />
        <EventLog events={events} />
      </div>
    </div>
  );
}
