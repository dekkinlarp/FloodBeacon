-- Dispatch layer schema for PostgreSQL + PostGIS. Mirrors src/types/ — change both together.
-- NOT applied anywhere yet. Review with Person 3 (schema owner, PLAN.md Q5) before running.

create extension if not exists postgis;

-- Enums (values exactly as in src/types/enums.ts)
create type incident_status as enum
  ('new', 'verified', 'assigned', 'en_route', 'on_scene', 'resolved', 'could_not_reach', 'cancelled');
create type team_status as enum
  ('available', 'en_route', 'on_scene', 'returning', 'resting', 'off_duty');
create type severity as enum ('critical', 'high', 'medium', 'low');
create type access_type as enum ('truck', 'boat_only', 'walk_only');
create type need as enum ('rescue', 'evacuation', 'medical', 'medication', 'food_water', 'power');
create type medical_need as enum ('dialysis', 'oxygen', 'insulin', 'pregnancy', 'injury', 'mobility');
create type mobility_level as enum ('independent', 'assisted', 'bedridden');
create type incident_source as enum ('sms', 'phone', 'field', 'dispatcher');
create type vehicle as enum ('truck', 'flat_boat', 'kayak', 'on_foot');
create type skill as enum ('first_aid', 'boat_operator', 'swimmer');
create type language as enum ('thai', 'english', 'burmese');
create type assignment_end_reason as enum
  ('resolved', 'reassigned', 'could_not_reach', 'cancelled', 'recalled');
create type assignment_role as enum ('primary', 'backup');
create type event_entity_type as enum ('incident', 'health', 'team', 'assignment', 'feedback');
create type event_type as enum
  ('created', 'updated', 'status_changed', 'verified', 'assigned', 'unassigned', 'recalled', 'checked_in');
create type feedback_outcome as enum
  ('evacuated', 'supplied', 'referred_1669', 'no_one_found', 'could_not_reach');

create table incidents (
  id                text primary key,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  status            incident_status not null default 'new',
  severity          severity not null,
  access_type       access_type not null,
  district          text not null,
  location          geography(Point, 4326) not null,
  address_note      text not null default '',
  needs             need[] not null check (cardinality(needs) > 0),
  people_count      integer not null check (people_count >= 1),
  reporter_language language not null,
  contact_phone     text,
  last_contact_at   timestamptz,
  source            incident_source not null,
  original_message  text,
  ai_extracted      boolean not null default false,
  verified_by_human boolean not null default false,
  check (updated_at >= created_at),
  check (not ai_extracted or original_message is not null),
  check (source <> 'sms' or original_message is not null)
);
create index incidents_location_idx on incidents using gist (location);
create index incidents_status_idx on incidents (status);

-- Sensitive: separate table so access can be restricted with row-level security.
-- Policies are not written yet (who may read health is an open question).
create table health (
  incident_id       text primary key references incidents (id) on delete cascade,
  priority          severity not null,
  medical_needs     medical_need[] not null default '{}',
  mobility          mobility_level not null,
  vulnerable        jsonb not null default '{"elderly":0,"children":0,"pregnant":0,"disabled":0}',
  injuries          text[] not null default '{}',
  supplies_left     text,
  notes             text not null default '',
  ai_extracted      boolean not null default false,
  verified_by_human boolean not null default false,
  updated_at        timestamptz not null default now()
);

create table teams (
  id               text primary key,
  name             text not null,
  status           team_status not null default 'available',
  vehicle          vehicle not null,
  skills           skill[] not null default '{}',
  languages        language[] not null check (cardinality(languages) > 0),
  members_count    integer not null check (members_count >= 1),
  carry_capacity   integer not null check (carry_capacity >= 0),
  equipment        text[] not null default '{}',
  base_location    geography(Point, 4326) not null,
  current_location geography(Point, 4326) not null,
  on_duty_since    timestamptz,
  last_check_in_at timestamptz
);
create index teams_current_location_idx on teams using gist (current_location);

create table assignments (
  id          text primary key,
  incident_id text not null references incidents (id),
  team_id     text not null references teams (id),
  role        assignment_role not null default 'primary',
  assigned_at timestamptz not null default now(),
  assigned_by text not null,
  ended_at    timestamptz,
  end_reason  assignment_end_reason,
  check ((ended_at is null) = (end_reason is null))
);
create index assignments_incident_idx on assignments (incident_id);
create index assignments_team_idx on assignments (team_id);
-- At most one active primary per incident, and one active assignment per team.
create unique index assignments_one_primary_idx on assignments (incident_id)
  where ended_at is null and role = 'primary';
create unique index assignments_one_active_per_team_idx on assignments (team_id)
  where ended_at is null;

create table field_feedback (
  id             text primary key,
  incident_id    text not null references incidents (id),
  team_id        text not null references teams (id),
  submitted_at   timestamptz not null default now(),
  submitted_by   text not null,
  water_depth_cm numeric check (water_depth_cm >= 0),
  route_worked   boolean not null,
  blocked_routes text not null default '',
  people_helped  integer not null check (people_helped >= 0),
  outcome        feedback_outcome not null,
  photo_ref      text
);
create index field_feedback_incident_idx on field_feedback (incident_id);

-- Estimated travel minutes per team and incident (stand-in for Person 2's routes).
create table travel_times (
  team_id     text not null references teams (id),
  incident_id text not null references incidents (id) on delete cascade,
  minutes     numeric not null check (minutes >= 0),
  primary key (team_id, incident_id)
);

-- Explicit route when it differs from "direct by the team's vehicle" (e.g. bridge closed).
create table route_plans (
  incident_id text not null references incidents (id) on delete cascade,
  team_id     text not null references teams (id),
  legs        jsonb not null,            -- [{ "mode": "truck" | "boat" | "walk", "minutes": n }]
  reason      text,
  updated_at  timestamptz not null default now(),
  primary key (incident_id, team_id)
);

-- Alerts for the dispatcher. Messages never hold health details.
create table alerts (
  id              text primary key,
  created_at      timestamptz not null default now(),
  message         text not null,
  incident_id     text references incidents (id) on delete cascade,
  team_id         text references teams (id),
  acknowledged_at timestamptz
);

-- Append-only log. Values are statuses/ids only, never health details.
create table events (
  id          text primary key,
  occurred_at timestamptz not null default now(),
  actor       text not null,
  entity_type event_entity_type not null,
  entity_id   text not null,
  event_type  event_type not null,
  from_value  text,
  to_value    text,
  note        text
);
create index events_entity_idx on events (entity_type, entity_id, occurred_at);
