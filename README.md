# Lead Intelligence

Internal POC for discovering companies that may need outbound / appointment-setting support, then ranking them with evidence-backed intent scores.

## Architecture

```text
PRODUCT LAYER          DATA LAYER           INTELLIGENCE LAYER
Next.js dashboard  →   Supabase Postgres ←  FastAPI + LangGraph
filters / review       Auth-ready RLS       Firecrawl search/scrape
Realtime companies     (POC anon access)    OpenRouter structured extraction
                                            → signals → deterministic score → summary
```

`discovery_run_costs` exists in the schema for later spend tracking. V1 does not write it.

Realtime: the dashboard subscribes to `companies` and `signals`. Discovery progress is polled from `discovery_runs`.

## Repository

```text
lead-intelligence/
  apps/web/            Next.js dashboard
  apps/ai-service/     FastAPI research/AI pipeline
  supabase/            SQL migrations + seed
  docs/                Architecture notes
```

## Full-stack demo setup (ordered)

1. Create a Supabase project.
2. Run `supabase/migrations/001_initial_schema.sql`, then `supabase/migrations/002_contacts.sql`.
3. Optionally run `supabase/seed.sql` for a populated dashboard before the first live run.
4. Web app:

```bash
cd apps/web
cp .env.example .env.local
# set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_AI_SERVICE_URL
npm install
npm run dev
```

Without Supabase env vars, the dashboard still opens with **seed demo data**.

5. AI service:

```bash
cd apps/ai-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set OPENROUTER_API_KEY and FIRECRAWL_API_KEY for live search/enrichment
uvicorn app.main:app --reload --port 8000
```

6. Open `http://localhost:3000/dashboard`, then `/discover`.

### Seed-only vs live

- **Seed-only:** no Supabase, no AI service. Dashboard and seed company detail work. Discover will fail until the AI service is up.
- **Live:** Discover runs LangGraph (`POST /v1/discovery`): query → search → resolve → crawl → enrich → extract signals → score → summary. Results persist to Supabase and appear on the dashboard with scores and evidence.

If `FIRECRAWL_API_KEY` is missing **or** rejected (401/403), search falls back to a **mock fixture provider**. The Discover UI labels mock results so they are not mistaken for live web data.

Never commit `.env` files. If a secret was ever committed, rotate it.

### Smoke script

```bash
cd apps/ai-service
source .venv/bin/activate
PYTHONPATH=. python scripts/run_phase3_discovery.py
```

## Tests

```bash
cd apps/ai-service && source .venv/bin/activate && pytest
cd apps/web && npm test && npm run lint && npm run build
```

## V1 vs V2

### What V1 includes (and why)

V1 is a usable internal POC: discover companies from public intent queries (funding, sales hiring, expansion, public demand/discussion, optional keywords), enrich from crawled pages, extract evidence with an LLM, then **rank with a deterministic weighted score**. Scoring is rule-based so results are explainable in a sales review: hiring + funding → high; early-stage + sales hiring → medium-high; no growth signals → low. Seed data exists so the UI can be demoed without keys. Auth is intentionally open (anon RLS) for a time-boxed demo.

### What V2 would add

- Scheduled / continuous signal tracking
- Stronger scoring calibration and evaluation sets
- Higher-quality contact graphs and ICP filters
- Production auth and tighter RLS (service-role writes only)
- More discussion sources and spend tracking via `discovery_run_costs`
- Hosted demo + CI on a published GitHub remote

## Environment

**Web**

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_AI_SERVICE_URL`

**AI service**

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENROUTER_API_KEY` (preferred) or `LLM_API_KEY`
- `LLM_MODEL` (default `openrouter/free`)
- `FIRECRAWL_API_KEY`
- `SEARCH_PROVIDER=firecrawl` (or `mock`)
- `FRONTEND_URL`
# crework-assignment
