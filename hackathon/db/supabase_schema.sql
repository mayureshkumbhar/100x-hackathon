-- Eval Co-pilot schema for Supabase (Postgres).
-- Paste into Supabase > SQL Editor > New query > Run. Safe to run more than once.

-- 1. A classmate's app that you are testing (public URL only, never secret keys)
CREATE TABLE IF NOT EXISTS public.app (
  id   BIGSERIAL PRIMARY KEY,
  url  TEXT NOT NULL UNIQUE,
  name TEXT
);

-- 2. The golden pairs: what the user types + the checks (plain English, separated by ;)
CREATE TABLE IF NOT EXISTS public.golden_pair (
  id         BIGSERIAL PRIMARY KEY,
  app_id     BIGINT NOT NULL REFERENCES public.app(id),
  user_input TEXT   NOT NULL,
  rules      TEXT   NOT NULL,
  UNIQUE (app_id, user_input)
);

-- 3. One row per "Run all cases" click. Runs are never overwritten.
CREATE TABLE IF NOT EXISTS public.run (
  id         BIGSERIAL PRIMARY KEY,
  app_id     BIGINT      NOT NULL REFERENCES public.app(id),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note       TEXT
);

-- 4. One row per case per run: the app's answer, pass/fail, and the verdict for each check.
--    checks looks like: [{"check": "...", "passed": true|false|null, "reason": "..."}]
CREATE TABLE IF NOT EXISTS public.result (
  id      BIGSERIAL PRIMARY KEY,
  run_id  BIGINT  NOT NULL REFERENCES public.run(id),
  pair_id BIGINT  NOT NULL REFERENCES public.golden_pair(id),
  answer  TEXT,
  passed  BOOLEAN NOT NULL,
  checks  JSONB   NOT NULL
);

-- Indexes for the lookups the app does most (foreign keys are not indexed automatically)
CREATE INDEX IF NOT EXISTS golden_pair_app_idx ON public.golden_pair (app_id);
CREATE INDEX IF NOT EXISTS run_app_idx         ON public.run (app_id);
CREATE INDEX IF NOT EXISTS result_run_idx      ON public.result (run_id);
CREATE INDEX IF NOT EXISTS result_pair_idx     ON public.result (pair_id);

-- Security: turn on row level security with no policies.
-- This blocks the public anon / authenticated API keys from reading or writing these tables.
-- Your app connects with the direct postgres connection string, which bypasses RLS, so it still works.
ALTER TABLE public.app         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.golden_pair ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.run         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.result      ENABLE ROW LEVEL SECURITY;

-- Optional: wipe everything and start over (uncomment, run once, then re-run the script above)
-- DROP TABLE IF EXISTS public.result, public.run, public.golden_pair, public.app CASCADE;
