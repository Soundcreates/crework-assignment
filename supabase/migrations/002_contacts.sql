-- Contacts extracted from public pages (POC bonus)

create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  name text not null,
  title text,
  source_url text,
  created_at timestamptz not null default now()
);

create index if not exists contacts_company_id_idx on public.contacts (company_id);

alter table public.contacts enable row level security;

create policy "anon read contacts"
  on public.contacts for select to anon, authenticated using (true);
