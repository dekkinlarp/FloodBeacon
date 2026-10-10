# PROGRESS.md

## Session 1 — Data model and fake data (2026-10-03)

### Done
- Project setup: `package.json` (`npm test` = Vitest, `npm run build` = `tsc` type-check),
  `tsconfig.json` (strict), `.gitignore`. Dev deps: `typescript`, `vitest` only.
- `src/types/`: `Incident`, `Health`, `Team`, `Assignment`, `Event`, `LatLon`, and enums
  (`enums.ts`). CLAUDE.md enums copied exactly; each enum is a `const` array + union type.
- `data/fake/incidents.json`: 20 incidents, 14 districts, all severities, needs and access types,
  Thai / English / Burmese reporters. Statuses only `new`, `verified`, `cancelled`, because no
  assignments exist yet.
- `data/fake/health.json`: 7 health records. Critical medical: INC-001 (dialysis), INC-002
  (bedridden, home oxygen).
- `data/fake/teams.json`: 6 teams. 2 trucks, 2 flat boats, 1 kayak, 1 walking team.
- `supabase/schema.sql`: enums, 5 tables, PostGIS `geography(Point, 4326)`, GiST indexes.
  **Not run.**
- `src/logic/validateData.ts` validates each record and cross-checks the collections.
  Covered by `tests/logic/validateData.test.ts` (12 tests).
- `npm test` passes and `npm run build` passes.

### Decisions made this session (please review)
- Added enums not in CLAUDE.md: `Need`, `MedicalNeed`, `MobilityLevel`, `IncidentSource`,
  `Vehicle`, `Skill`, `Language`, `AssignmentEndReason`, `EventEntityType`, `EventType`.
- `health.json` was not in the brief. Added it because the dialysis case needs a health record,
  and CLAUDE.md keeps health in its own table.
- "Critical medical case" = incident severity `critical` AND health priority `critical`.
  This is only used by the test so far (PLAN.md Q11 still open).
- IDs are text (`INC-001`, `TEAM-01`), not UUIDs.
- Phone numbers are deliberately invalid (`+660000000NN`) so the fake data can never reach a
  real person.
- Validation is hand-written. No zod, because rule 4 says no new dependencies.
- `build` is `tsc` only for now. It becomes `tsc && vite build` when the UI session adds Vite.

### Next
- Answers to the PLAN.md questions (especially Q4–Q11) before going further.
- Session 2 per PLAN.md: incident map. Needs Vite + React + MapLibre installed, which needs
  approval first.
- Validators for `Assignment` and `Event`, once those records exist.

### Known issues
- Not a git repo yet.
- `schema.sql` has no row-level security policies for `health`. Ownership is undecided.
- No assignments or events fake data yet.
- Team vehicle → access type mapping (e.g. kayak → `boat_only`) is not defined. It's needed
  for team suggestions.
- Installed versions: TypeScript 7.0 and Vitest 5.0 (latest at install). Check that they match
  Person 3's versions.

## Session 1 re-check (2026-10-03)
- The Session 1 brief was given again. Re-checked every point against the existing work instead
  of redoing it: 20 incidents in 14 real districts, all coordinates within lat 13.6–13.95 /
  lon 100.35–100.95, all severities and access types used, 2 critical medical cases (INC-001
  dialysis, INC-002 oxygen), 6 teams covering truck / flat boat / kayak / walking with all three
  skills and languages, PostGIS points in `schema.sql`, 12 validation tests.
- No code changes. `npm test` and `npm run build` pass.
- PLAN.md revised the same day: Session 1 leftovers (status rules, event builder, data layer,
  fake assignments/events) moved into a proposed Session 2. Real sessions list still missing.

## Session 2 — Incident map (2026-10-03)

Note: the session prompt for this session was the incident map. PLAN.md had proposed status
rules for Session 2, so PLAN.md's numbering is now out of date; status rules, the event log and
the data layer are still to do.

### Done
- Installed (approved): `react`, `react-dom` 19.3, `maplibre-gl` 6.12; dev: `vite` 8.3,
  `@vitejs/plugin-react` 6.1, `@types/react(-dom)` 19.3. Scripts: `dev`, `build`
  (`tsc && vite build`), `preview`, `test`.
