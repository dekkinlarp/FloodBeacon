# PLAN.md — Dispatch Layer

Status: **draft, waiting for review.** Revised 2026-10-03 after Session 1.

## 0. What exists today

- Repo: `~/development/flood-dispatch`. Not a git repo.
- `docs/dispatch-plan.md`: **does not exist** (`docs/` is empty).
- Person 3's app: **not found on this machine.** No app shell, Vite config, login or database client
  in this repo or nearby folders (`~/development`, `~/Documents`, `~/Desktop`, `~/Downloads`).
  If it lives elsewhere, this plan must be re-checked against it.
- Session 1 output (see `PROGRESS.md` for details):

```
flood-dispatch/
├── CLAUDE.md, PLAN.md, PROGRESS.md
├── package.json            # npm test = vitest run, npm run build = tsc (no Vite yet)
├── tsconfig.json           # strict
├── data/fake/              # incidents.json (20), health.json (7), teams.json (6)
├── src/types/              # enums, location, incident, health, team, assignment, event, index
├── src/logic/validateData.ts
├── db/schema.sql           # PostgreSQL + PostGIS, written, never run (was supabase/)
└── tests/logic/validateData.test.ts   # 12 tests, passing
```

Session 1 did **not** do everything the earlier plan listed for it: status transition rules, the
event builder, the data-access layer (`src/data/`) and fake assignments are still missing. They
are moved into Session 2 below.

## 1. Proposed folder structure

```
flood-dispatch/
├── data/fake/                  # stand-ins for teammates' data, shaped by src/types/
│   ├── incidents.json, health.json, teams.json        # exist
│   ├── assignments.json, events.json                  # to add
│   ├── flood-zones.geojson     # Person 1 stand-in (depth, rising)
│   └── access.json             # Person 2 stand-in (severity score, access type, routes)
├── src/
│   ├── types/                  # data contracts, single source of truth
│   ├── logic/                  # pure functions only: no React, no database, no I/O
│   ├── data/                   # data access: fake now, PostgreSQL later. Only place that
│   │                           # imports JSON or talks to the database API.
│   ├── components/             # thin UI pieces
│   └── pages/DispatchPage.tsx  # the one dispatch screen
├── db/schema.sql
└── tests/
    ├── logic/                  # one test file per src/logic/ file
    └── components/             # a few render tests where useful
```

Why: `src/logic/` holds every decision so it is testable without a browser (rule 5).
`src/data/` isolates where data comes from, so swapping fake → PostgreSQL touches one folder.
If Person 3's app shell appears, `DispatchPage.tsx` becomes one route in their app and our
folders stay as they are.

## 2. Sessions 1–7

> **The sessions list is still missing.** The prompt says "sessions 1–7 below" but nothing follows
> it, both last time and this time. The list below is **my proposal** based on the scope in
> CLAUDE.md. Replace it with your list if you have one.

### Session 1 — Data model and fake data ✅ done
Created the files shown in section 0.

### Session 2 — Status rules, event log, data layer (leftovers from Session 1)
- `src/logic/incidentStatus.ts`: allowed incident transitions (needs Q8)
- `src/logic/teamStatus.ts`: allowed team transitions (needs Q10)
- `src/logic/events.ts`: build an event record for every state change (rule 6)
- `src/data/repository.ts` (interface), `src/data/fakeRepository.ts`
- `data/fake/assignments.json`, `data/fake/events.json`
- `src/logic/validateData.ts`: add Assignment and Event validators
- `tests/logic/incidentStatus.test.ts`, `teamStatus.test.ts`, `events.test.ts`, `fakeRepository.test.ts`
- No new dependencies.

### Session 3 — Incident map
- Needs approval to install: `vite`, `react`, `react-dom`, `@vitejs/plugin-react`, `maplibre-gl`
  (plus their types). `build` becomes `tsc && vite build`.
- `vite.config.ts`, `index.html`, `src/main.tsx` (only if Person 3 has no app shell; Q1)
- `src/components/IncidentMap.tsx`: MapLibre map, Bangkok extent
- `src/components/IncidentMarker.tsx`: priority colour + need icon only (rule 7)
- `src/logic/mapStyle.ts`: severity → colour, need → icon
- `src/pages/DispatchPage.tsx`: map + empty side panel
- `tests/logic/mapStyle.test.ts`

