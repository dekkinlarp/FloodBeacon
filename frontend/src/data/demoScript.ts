import derna from '../../data/scenarios/derna-2023.json';
import nepal from '../../data/scenarios/nepal-2026.json';
import { DEFAULT_SITE, type SiteId } from './sites';
import scriptJson from '../../data/fake/demo_script.json';
import type { DemoScript } from '../logic/demo';
import { validateDemoScript } from '../logic/demo';

/** Loads and checks data/fake/demo_script.json. */
export function loadDemoScript(siteId: SiteId = DEFAULT_SITE): DemoScript {
  const script = siteId === 'derna-2023' ? derna.script : siteId === 'nepal-2026' ? nepal.script : scriptJson;
  const errors = validateDemoScript(script);
  if (errors.length > 0) throw new Error(`Demo script is invalid:\n${errors.join('\n')}`);
  return script as DemoScript;
}
