import { SiteProvider, useSite } from './state/Site';
import { DEFAULT_SITE, type SiteId } from './data/sites';
import { useEffect, useState } from 'react';
import { loadFakeData } from './data/fakeData';
import { loadDemoScript } from './data/demoScript';
import { initialDispatchState } from './logic/dispatch';
import { parseRoute } from './logic/route';
import { ClockProvider, useClock } from './state/Clock';
import { DispatchStoreProvider, useDispatchStore } from './state/DispatchStore';
import { DispatchPage } from './pages/DispatchPage';
import { TeamView } from './pages/TeamView';


/** Fake data with its timestamps shifted to end just before `at` (see loadFakeData). */
export function freshState(at: Date, siteId: SiteId = DEFAULT_SITE) {
  return initialDispatchState(loadFakeData({ shiftTo: at, siteId }));
}

function useHash(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}

/** Static demo: dispatch state stays in this browser tab. */
export function App() {
  return <SiteProvider><SiteApp /></SiteProvider>;
}

function SiteApp() {
  const { siteId } = useSite();
  // Switching sites resets the clock, state, selections, and script progress together.
  return <ClockProvider key={siteId}><Shell /></ClockProvider>;
}

function Shell() {
  const clock = useClock();
  const { siteId } = useSite();
  const [initial] = useState(() => freshState(new Date(), siteId));
  return (
    <DispatchStoreProvider initial={initial} getNow={clock.now}>
      <DemoRunner />
      <Screens />
    </DispatchStoreProvider>
  );
}

function Screens() {
  const { siteId } = useSite();
  const demoScript = loadDemoScript(siteId);
  const route = parseRoute(useHash());
  return route.page === 'team' ? <TeamView teamId={route.teamId} /> : <DispatchPage demoScript={demoScript} />;
}

/** While the demo clock runs, applies scripted steps as their time comes. */
function DemoRunner() {
  const { siteId } = useSite();
  const demoScript = loadDemoScript(siteId);
  const { clock, now } = useClock();
  const { demoTick } = useDispatchStore();
  useEffect(() => {
    if (!clock) return;
    const simStart = clock.simStart;
    demoTick(demoScript, simStart, now().getTime());
    if (!clock.running) return;
    const id = setInterval(() => demoTick(demoScript, simStart, now().getTime()), 250);
    return () => clearInterval(id);
  }, [clock, now, demoTick, siteId]);
  return null;
}
