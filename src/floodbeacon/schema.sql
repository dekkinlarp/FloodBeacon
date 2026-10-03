CREATE TABLE IF NOT EXISTS cases (
    id text PRIMARY KEY,
    name text NOT NULL,
    bbox jsonb NOT NULL,
    description text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    case_id text NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    id text NOT NULL,
    generated_at timestamptz NOT NULL,
    metadata jsonb NOT NULL,
    PRIMARY KEY (case_id, id)
);
CREATE INDEX IF NOT EXISTS runs_latest ON runs (case_id, generated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS layers (
    case_id text NOT NULL,
    run_id text NOT NULL,
    name text NOT NULL,
    data jsonb NOT NULL,
    PRIMARY KEY (case_id, run_id, name),
    FOREIGN KEY (case_id, run_id) REFERENCES runs(case_id, id) ON DELETE CASCADE,
    CHECK (data->>'type' = 'FeatureCollection' AND jsonb_typeof(data->'features') = 'array')
);

CREATE TABLE IF NOT EXISTS observations (
    case_id text NOT NULL,
    run_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    data jsonb NOT NULL,
    PRIMARY KEY (case_id, run_id, ordinal),
    FOREIGN KEY (case_id, run_id) REFERENCES runs(case_id, id) ON DELETE CASCADE
);
