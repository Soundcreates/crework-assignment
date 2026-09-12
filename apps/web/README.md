# Web dashboard

Next.js UI for Lead Intelligence.

## Setup

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000/dashboard](http://localhost:3000/dashboard).

Required env:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_AI_SERVICE_URL` (default `http://localhost:8000`)

Without Supabase vars, the app shows seed companies. Discover still needs the FastAPI service.

## Known limitations (V1)

- Anon RLS is demo-only; do not use this as a production internal ACL.
- Mock Firecrawl results are fixtures and are labeled in the Discover UI.
- Live demo URL / Loom / GitHub remote are submission artifacts, not part of the app runtime.

## Scripts

```bash
npm run dev
npm run lint
npm test
npm run build
```