- Basemap: **OpenFreeMap Positron** `https://tiles.openfreemap.org/styles/positron`. No API key.
  Style, tiles and fonts checked to load; attribution shown bottom-left.
- Pure logic + tests (31 tests total now):
  - `src/logic/severity.ts`: severity colours (critical red, high orange, medium yellow,
    low green, resolved grey), readable ink colour, severity rank.
  - `src/logic/sortIncidents.ts`: severity, then longest waiting (`created_at`), then id.
  - `src/logic/contactBadge.ts`: hours since `last_contact_at`; red when > 6 h.
  - `src/logic/mainNeed.ts`: first listed need = marker icon.
  - `src/logic/emergencyReminder.ts`: 1669 when health priority is critical; 1784 when
    the incident needs rescue (rule 9; shown on the card).
- `src/data/fakeData.ts`: loads and validates `data/fake/` before the UI uses it.
- UI: `src/pages/DispatchPage.tsx` (list | map, card over the map's right side),
  `IncidentMap.tsx` (MapLibre markers rendered via React portals), `IncidentList.tsx`,
  `IncidentCard.tsx` (original message, extracted fields, `verified_by_human`, health, access,
  status, contact badge), `NeedIcon.tsx` (hand-drawn SVG, no emoji), `src/styles.css`.
- Map markers show only severity colour, need icon and contact hours (rule 7). Health details
  appear only in the card. Nothing logs health data.
- Checked in headless Chrome against both `npm run dev` and `vite preview`: basemap renders,
  20 markers, sorted list, card opens on marker click, no console errors.

### Decisions made this session (please review)
- "Main need" = the first need in `needs`. Gemini output order then decides the icon; a fixed
  priority order (e.g. rescue > medical > …) may be better.
- Missing `last_contact_at` falls back to `created_at` (the report counts as a contact).
- "Time waiting" in the list = time since `created_at`.
- Only `resolved` is grey. `cancelled` incidents keep their severity colour and stay in the
  list/map; resolved/cancelled are not pushed to the bottom of the list.
- 1669 rule uses health priority `critical` only (Session 1 test used incident AND health).
  PLAN.md Q11 still open.
- MapLibre worker: bundled through Vite (`?worker&url` + `setWorkerUrl`, `worker.format: 'es'`).
  Without this the basemap fails to load in both dev and build.

### Next
- Status rules, event log builder and data layer (`src/data/repository.ts`) — rule 6 needs the
  event log before any status change UI.
- Answers to PLAN.md questions (Q8–Q11 especially).
- Re-number PLAN.md sessions once the real sessions list is known.

### Known issues
- Fake data is dated 2026-10-02, so every contact badge is red (45 h+) when viewed now.
  Demo mode (fake clock) would fix this.
- Bundle is ~1.3 MB (MapLibre); Vite warns about chunk size. Not a problem yet.
- The card covers the right part of the map; the selected marker is centred on the full map
  width, so it sits left of centre in the visible area.
- No component tests (no DOM test library installed; PLAN.md Q19).
- Narrow screens stack list over map, but the card then covers the whole map. Not tuned for phones.

## Session 3 — Assignment and status tracking (2026-10-03)

### Done
- `src/logic/dispatch.ts` (pure, 35 tests in `tests/logic/dispatch.test.ts`):
  - `INCIDENT_TRANSITIONS` exactly as briefed: new→verified→assigned→en_route→on_scene→resolved;
    en_route/on_scene→could_not_reach→verified; new→cancelled. `assigned` only via `assignTeam`.
  - `TEAM_TRANSITIONS` (manual): available↔resting, available/resting→off_duty,
    off_duty→available, returning→available, en_route→on_scene.
  - `canAssign(state, incident, team, now, { backup })` → `{ ok, reasons, safetyNotes }`.
  - `assignTeam`, `updateIncidentStatus`, `updateTeamStatus`, `recallTeam`, `describeEvent`.
  - Every change returns `{ ok, state, events }`; refused changes return `{ ok: false, reasons }`.
- Rules enforced and tested: one active primary per incident (backup only when explicit); a busy
  team can't be assigned until recalled (and back to available); invalid transitions rejected;
  vehicle must fit access type (blocking); inputs never mutated; event ids unique.
- Decisions from the user this session:
  - Team status linked: assign → team en_route; incident on_scene → teams on_scene;
    resolved/could_not_reach → assignments end, teams returning.
  - Recall: assignment ends ('recalled'), team returning; if no team left, incident → verified
    (recall-only transition, not available by hand).
  - Access fit blocks: truck→truck; flat_boat/kayak→boat_only+truck; on_foot→walk_only+truck.
  - Safety notes (non-blocking): no swimmer for boat_only, no first aid for medical, on duty
    > 12 h, check-in > 1 h ago or never, AI-extracted and not verified.
- Data model: `Team` + `equipment`, `on_duty_since`, `last_check_in_at`; `Assignment` + `role`
  (primary/backup); `recalled` added to assignment end reasons and event types. Schema, validator
  and `teams.json` updated. Schema adds partial unique indexes (one active primary per incident,
  one active assignment per team). TEAM-06 is now `off_duty` in fake data.
- UI: `src/state/DispatchStore.tsx` (React context + useReducer; Zustand not installed, not
  added). `TeamCardBar`, `IncidentDispatchPanel` (status buttons, active teams + recall, assign
  list with reasons, "Add backup" checkbox), `AssignDialog` (native `<dialog>`, team, incident,
  role, safety notes), `EventLog` (latest 50, newest first), error banner for refused actions.
- Checked in headless Chrome: assign → confirm → en route → backup → recall; truck blocked on a
  boat-only incident; second primary refused; event log correct; no console errors.

### Next
- Team suggestions, drag and drop, Supabase (out of scope this session).
- PLAN.md session list needs re-numbering to match the sessions actually run.

### Known issues
- Actor is the placeholder `'dispatcher'` until login exists (PLAN.md Q6).
- Event/assignment ids (`EVT-0001`, `ASG-0001`) are counted from in-memory state; they will
  clash once events come from Supabase. Let the database generate ids then.
- State is in memory only; a page reload resets all assignments and events.
- When the primary is recalled but a backup stays, the backup is not promoted to primary, so
  a new team can only be added as another backup.
- Fake team times are from 2 Oct, so every team shows fatigue and overdue check-in notes now.
- `last_check_in_at` is never updated (no check-in action yet — field feedback session).
- The incident card is long; the assign list shows reasons for every blocked team.

## Session 4 — Team suggestions and health triage (2026-10-03)

### Done
- `src/logic/suggest.ts`: `evaluateTeam`, `evaluateTeams`, `suggestTeams(incident, teams,
  travelTimes, now)` → top 3 `{ team, score, reasons, travelMinutes }`. Nothing assigns.
  - Excluded: not `available`; vehicle can't reach access type (reuses `vehicleCanServe`);
    evacuation with `carry_capacity < people_count`; on duty > `MAX_HOURS_ON_DUTY` (16 h).
  - Score: travel `TRAVEL_MAX_POINTS` (100) falling linearly to 0 at 240 min; +40 per matched
    need skill (`NEED_SKILLS`: medical/medication → first_aid, rescue → swimmer); +15 language
    match; −4/h beyond 8 h on duty. Ties: shorter travel, then id. Missing travel time = 0 points.
  - Travel weight was first 50 pts / 180 min; the browser check showed a first-aid team ~5 h away
    beating a team 21 min away for the dialysis case, so travel was reweighted (regression test).
- `src/logic/warnings.ts`: `isOverdueCritical` (critical, status new/verified/could_not_reach,
  created > 30 min ago). `sortIncidents(incidents, now)` now puts these first. List rows and map
  markers flash (static under `prefers-reduced-motion`) with "No team for over 30 min".
- Health triage (`HealthTriage.tsx`): priority, vulnerable counts, injuries, mobility, medical
  dependencies (`medical_needs`), supplies left, notes. "AI-extracted, not yet confirmed" +
  Confirm button until confirmed. `confirmHealth` in `dispatch.ts` sets `verified_by_human` and
  logs a `health`/`verified` event with no health values.
- Reminders now read "Call 1669" / "Call 1784" as a large red label at the top of the card.
- Suggestions in the incident card (`SuggestionList.tsx`, "Assign…" opens the confirm dialog);
  team bar highlights the best match and greys out teams that can't go, with the reasons.
- Data: `Health` + `vulnerable`, `injuries`, `supplies_left`, `ai_extracted` (types, schema,
  validator, `health.json`). New `TravelTime` type and `data/fake/travel-times.json` (120 rows,
  generated from straight-line distance × 1.4 at truck 20 / boat 10 / kayak 6 / foot 3 km/h + 5
  min; stand-in for Person 2). `DispatchState` now holds `health`.
- Fake timestamps are shifted at load in the app (`loadFakeData({ shiftTo: new Date() })`,
  `src/logic/shiftTimes.ts`) so the newest is 5 min ago and gaps are kept. Tests load unshifted.
- 100 tests pass; build passes. Checked in headless Chrome, no console errors.

### Decisions made this session
- User: shift fake times at load; health fields as counts + lists.
- Mine (please review): scoring weights and limits above; `NEED_SKILLS` mapping (rescue →
  swimmer is my assumption); "unassigned" for the 30-min warning = new / verified /
  could_not_reach, measured from `created_at`; suggestions are shown even when the incident
  isn't assignable yet (Assign stays disabled); eligible teams can have negative scores.

### Next
- Drag and drop, Supabase, mobile view (out of scope this session).
- Replace fake travel times with Person 2's routes once their shape is known.
- PLAN.md session numbering is still out of date.

### Known issues
- Fake travel times ignore water depth and roads; slow vehicles get very long times across the city.
- `suggestTeams` does not know about active assignments directly; it relies on team status
  (busy teams are en_route/on_scene, so they are excluded).
- The 30-minute timer counts from `created_at`, so a could_not_reach incident flashes at once.
- Confirm on health has no undo.

## Session 5 — Responder safety and field feedback (2026-10-03)

### Done
- `src/logic/safety.ts`: `SUGGEST_REST_HOURS` (12) and `BLOCK_ASSIGNMENT_HOURS` (16); `fatigue()`
  (ok / rest / block + bar fraction). `canAssign` now blocks above 16 h; suggestions use the same
  limit (`MAX_HOURS_ON_DUTY = BLOCK_ASSIGNMENT_HOURS`); the safety note uses the rest limit.
- Check-in timer: `CHECK_IN_INTERVAL_MINUTES` (60) for field teams only (en_route, on_scene,
  returning — user's choice). `checkInState`, `missedCheckIns`, `formatCheckInAge` (minutes, so
  a missed check-in never reads "1h"). `checkInTeam` logs a `checked_in` event. Status reports
  from the team view and feedback submission also count as check-ins.
- Team cards: fatigue bar (green / orange "suggest rest" / red "no new assignments"), red card +
  "Missed check-in", "log check-in" (dispatcher, radio) and "team view" link. Red banner over
  the map lists every missed check-in.
- `TeamView` page at `#/team/<id>` (hash routing in `src/App.tsx` + `src/logic/route.ts`; no
  router dependency). Phone-first: destination, AI flag + original message (rule 8), route
  summary (fake travel time; Person 2 placeholder), reported blocked routes, safety notes,
  required-equipment checklist (`requiredEquipment` / `equipmentCheck`), 1669/1784 reminders,
  big buttons: En route / On scene (direct), Could not reach… / Resolved… (open feedback form).
  No health details (rule 7).
- `FieldFeedback` type + `field_feedback` table; `src/logic/feedback.ts`: `OUTCOME_STATUS`
  (evacuated / supplied / referred_1669 / no_one_found → resolved; could_not_reach →
  could_not_reach — user's choice), `allowedOutcomes` (on scene: all; en route: could_not_reach
  only), `validateFeedbackInput`, `submitFeedback` (stores feedback, moves incident → ends
  assignment, team returning, check-in; 5 events). Photo stores the file name only.
- `src/logic/exportEvents.ts`: JSON and CSV (RFC 4180 quoting, formula cells neutralised with a
  leading apostrophe, UTF-8 BOM so Excel shows Thai). Export buttons in the event log header.
- `reportFromField` + `chain` helper in `dispatch.ts`; store actions now carry an actor
  (`dispatcher` or `team:<id>`).
- 133 tests pass; build passes. Checked in headless Chrome (desktop + 390 px phone): assign →
  missed check-in alert → team view → en route (alert clears) → on scene → feedback → resolved;
  export produced CSV and JSON blobs; no console errors. Fixed after the check: white-on-white
  "Check in now" button, alert covering the incident card, team-card buttons clipped.

### Decisions made this session (please review)
- Required-equipment lists (`ACCESS_EQUIPMENT`, `NEED_EQUIPMENT`) and item names are mine; they
  match the free-text names in `teams.json`.
- Water depth in cm (0–500); blocked routes max 500 chars; `could_not_reach` requires 0 people
  helped.
- Fake `teams.json` unchanged; with time-shifting, TEAM-03 shows a missed check-in as soon as
  it is sent out (last check-in ~1 h 50 min earlier). Useful for the demo.

### Next
- Demo mode / Supabase / drag and drop / real GPS (not in this session).
- Person 4: confirm the CSV columns suit the validation scripts.

### Known issues
- Team view and dispatch share one in-memory store, so they only stay in sync inside the same
  browser tab. Two devices need Supabase Realtime.
- Photo upload stores the file name only; the file itself is not kept.
- Feedback ids (`FB-0001`) are counted in memory, like events.
- No undo for feedback.

## Session 6 — Replayable demo with a simulated clock (2026-10-03)

### Done
- `src/logic/clock.ts` (8 tests): pure demo clock — `createClock`, `start`, `pause`,
  `setSpeed`, `reset`, `simNow`, `elapsedMinutes`, `formatElapsed`. `DEMO_SPEED` = 360
  (1 h = 10 s). Never reads `Date.now()`; callers pass real time.
- `src/state/Clock.tsx`: the one place the app reads the time. `useNow()` (ticks every 250 ms
  while the demo runs, else 30 s) and `clock.now()` return simulated time in demo mode. The
  store stamps every action with `getNow`, so events, check-ins and warnings use demo time.
  Remaining `Date.now()`/`new Date()` uses: clock plumbing, initial live data shift, export
  file names (real time on purpose).
- `data/fake/demo_script.json` + `src/data/demoScript.ts` + `src/logic/demo.ts`
  (`validateDemoScript`, `dueSteps`, `applyDemoStep`, `runDueSteps`). Story: T+0 loaded;
  T+1h SMS from a dialysis patient in Bang Kapi (INC-021, critical, boat_only, AI-extracted);
  T+1h25 dispatcher verifies; T+1h30 dispatcher assigns the top suggested boat team (resolves
  to Flat Boat 1 / TEAM-02); T+1h35 en route; T+2h bridge closed → route truck 25 min → boat
  30 min + alert; T+3h on scene; T+3h30 resolved with feedback (evacuated, 2 people).
  - Steps go through the normal dispatch functions, so every step writes events (actors
    `demo:sms-intake`, `demo:dispatcher`, `team:<id>`). Each step is stamped with its own
    scripted time, so a clock jump gives the same result.
  - Manual actions still work. A step the dispatcher already did is *skipped* with a reason
    (e.g. "INC-021 already has TEAM-02"), never an error. The runner runs inside the store
    reducer, on the latest state.
- New dispatch functions: `reportIncident` (incident + health + travel times; health event has
  no values), `changeRoute` (route plan, travel time, alert, event), `acknowledgeAlert`,
  `routeFor`, `describeLegs`, `initialDispatchState`. New types `RoutePlan`/`RouteLeg`
  (stand-in for Person 2's routes) and `DispatchAlert`. `DispatchState` now also holds
  `travelTimes`, `routePlans`, `alerts`.
- `src/logic/score.ts`: resolved count, average response (report → first on scene), people
  reached (feedback), teams resting. Shown in the demo bar.
- Demo bar: Start demo / Start-Pause-Resume / speed (1 h = 10 s, 1 h = 1 min, real time) /
  Reset demo / Exit demo, T+ clock, last step and next step, score. Route alerts show over the
  map with Acknowledge, and in the team view with the new legs.
- 163 tests (incl. the whole story end to end, a manual-takeover run, and a clock jump).
  Build passes. In headless Chrome the full story played at 1 h = 10 s with every step
  applied, score 1 resolved / 120 min / 2 people / 1 resting; Reset returned to T+0 with no
  events; a run with a manual verify + assign skipped S3/S4 and still finished. No console
  errors.
- Bugs found and fixed while checking: a successful manual action wiped the demo progress
  (steps would have replayed); the T+ label passed simulated time into a real-time function.

### Decisions made this session (please review)
- Added two steps not in the brief: dispatcher verifies the SMS (T+1h25) and the team reports
  en route (T+1h35). Without them the assignment and on-scene steps are not allowed.
- "Average response time" = report (`created_at`) → first `on_scene`.
- Starting, resetting or exiting the demo replaces all in-memory data (fresh fake data).

### Next
- Person 4: replace/extend `demo_script.json` with the real demo script.
- Supabase, drag and drop (still out of scope).

### Known issues
- Marking an AI-extracted incident "verified" changes its status but not `verified_by_human`,
  so the "not yet verified by a person" safety note stays. Should verifying set the flag?
- Demo state lives in the browser tab only; a reload ends the demo.
- Fake travel times for INC-021 use the same straight-line formula as before.

## Session 7 — Dispatch console restyle (2026-10-03)

User asked: "make it less messy and more in dispatch style". Visual/layout only; no rule changes.

### Done
- Dark control-room theme for the dispatch screen (tokens scoped to `.dispatch`; the team view
  keeps the light theme for phones outdoors). Monospace for ids, times and counts.
- Basemap switched from OpenFreeMap Positron to OpenFreeMap **Dark** (same provider, no key).
  Missing pattern images in that style are filled with a transparent pixel
  (`setMissingStyleImageResolver`) so the console stays clean.
- Layout: header strip | queue | map | detail column (only when an incident is selected, no
  longer floating over the map) | team board + event log along the bottom.
- `TopBar.tsx` (new): brand, live counters (open, critical, waiting, no team > 30 min, teams
  free) from new pure `src/logic/summary.ts` (`boardSummary`, 2 tests), clock, LIVE/DEMO.
  Demo controls + story + score move to their own amber strip under the header in demo mode.
- Queue: dense rows with a severity stripe, status pill and "No team" tag; overdue rows pulse.
- Detail panel: header with severity + status, CALL 1669/1784 callout, key facts grid,
  Dispatch (status actions, assigned teams, top-3 suggestions; full team list / backup behind a
  collapsed "All teams" / "Add a backup team"), Report (AI flag + original message), Health.
  Backup is now explicit by opening "Add a backup team" (checkbox removed).
- `TeamBoard.tsx` replaces `TeamCardBar.tsx`: a table (team · status & job · duty bar &
  check-in · actions); skills/equipment in the name tooltip; team status changes via a small
  "Set…" menu; "Best" tag only while the incident still needs a team; teams that can't go are
  dimmed with the first reason.
- Alerts (missed check-in, route, refused action) are compact rows over the top of the map.
- 165 tests pass; build passes. Checked in headless Chrome (idle, selected, dialog, demo at
  T+2h with route alert); no console errors or warnings.

### Known issues
- Narrow screens (< ~1200 px) were not tuned (mobile view still out of scope).

## Session 8 — 2.5D map (2026-10-04)

### Done
- Map opens tilted (pitch 50°, bearing −17°). A "2D / 3D" button under the zoom controls
  flattens or re-tilts it; it follows manual tilting too.
- 3D buildings from the basemap's own OpenMapTiles `building` layer (`render_height`,
  `render_min_height`, skipping `hide_3d`). They rise between zoom 13 and 14, sit under the
  label layers, and taller buildings are lighter so high-rises stand out on the dark map.
- No new dependencies. 165 tests pass, build passes; checked in headless Chrome (tilted city,
  street-level buildings, flat toggle), no console errors.

### Known issues
- Building coverage depends on OpenStreetMap; some districts have few mapped buildings.
- Markers stay upright (screen-aligned) when tilted; they do not sit "on" the 3D ground.

## Session 9 — Supabase → PostgreSQL (2026-10-04)

User decision, agreed with Person 3: use plain PostgreSQL + PostGIS instead of Supabase.

### Done
- `supabase/schema.sql` → `db/schema.sql` (content unchanged: it never used Supabase-only
  features). CLAUDE.md tech stack, README, PLAN.md (Q5 updated) and code comments reworded.
  Earlier PROGRESS entries keep their original wording as history.
- Status page updated: the database box, the swap steps (now include an API server) and a new
  open question about who builds it.
- No code behaviour changed; 165 tests pass, build passes.

### Next
- Decide with Person 3 who builds the API server between the browser and PostgreSQL (reads and
  writes, login, live updates between the console and team phones), and where it is hosted.
