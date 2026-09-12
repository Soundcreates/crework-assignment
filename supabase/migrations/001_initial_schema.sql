-- Lead Intelligence Platform — initial schema

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- companies
-- ---------------------------------------------------------------------------
create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  normalized_name text not null,
  website text,
  normalized_domain text unique,
  description text,
  industry text,
  estimated_employee_range text,
  estimated_stage text,
  business_model text,
  headquarters text,
  intent_score integer not null default 0 check (intent_score >= 0 and intent_score <= 100),
  intent_level text not null default 'LOW'
    check (intent_level in ('HIGH', 'MEDIUM HIGH', 'MEDIUM', 'LOW')),
  ai_summary text,
  review_status text not null default 'new'
    check (review_status in ('new', 'reviewing', 'qualified', 'not_relevant', 'contacted')),
  first_discovered_at timestamptz not null default now(),
  last_updated_at timestamptz not null default now()
);

create index if not exists companies_intent_score_idx on public.companies (intent_score desc);
create index if not exists companies_industry_idx on public.companies (industry);
create index if not exists companies_intent_level_idx on public.companies (intent_level);
create index if not exists companies_review_status_idx on public.companies (review_status);
create index if not exists companies_normalized_name_idx on public.companies (normalized_name);

-- ---------------------------------------------------------------------------
-- signals
-- ---------------------------------------------------------------------------
create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  signal_type text not null
    check (signal_type in ('funding', 'sales_hiring', 'expansion', 'public_demand', 'other_growth')),
  strength numeric(4, 3) not null check (strength >= 0 and strength <= 1),
  title text,
  explanation text not null,
  evidence text not null,
  source_url text not null,
  source_domain text,
  occurred_at timestamptz,
  detected_at timestamptz not null default now()
);

create index if not exists signals_company_id_idx on public.signals (company_id);
create index if not exists signals_signal_type_idx on public.signals (signal_type);
create index if not exists signals_detected_at_idx on public.signals (detected_at desc);

-- ---------------------------------------------------------------------------
-- discovery_runs
-- ---------------------------------------------------------------------------
create table if not exists public.discovery_runs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'pending'
    check (status in ('pending', 'searching', 'enriching', 'scoring', 'completed', 'failed')),
  industries text[] default '{}',
  country text,
  max_companies integer default 25,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  queries_generated integer not null default 0,
  search_results_found integer not null default 0,
  companies_discovered integer not null default 0,
  companies_enriched integer not null default 0,
  companies_failed integer not null default 0,
  error text
);

create index if not exists discovery_runs_status_idx on public.discovery_runs (status);
create index if not exists discovery_runs_started_at_idx on public.discovery_runs (started_at desc);

-- ---------------------------------------------------------------------------
-- Optional cost tracking per run
-- ---------------------------------------------------------------------------
create table if not exists public.discovery_run_costs (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.discovery_runs (id) on delete cascade,
  llm_calls integer not null default 0,
  llm_tokens integer not null default 0,
  search_requests integer not null default 0,
  crawl_requests integer not null default 0,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_last_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.last_updated_at = now();
  return new;
end;
$$;

drop trigger if exists companies_set_last_updated_at on public.companies;
create trigger companies_set_last_updated_at
before update on public.companies
for each row execute function public.set_last_updated_at();

-- ---------------------------------------------------------------------------
-- Realtime
-- ---------------------------------------------------------------------------
alter publication supabase_realtime add table public.discovery_runs;
alter publication supabase_realtime add table public.companies;

-- ---------------------------------------------------------------------------
-- RLS (open for POC/demo anon access; production must add auth and tighten policies).
-- Anon can currently read companies/signals/runs and update company rows (used for review_status).
-- ---------------------------------------------------------------------------
alter table public.companies enable row level security;
alter table public.signals enable row level security;
alter table public.discovery_runs enable row level security;
alter table public.discovery_run_costs enable row level security;

create policy "anon read companies"
  on public.companies for select to anon, authenticated using (true);

create policy "anon update review status"
  on public.companies for update to anon, authenticated
  using (true)
  with check (true);

create policy "anon read signals"
  on public.signals for select to anon, authenticated using (true);

create policy "anon read discovery_runs"
  on public.discovery_runs for select to anon, authenticated using (true);

create policy "anon insert discovery_runs"
  on public.discovery_runs for insert to anon, authenticated
  with check (true);

create policy "anon read costs"
  on public.discovery_run_costs for select to anon, authenticated using (true);