### Session 4 — Incident card, health triage, AI fields, emergency reminders
- `src/components/IncidentCard.tsx`: full details, status controls
- `src/components/HealthTriage.tsx`: health details, card only (rule 7)
- `src/components/AiFieldBadge.tsx`: `verified_by_human` + original message (rule 8)
- `src/components/EmergencyReminder.tsx`: 1669 / 1784 (rule 9)
- `src/logic/emergencyReminder.ts`: when to show which number (needs Q11)
- `tests/logic/emergencyReminder.test.ts`, `tests/components/IncidentCard.test.tsx`
  (component tests need a DOM test library; ask first)

### Session 5 — Team cards, drag-and-drop assignment, team suggestions
- Needs approval to install `@dnd-kit/core`.
- `src/components/TeamCard.tsx`, `TeamList.tsx`, `AssignmentDnd.tsx`, `TeamSuggestions.tsx`
- `src/logic/assignment.ts`: validate assign/unassign, return status changes + events (needs Q9)
- `src/logic/suggestTeams.ts`: rank available teams (needs Q12 and vehicle → access mapping)
- `data/fake/access.json`
- `tests/logic/assignment.test.ts`, `suggestTeams.test.ts`

### Session 6 — Responder safety and field feedback
- `src/logic/responderSafety.ts`: warn when a team or route is in deep or rising water (needs Q13)
- `src/logic/fieldFeedback.ts`: reached / resolved / could not reach, from the field
- `src/components/SafetyAlert.tsx`, `FieldFeedbackForm.tsx`
- `data/fake/flood-zones.geojson`
- `tests/logic/responderSafety.test.ts`, `fieldFeedback.test.ts`

### Session 7 — Demo mode
- `src/logic/demoClock.ts`: fake "now" that can be stepped forward
- `src/data/demoScenario.ts`: scripted changes (new incidents, rising water)
- `src/components/DemoControls.tsx`
- `tests/logic/demoClock.test.ts`

Not in any session: the PostgreSQL connection (through a backend API, to be decided with
Person 3), live updates between devices, and
row-level security for `health`. See Q5.

Note: the earlier draft had 7 sessions starting with "foundations". Because Session 1 only
covered the data model, sessions are shifted and team cards + suggestions are merged into one
session to stay at 7. That makes Session 5 the largest; it may need splitting.

## 3. Questions and unclear points

**Repo and ownership**
1. Does Person 3 have an app shell repo? If yes, where? Should the dispatch screen be a route inside
   it or a separate app? Should I scaffold Vite here at all?
2. Is `~/development/flood-dispatch` the right location, or a shared monorepo? Should it be a git repo?
3. Where is the real sessions 1–7 list? Is there a `docs/dispatch-plan.md`?

**Data contracts**
4. Session 1 chose field names, extra enums (`Need`, `MedicalNeed`, `Vehicle`, …), text IDs
   (`INC-001`) and a separate `health.json`. Are these OK, or do teammates already have a schema?
5. Who owns the PostgreSQL schema, migrations and access rules for `health`: me or Person 3?
   Which backend serves the browser (API, live updates, login), and when is it built?
   (Decided 2026-10-04: PostgreSQL instead of Supabase.)
6. Is `events` append-only? Required fields (actor, entity, from, to, time)? Who is the "actor"
   before login exists?
7. Who sets `severity`: Person 2's score, the dispatcher, or both with override?

**Business rules**
8. Allowed incident transitions: can `could_not_reach` go back to `assigned`? Can `resolved` /
   `cancelled` be reopened? Can `new` skip `verified`?
9. Can one team hold more than one incident? Can one incident have more than one team?
10. When does a team become `returning` / `resting`? Automatic or manual?
11. What makes a case "critical medical" for 1669: severity `critical`, health priority `critical`,
    or both? (Session 1 assumed both, only in a test.) When exactly is 1784 shown?
12. Team suggestions: which factors in which order (access match, distance, load, equipment)?
    Does Person 2 provide travel time or only access type?
13. Responder safety: what depth / rising threshold is unsafe? Will Person 1 provide polygons,
    a raster or point values?
14. Which vehicle can serve which access type (e.g. can a kayak serve `boat_only`; can a boat
    team serve `walk_only`)?

**Users and UI**
15. Field feedback: responders on phones (mobile layout + login) or dispatchers entering it from radio?
16. UI language: Thai, English or both?
17. Does Person 3 have a UI kit or design rules to follow?

**Tooling**
18. TypeScript 7.0 and Vitest 5.0 were installed (latest). Do they match Person 3's versions?
19. Component tests need a DOM library (e.g. jsdom + Testing Library). Allowed, or logic tests only?

**Demo**
20. Should demo mode run fully offline on fake data, or against a PostgreSQL demo database?
    Does Person 4's demo script define the scenario, or do I?
