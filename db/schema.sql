-- Disease surveillance schema with row-level security (RLS).
-- Run in the Supabase SQL editor.

create table districts (
  id         serial primary key,
  name       text unique not null,
  dhis2_uid  text,
  population integer
);

create table diseases (
  id    serial primary key,
  name  text unique not null,
  icd10 text not null            -- ICD-10 code or range
);

-- One row per district, disease and week (aggregated counts only).
create table weekly_cases (
  id               bigserial primary key,
  district_id      integer not null references districts(id),
  disease_id       integer not null references diseases(id),
  week_start       date    not null,          -- Monday of the ISO week
  cases            integer not null check (cases >= 0),
  reports_received integer not null check (reports_received >= 0),
  reports_expected integer not null check (reports_expected > 0),
  source           text    not null default 'dhis2-demo',
  unique (district_id, disease_id, week_start)
);
create index on weekly_cases (week_start);
create index on weekly_cases (district_id, disease_id);

-- National-level public interest (e.g. Wikipedia pageviews per term).
create table web_interest (
  id         bigserial primary key,
  term       text    not null,
  week_start date    not null,
  views      integer not null check (views >= 0),
  source     text    not null default 'wikipedia-pageviews',
  unique (term, week_start)
);

-- Links each login to a role and, for officers, one district.
create table profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  full_name   text,
  role        text not null check (role in ('national_manager', 'district_officer')),
  district_id integer references districts(id),
  check (role = 'national_manager' or district_id is not null)
);

-- Record of alerts sent (supports alert-fatigue review and audit).
create table alert_log (
  id          bigserial primary key,
  district_id integer not null references districts(id),
  disease_id  integer not null references diseases(id),
  week_start  date    not null,
  cases       integer not null,
  threshold   numeric not null,
  sent_at     timestamptz not null default now(),
  unique (district_id, disease_id, week_start)
);

-- Helper functions. SECURITY DEFINER lets policies read profiles safely.
create or replace function public.current_app_role() returns text
language sql stable security definer set search_path = public as $$
  select role from profiles where id = auth.uid()
$$;

create or replace function public.current_district() returns integer
language sql stable security definer set search_path = public as $$
  select district_id from profiles where id = auth.uid()
$$;

-- Turn RLS on everywhere.
alter table districts    enable row level security;
alter table diseases     enable row level security;
alter table weekly_cases enable row level security;
alter table web_interest enable row level security;
alter table profiles     enable row level security;
alter table alert_log    enable row level security;

-- Read policies. There are no insert/update/delete policies for logged-in users,
-- so only the pipeline (service role key, server-side) can write data.
create policy "districts: managers all, officers own"
  on districts for select to authenticated
  using (current_app_role() = 'national_manager' or id = current_district());

create policy "diseases: all signed-in users"
  on diseases for select to authenticated using (true);

create policy "weekly_cases: managers all, officers own district"
  on weekly_cases for select to authenticated
  using (current_app_role() = 'national_manager' or district_id = current_district());

create policy "web_interest: all signed-in users"
  on web_interest for select to authenticated using (true);

create policy "profiles: own row only"
  on profiles for select to authenticated using (id = auth.uid());

create policy "alert_log: managers only"
  on alert_log for select to authenticated
  using (current_app_role() = 'national_manager');

-- Honest-data view: adds completeness (the denominator) and a small-number flag.
-- security_invoker makes the view obey the caller's RLS.
create or replace view weekly_cases_flagged with (security_invoker = true) as
select
  wc.*,
  round(100.0 * wc.reports_received / wc.reports_expected, 1) as completeness_pct,
  (wc.cases < 5) as low_count
from weekly_cases wc;
