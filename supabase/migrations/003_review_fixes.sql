-- Review-driven schema fixes: run-scoped companies, mock/live source,
-- completed_with_errors, provider metadata, last_checked_at, ICP payload.

alter table public.companies
  add column if not exists discovery_run_id uuid references public.discovery_runs (id) on delete set null,
  add column if not exists source text not null default 'live'
    check (source in ('live', 'mock', 'manual')),
  add column if not exists last_checked_at timestamptz;

create index if not exists companies_discovery_run_id_idx
  on public.companies (discovery_run_id);
create index if not exists companies_source_idx
  on public.companies (source);
create index if not exists companies_last_checked_at_idx
  on public.companies (last_checked_at);

alter table public.discovery_runs
  drop constraint if exists discovery_runs_status_check;

alter table public.discovery_runs
  add constraint discovery_runs_status_check
  check (status in (
    'pending',
    'searching',
    'enriching',
    'scoring',
    'completed',
    'completed_with_errors',
    'failed'
  ));

alter table public.discovery_runs
  add column if not exists search_provider text,
  add column if not exists used_mock_fallback boolean not null default false,
  add column if not exists icp jsonb not null default '{}'::jsonb;

alter publication supabase_realtime add table public.signals;
