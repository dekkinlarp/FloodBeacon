import scriptJson from '../../data/fake/demo_script.json';
import type { DemoScript } from '../logic/demo';
import { validateDemoScript } from '../logic/demo';

/** Loads and checks data/fake/demo_script.json. */
export function loadDemoScript(): DemoScript {
  const errors = validateDemoScript(scriptJson);
  if (errors.length > 0) throw new Error(`Demo script is invalid:\n${errors.join('\n')}`);
  return scriptJson as DemoScript;
}
