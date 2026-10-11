> The default frontend is a static demo. Dispatch records are synthetic, actions run in
> browser memory, and refreshing resets changes. Historical satellite imagery is bundled
> locally. No operator key, Twilio, Python API, or PostgreSQL is required.
> See [Cloudflare deployment](DEPLOYMENT.md). [INTAKE.md](INTAKE.md) describes the previous backend integration.

# FloodBeacon — Ahr Valley, Derna, and Nepal flood response (dispatch layer)

A web app for a community organisation responding to floods in Ahr Valley, Derna, and Nepal (three satellite study areas).
This repository is the **dispatch layer**: dispatchers see incidents (people needing help) and
response teams on a map, assign teams, track each incident until it is resolved, and keep
responders safe.

It does **not** forecast floods and does **not** diagnose medical conditions. **The system
suggests; the dispatcher decides.** Nothing is assigned automatically.

> Dispatch data in `data/fake/` and `data/scenarios/` is invented. Contact identifiers
> start with `DEMO-` and are not phone numbers.

## Quick start

```bash
pnpm install --frozen-lockfile
pnpm run dev      # http://localhost:5173
pnpm test        # Vitest
pnpm run build    # type-check + production build
```

- **Dispatch console:** `http://localhost:5173/`
- **Team view (phone):** `http://localhost:5173/#/team/TEAM-02`
- **Demo:** click **▶ Scripted demo**, then **Start**. The scripted story (`data/fake/demo_script.json`)
  plays at 1 hour = 10 seconds: a dialysis patient's SMS arrives in the selected study area, a boat team is
  suggested and assigned, a bridge closes and the route changes, and the case is resolved with
  field feedback. You can still act manually during the demo.

## Site selection

Ahr Valley is selected on first load. The map selector switches between Ahr Valley,
Derna, and Syabrubesi, Nepal. Switching resets the incidents, teams, assignments, event
log, and scripted exercise for that site. All rescue locations and travel times are
invented exercises within the imagery study bounds, not historical rescue records.
The header and event times use UTC.

The **Scripted demo** button loads the selected site's exercise, initially paused.
**Start** runs its incoming-report, assignment, route-change, and field-feedback steps
on a simulated clock. Manual dispatch actions also work without starting the script.

## Severity and priority criteria

### Severity levels (critical, high, medium, low)

**Severity is an input to this app, not something it calculates.** In the full system it comes
from Person 2's severity score (not built yet), with the dispatcher able to review it. This repo
only displays it, sorts by it and applies the rules below.

The fake incidents in `data/fake/incidents.json` were labelled with the guide below. It is a
**guide for the fake data, not a rule in code**, until the real scoring exists:

| Level | Marker colour | Typical situation in the fake data | Examples |
|---|---|---|---|
| **Critical** | red | Life at risk now: life-sustaining treatment interrupted (dialysis, home oxygen), a bedridden person in rising water, or people trapped and needing rescue | INC-001 dialysis missed, boat only · INC-002 bedridden on oxygen, power out · INC-009 rescue, water rising fast |
| **High** | orange | Serious risk within hours: rescue or evacuation, large groups, medically vulnerable people (insulin, late pregnancy, bedridden) | INC-003 5 people on a roof · INC-011 8 months pregnant · INC-015 12 people to evacuate |
| **Medium** | yellow | Needs help today but not life-threatening right now: supplies, medication running out, minor injury, evacuation of mobile people | INC-005 food and water · INC-012 out of heart medication · INC-018 cut on the leg |
| **Low** | green | Comfort and supplies, no medical or rescue need | INC-008 food and water · INC-013 power out |
| Resolved | grey | Any severity once resolved | — |

### Health priority

Each incident may have a health record with its own `priority` (same four levels). It is shown
**only in the incident detail panel**, never on the map, and never written to logs or events.
AI-extracted health data shows *"AI-extracted, not yet confirmed"* until a dispatcher clicks
**Confirm**.

### Rules the app enforces

These are fixed in code (`src/logic/`) and covered by tests.

**Warnings and alerts**

| What | Rule | Constant |
|---|---|---|
| Medical escalation label | Health priority is `critical` | `src/logic/emergencyReminder.ts` |
| Rescue escalation label | The incident needs `rescue` | `src/logic/emergencyReminder.ts` |
| Critical incident flashes and moves to the top | Critical, no team (`new`, `verified` or `could_not_reach`), reported **more than 30 min** ago | `CRITICAL_UNASSIGNED_MINUTES = 30` |
| Contact badge turns red | Last contact **more than 6 h** ago | `CONTACT_OVERDUE_HOURS = 6` |
| Missed check-in (red row and alert) | A team in the field (`en_route`, `on_scene`, `returning`) has not checked in for **more than 60 min** | `CHECK_IN_INTERVAL_MINUTES = 60` |

**Team fatigue** (from hours on duty)

| Level | Hours on duty | Effect |
|---|---|---|
| OK (green bar) | under 12 h | none |
| Suggest rest (orange) | 12 h to 16 h | safety note when assigning |
| Blocked (red) | more than 16 h | cannot be assigned; never suggested |

Constants: `SUGGEST_REST_HOURS = 12`, `BLOCK_ASSIGNMENT_HOURS = 16`.

**Who can go where** (blocking)

| Vehicle | Can serve access types |
|---|---|
| Truck | truck |
| Flat boat, kayak | boat only, truck |
| On foot | walk only, truck |

A team is also blocked if it is not `available`, already has an assignment (recall it first),
or, for evacuations, cannot carry everyone (`carry_capacity < people_count`). One primary team
per incident; a second team only through **Add a backup team**.

**Team suggestions** (`src/logic/suggest.ts`, top 3, never automatic)

| Factor | Points |
|---|---|
| Travel time | up to +100, falling to 0 at 240 min |
| Each matched skill (medical or medication → first aid; rescue → swimmer) | +40 |
| Speaks the reporter's language | +15 |
| Fatigue | −4 per hour beyond 8 h on duty |

**Incident status flow**

```
new → verified → assigned → en_route → on_scene → resolved
                             en_route / on_scene → could_not_reach → verified
new → cancelled
```

Every change writes an event to the log, which can be exported as JSON or CSV.

## Project structure

```
src/types/       data contracts (incidents, health, teams, assignments, events, feedback, routes)
src/logic/       all rules as pure functions, with tests in tests/logic/
src/data/        loads and validates synthetic data/fake/
src/state/       app clock (live or demo) and the in-memory store
src/components/  UI pieces (queue, map, detail panel, team board, event log, dialogs)
src/pages/       DispatchPage (console) and TeamView (phone)
data/fake/       stand-in data for teammates' parts, and the demo script
db/              schema.sql for PostgreSQL + PostGIS (not applied yet)
```

Tech: React, TypeScript, Vite, MapLibre GL JS (OpenFreeMap basemap, no API key), Vitest.

## Status

The static demo combines synthetic Ahr Valley, Derna, and Nepal dispatch/team interactions with historical
Ahr, Derna, and Nepal imagery. Select a study area on the map to review dated images,
manual bridge findings, and agency flood evidence. Rescue records are fictional;
historical imagery does not establish present route safety.

The street basemap is fetched from OpenFreeMap, so an internet connection is required.
Backend integration files remain available for future work but are not used by the demo.
