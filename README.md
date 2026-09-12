# Lead Intelligence Platform

Discover companies from public buying-intent signals, enrich profiles, extract evidence, and rank outbound likelihood.

Default LLM is **`openai/gpt-4o-mini` via OpenRouter** (structured outputs + `provider.require_parameters`). `openrouter/free` is last-resort fallback only — it rate-limits at 20 req/min and often cannot return JSON.

## Local setup

1. Copy env files (never commit real secrets):

   ```bash
   cp apps/ai-service/.env.example apps/ai-service/.env
   cp apps/web/.env.example apps/web/.env.local
   ```

2. Apply schema to the linked Supabase project:

   ```bash
   supabase db push
   ```

   Migrations live in `supabase/migrations/` (`001` schema, `002` contacts, `003` run-scoped companies / mock source / `completed_with_errors`).

3. Start the AI service (reload is **off** unless `UVICORN_RELOAD=1`):

   ```bash
   cd apps/ai-service
   python -m pip install -r requirements.txt
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. Start the web app:

   ```bash
   cd apps/web
   npm ci
   npm run dev
   ```

5. Open `http://localhost:3000/dashboard` and run Discover.

## Technical walkthrough

Code-level map of the discovery graph, LLM client, scoring, and UI: [TECHNICAL.md](TECHNICAL.md).

```bash
cd apps/ai-service && python -m pytest -q
python scripts/review_committee.py

cd apps/web && npm test && npm run lint
```

Run pytest from `apps/ai-service` or the repo root with `pytest apps/ai-service/tests` — `Database(client=None)` is offline and never opens a live Supabase client.

## V1 vs V2

**V1 (this repo)**

- Keyword + industry discovery (Firecrawl search, mock fallback)
- LangGraph pipeline: query → search → rank → resolve → dedupe → enrich/score
- Batched signal extraction, rate-limit backoff, shared RPM limiter
- ICP filters on discovery (industry / stage / headcount / geography)
- Contacts extraction once `002_contacts.sql` is applied
- Dashboard with scores, filters, enrich actions, mock badges, pagination
- GitHub Actions weekday cron for discovery + stale recheck (needs `AI_SERVICE_URL`)
- In-process stale-run reaper (marks stranded BackgroundTasks runs failed)

**V2 (not built)**

- Durable queue/worker (Redis, Celery, or pgmq) instead of FastAPI `BackgroundTasks`
- Auth, per-tenant ICP profiles, CRM write-back
- Deeper monitoring (signal decay jobs, alerting, cost dashboards)
- Human-in-the-loop review queue and suppression lists

## Deploy notes

- **Web:** Vercel deployed from `apps/web` at [https://lead-intelligence-web-nine.vercel.app](https://lead-intelligence-web-nine.vercel.app) (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_AI_SERVICE_URL`).
- **API:** Render deployed in Hackathons workspace at [https://lead-intelligence-ai.onrender.com](https://lead-intelligence-ai.onrender.com) using `apps/ai-service/Dockerfile` and `render.yaml`. `FRONTEND_URL` configured for Vercel CORS.
- Production deploys use `UVICORN_RELOAD=0` to ensure background discovery pipelines are uninterrupted.

## Live Deployments & Demo

- **Web Application (Vercel):** [https://lead-intelligence-web-nine.vercel.app](https://lead-intelligence-web-nine.vercel.app)
- **AI Service Backend (Render):** [https://lead-intelligence-ai.onrender.com](https://lead-intelligence-ai.onrender.com)
- **Backend Health Check:** [https://lead-intelligence-ai.onrender.com/health](https://lead-intelligence-ai.onrender.com/health)

## Submission checklist (manual)

- [x] Commit and push to GitHub
- [x] `supabase db push` on the demo project (001, 002, 003 applied)
- [x] Deploy web + API to Render & Vercel
- [ ] Record a 5–10 min Loom **after** a discovery run that produces non-zero scores on real companies (not publisher listicles)
