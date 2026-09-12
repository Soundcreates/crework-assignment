"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  checkAiHealth,
  getDiscoveryRun,
  runSearchDiscovery,
  startDiscovery,
  type SearchDiscoveryResult,
} from "@/lib/api/ai-service";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import type { Company, DiscoveryRun } from "@/types/company";

function formatUnknownError(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (err && typeof err === "object") {
    const maybe = err as { message?: unknown; code?: unknown };
    if (typeof maybe.message === "string" && maybe.message.trim()) {
      const code = typeof maybe.code === "string" ? ` (${maybe.code})` : "";
      return `${maybe.message}${code}`;
    }
  }
  return "Discovery failed";
}

function hintForError(message: string): string | null {
  const lower = message.toLowerCase();
  if (
    lower.includes("could not find the table") ||
    lower.includes("pgrst205") ||
    lower.includes("schema cache")
  ) {
    return "Your Supabase project is missing the app schema. In the Supabase SQL Editor, run supabase/migrations/001_initial_schema.sql, 002_contacts.sql, and 003_review_fixes.sql (then optionally supabase/seed.sql).";
  }
  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("ai service error")
  ) {
    return "Make sure the AI service is running on localhost:8000.";
  }
  return null;
}

export function DiscoverView() {
  const [industries, setIndustries] = useState("SaaS, AI, Developer Tools");
  const [keywords, setKeywords] = useState("");
  const [country, setCountry] = useState("");
  const [maxCompanies, setMaxCompanies] = useState(10);
  const [stages, setStages] = useState("");
  const [employeeRanges, setEmployeeRanges] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [result, setResult] = useState<SearchDiscoveryResult | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [aiHealthy, setAiHealthy] = useState<boolean | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);

  useEffect(() => {
    void checkAiHealth().then(setAiHealthy);
  }, []);

  async function onDiscover() {
    setBusy(true);
    setError(null);
    setHint(null);
    setResult(null);
    setCompanies([]);
    try {
      const industryList = industries
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const keywordList = keywords
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const icp = {
        stages: stages.split(",").map((s) => s.trim()).filter(Boolean),
        employee_ranges: employeeRanges.split(",").map((s) => s.trim()).filter(Boolean),
        countries: country ? [country] : [],
      };

      const supabase = getSupabaseBrowserClient();
      let createdRunId: string | undefined;
      let schemaWarning: string | null = null;
      if (supabase) {
        const { data, error: insertError } = await supabase
          .from("discovery_runs")
          .insert({
            status: "pending",
            industries: industryList,
            country: country || null,
            max_companies: maxCompanies,
          })
          .select("id")
          .single();
        if (insertError) {
          schemaWarning = formatUnknownError(insertError);
        } else {
          createdRunId = data.id;
        }
      }

      if (!supabase) {
        const discovery = await runSearchDiscovery({
          industries: industryList,
          keywords: keywordList,
          country: country || undefined,
          max_companies: maxCompanies,
          discovery_only: false,
          icp,
        });
        setResult(discovery);
        setRunStatus(discovery.status);
        if (discovery.status === "failed") {
          const message = discovery.error ?? "Discovery failed";
          setError(message);
          setHint(hintForError(message));
        }
        return;
      }

      const started = await startDiscovery({
        industries: industryList,
        keywords: keywordList,
        country: country || undefined,
        max_companies: maxCompanies,
        run_id: createdRunId,
        discovery_only: false,
        icp,
      });
      setRunStatus(started.status);

      const terminal = await waitForRun(started.run_id, supabase);
      setResult(terminal);
      setRunStatus(terminal.status);

      if (supabase) {
        const { data } = await supabase
          .from("companies")
          .select("*")
          .eq("discovery_run_id", started.run_id)
          .order("intent_score", { ascending: false })
          .limit(maxCompanies);
        setCompanies((data as Company[]) ?? []);
      }

      if (terminal.status === "failed") {
        const message = terminal.error ?? "Discovery failed";
        setError(message);
        setHint(hintForError(message));
      } else if (terminal.status === "completed_with_errors") {
        setError(terminal.error ?? "Discovery finished with partial AI failures.");
      } else if (schemaWarning) {
        setError(schemaWarning);
        setHint(hintForError(schemaWarning));
      }
    } catch (err) {
      const message = formatUnknownError(err);
      setError(message);
      setHint(hintForError(message));
    } finally {
      setBusy(false);
    }
  }

  const provider = result?.provider ?? "";
  const isMock =
    provider.toLowerCase().includes("mock") || Boolean(result?.used_mock_fallback);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <Link href="/dashboard" className="text-sm text-zinc-500 hover:underline dark:text-zinc-400 dark:hover:text-white">
          ← Back to dashboard
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-white">
          Discover Companies
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-300">
          Search public intent signals, enrich company profiles, extract evidence,
          and score outbound likelihood.
        </p>
        <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
          AI service {aiHealthy ? "online" : aiHealthy === false ? "offline" : "checking…"}
        </p>
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">Industries</span>
          <input
            value={industries}
            onChange={(e) => setIndustries(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">Keywords (optional)</span>
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
            placeholder="appointment setting, dentist marketing"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">Country (optional)</span>
          <input
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
            placeholder="US"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">ICP stages (optional)</span>
          <input
            value={stages}
            onChange={(e) => setStages(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
            placeholder="seed, series a"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">ICP headcount (optional)</span>
          <input
            value={employeeRanges}
            onChange={(e) => setEmployeeRanges(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
            placeholder="1-50, 51-200"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">Maximum companies</span>
          <input
            type="number"
            min={1}
            max={100}
            value={maxCompanies}
            onChange={(e) => setMaxCompanies(Number(e.target.value) || 10)}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-black dark:text-white"
          />
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void onDiscover()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
        >
          {busy ? `Running… ${runStatus ?? ""}` : "Run Discovery"}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
          <p>{error}</p>
          {hint ? <p className="mt-2 text-red-700 dark:text-red-400">{hint}</p> : null}
        </div>
      )}

      {isMock && result && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300">
          Results came from the mock search provider (missing or invalid Firecrawl
          key). These are fixture companies, not live web results.
        </div>
      )}

      {result && (
        <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-5 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300">
          <div>
            Run ID: <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-xs text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{result.run_id}</code>
          </div>
          <div>Status: {result.status}</div>
          <div>Provider: {result.provider}</div>
          {result.costs ? (
            <div>
              Usage: {result.costs.llm_calls} LLM calls · {result.costs.search_requests}{" "}
              searches · {result.costs.crawl_requests} crawls
            </div>
          ) : null}
          <div className="mt-2 space-y-1">
            <div>{result.queries_generated} queries generated</div>
            <div>{result.search_results_found} search results found</div>
            <div>{result.companies_discovered} companies discovered</div>
          </div>
          <Link href="/dashboard" className="inline-block text-zinc-900 underline dark:text-white dark:hover:text-zinc-200">
            View ranked leads on dashboard
          </Link>
          <ul className="mt-4 space-y-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
            {(companies.length > 0
              ? companies.map((company) => ({
                  id: company.id,
                  name: company.name,
                  domain: company.normalized_domain,
                  intent_score: company.intent_score,
                  intent_level: company.intent_level,
                }))
              : result.companies
            ).map((company) => (
              <li key={`${company.name}-${company.id ?? company.domain}`}>
                {company.id ? (
                  <Link
                    href={`/companies/${company.id}`}
                    className="font-medium text-zinc-900 underline dark:text-white dark:hover:text-zinc-200"
                  >
                    {company.name}
                  </Link>
                ) : (
                  <span className="font-medium text-zinc-900 dark:text-white">{company.name}</span>
                )}
                {company.domain ? (
                  <span className="text-zinc-500 dark:text-zinc-400"> · {company.domain}</span>
                ) : null}
                {"intent_score" in company && company.intent_score != null ? (
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                    score {company.intent_score} · {company.intent_level}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

async function waitForRun(
  runId: string,
  supabase: ReturnType<typeof getSupabaseBrowserClient>,
): Promise<SearchDiscoveryResult> {
  const deadline = Date.now() + 420_000;
  while (Date.now() < deadline) {
    if (supabase) {
      const { data } = await supabase
        .from("discovery_runs")
        .select("*")
        .eq("id", runId)
        .limit(1)
        .maybeSingle();
      const row = data as DiscoveryRun | null;
      if (row && (row.status === "completed" || row.status === "failed" || row.status === "completed_with_errors")) {
        return {
          run_id: runId,
          status: row.status,
          queries_generated: row.queries_generated,
          search_results_found: row.search_results_found,
          companies_discovered: row.companies_discovered,
          companies: [],
          provider: row.search_provider || "langgraph",
          used_mock_fallback: Boolean(row.used_mock_fallback),
          error: row.error,
        };
      }
    } else {
      try {
        const remote = await getDiscoveryRun(runId);
        if (remote.status === "completed" || remote.status === "failed" || remote.status === "completed_with_errors") {
          return remote;
        }
      } catch {
        // Keep polling until timeout.
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  return {
    run_id: runId,
    status: "failed",
    queries_generated: 0,
    search_results_found: 0,
    companies_discovered: 0,
    companies: [],
    provider: "unknown",
    error: "Timed out waiting for discovery to finish.",
  };
}
