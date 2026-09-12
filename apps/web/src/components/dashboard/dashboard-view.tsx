"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { seedCompanies, seedSignals } from "@/data/seed";
import type { Company, ReviewStatus, Signal } from "@/types/company";
import { intentBadgeClass, signalLabel } from "@/lib/utils";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { checkAiHealth, enrichCompany } from "@/lib/api/ai-service";
import {
  EMPTY_LEADS_COPY,
  EMPTY_LEADS_CTA,
  PAGE_SIZE,
  bulkEnrichButtonLabel,
} from "@/lib/dashboard-copy";
import {
  emptyFilters,
  filterCompanies,
  sortCompanies,
  type LeadFilters,
  type SortKey,
} from "@/lib/leads";

export function DashboardView() {
  const [companies, setCompanies] = useState<Company[]>(
    isSupabaseConfigured() ? [] : seedCompanies,
  );
  const [signals, setSignals] = useState<Signal[]>(
    isSupabaseConfigured() ? [] : seedSignals,
  );
  const [filters, setFilters] = useState<LeadFilters>(emptyFilters);
  const [sortKey, setSortKey] = useState<SortKey>("intent_score");
  const [usingSeed, setUsingSeed] = useState(!isSupabaseConfigured());
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [error, setError] = useState<string | null>(null);
  const [aiHealthy, setAiHealthy] = useState<boolean | null>(null);
  const [page, setPage] = useState(1);
  const [enrichingId, setEnrichingId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{ current: number; total: number } | null>(
    null,
  );
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    void checkAiHealth().then(setAiHealthy);
  }, []);

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client) return;

    async function load(db: NonNullable<ReturnType<typeof getSupabaseBrowserClient>>) {
      setLoading(true);
      const [companyRes, signalRes] = await Promise.all([
        db.from("companies").select("*").order("intent_score", { ascending: false }),
        db.from("signals").select("*"),
      ]);
      if (companyRes.error) {
        setError(companyRes.error.message);
        setLoading(false);
        return;
      }
      setError(null);
      setCompanies((companyRes.data as Company[]) ?? []);
      setSignals((signalRes.data as Signal[]) ?? []);
      setUsingSeed(false);
      setLoading(false);
    }

    void load(client);

    const scheduleLoad = () => {
      if (reloadTimer.current) clearTimeout(reloadTimer.current);
      reloadTimer.current = setTimeout(() => {
        void load(client);
      }, 750);
    };

    const companyChannel = client
      .channel("companies-live")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "companies" },
        scheduleLoad,
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "signals" },
        scheduleLoad,
      )
      .subscribe();

    return () => {
      if (reloadTimer.current) clearTimeout(reloadTimer.current);
      void client.removeChannel(companyChannel);
    };
  }, []);

  async function updateReviewStatus(id: string, review_status: ReviewStatus) {
    setCompanies((current) =>
      current.map((c) => (c.id === id ? { ...c, review_status } : c)),
    );
    const supabase = getSupabaseBrowserClient();
    if (!supabase) return;
    const { error: updateError } = await supabase
      .from("companies")
      .update({ review_status })
      .eq("id", id);
    if (updateError) setError(updateError.message);
  }

  async function onEnrich(id: string) {
    setEnrichingId(id);
    setError(null);
    try {
      await enrichCompany(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enrich failed");
    } finally {
      setEnrichingId(null);
    }
  }

  async function onEnrichUnscored() {
    const targets = companies.filter((c) => c.intent_score === 0);
    if (targets.length === 0) return;
    setBulkBusy(true);
    setBulkProgress({ current: 1, total: targets.length });
    setError(null);
    let failures = 0;
    try {
      for (let i = 0; i < targets.length; i += 1) {
        setBulkProgress({ current: i + 1, total: targets.length });
        setEnrichingId(targets[i].id);
        try {
          await enrichCompany(targets[i].id);
        } catch {
          failures += 1;
        }
      }
      if (failures > 0) {
        setError(`${failures} of ${targets.length} enrichments failed`);
      }
    } finally {
      setBulkBusy(false);
      setBulkProgress(null);
      setEnrichingId(null);
    }
  }

  const filtered = useMemo(
    () => sortCompanies(filterCompanies(companies, signals, filters), sortKey),
    [companies, signals, filters, sortKey],
  );

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const unscored = companies.filter((c) => c.intent_score === 0).length;
  const emptyConfigured =
    isSupabaseConfigured() && !usingSeed && !loading && companies.length === 0;

  const highIntent = companies.filter((c) => c.intent_level === "HIGH").length;
  const avgScore =
    companies.length === 0
      ? 0
      : Math.round(
          companies.reduce((sum, c) => sum + c.intent_score, 0) / companies.length,
        );

  const industries = Array.from(
    new Set(companies.map((c) => c.industry).filter(Boolean)),
  ) as string[];
  const stages = Array.from(
    new Set(companies.map((c) => c.estimated_stage).filter(Boolean)),
  ) as string[];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
            Sales Intelligence
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Lead Dashboard
          </h1>
          <p className="mt-2 max-w-2xl text-zinc-600 dark:text-zinc-300">
            Companies ranked by evidence-backed buying intent for outbound
            outreach.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              aiHealthy
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 dark:border dark:border-emerald-800/60"
                : aiHealthy === false
                  ? "bg-amber-100 text-amber-900 dark:bg-amber-950/70 dark:text-amber-300 dark:border dark:border-amber-800/60"
                  : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            AI service {aiHealthy ? "online" : aiHealthy === false ? "offline" : "checking"}
          </span>
          {(unscored > 0 || bulkBusy) && (
            <button
              type="button"
              aria-label="Enrich unscored"
              disabled={bulkBusy}
              onClick={() => void onEnrichUnscored()}
              className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              {bulkEnrichButtonLabel(
                bulkBusy,
                bulkProgress?.current ?? 0,
                bulkProgress?.total ?? 0,
                unscored,
              )}
            </button>
          )}
          <Link
            href="/discover"
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            Discover Leads
          </Link>
        </div>
      </div>

      {usingSeed && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300">
          Showing seeded demo data. Connect Supabase env vars to load live
          companies.
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}
      {loading && (
        <div className="text-sm text-zinc-500 dark:text-zinc-400">Loading companies…</div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Companies discovered" value={String(companies.length)} />
        <Stat label="High-intent leads" value={String(highIntent)} />
        <Stat label="Average score" value={String(avgScore)} />
        <Stat label="Signals detected" value={String(signals.length)} />
      </div>

      <div className="grid gap-3 rounded-xl border border-zinc-200 bg-white p-4 md:grid-cols-6 dark:border-zinc-800 dark:bg-zinc-900/90">
        <Select
          label="Industry"
          value={filters.industry}
          onChange={(industry) => setFilters((f) => ({ ...f, industry }))}
          options={["all", ...industries]}
        />
        <Select
          label="Intent level"
          value={filters.intentLevel}
          onChange={(intentLevel) => setFilters((f) => ({ ...f, intentLevel }))}
          options={["all", "HIGH", "MEDIUM HIGH", "MEDIUM", "LOW"]}
        />
        <Select
          label="Signal type"
          value={filters.signalType}
          onChange={(signalType) => setFilters((f) => ({ ...f, signalType }))}
          options={[
            "all",
            "funding",
            "sales_hiring",
            "expansion",
            "public_demand",
            "other_growth",
          ]}
        />
        <Select
          label="Stage"
          value={filters.stage}
          onChange={(stage) => setFilters((f) => ({ ...f, stage }))}
          options={["all", ...stages]}
        />
        <label className="text-sm">
          <span className="mb-1 block text-zinc-500 dark:text-zinc-400">Minimum score</span>
          <input
            type="number"
            min={0}
            max={100}
            value={filters.minScore}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                minScore: Number(e.target.value) || 0,
              }))
            }
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </label>
        <Select
          label="Sort"
          value={sortKey}
          onChange={(value) => setSortKey(value as SortKey)}
          options={["intent_score", "first_discovered_at", "name"]}
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/90">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-zinc-50 text-zinc-500 dark:bg-zinc-800/60 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Industry</th>
              <th className="px-4 py-3 font-medium">Stage</th>
              <th className="px-4 py-3 font-medium">Signals</th>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Intent</th>
              <th className="px-4 py-3 font-medium">Review</th>
              <th className="px-4 py-3 font-medium">Detected</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((company) => (
              <tr key={company.id} className="border-t border-zinc-100 hover:bg-zinc-50/50 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                <td className="px-4 py-3">
                  <Link
                    href={`/companies/${company.id}`}
                    className="font-medium text-zinc-900 hover:underline dark:text-zinc-100"
                  >
                    {company.name}
                  </Link>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                    {company.normalized_domain}
                    {company.source === "mock" ? (
                      <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-900 dark:bg-amber-950/70 dark:text-amber-300 dark:border dark:border-amber-800/60">
                        mock
                      </span>
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300">
                  {company.industry ?? "—"}
                </td>
                <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300">
                  {company.estimated_stage ?? "—"}
                </td>
                <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300">
                  {(
                    signals
                      .filter((s) => s.company_id === company.id)
                      .map((s) => s.signal_type)
                      .filter((type, index, all) => all.indexOf(type) === index)
                  )
                    .map(signalLabel)
                    .join(", ") || "—"}
                </td>
                <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">
                  {company.intent_score}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${intentBadgeClass(company.intent_level)}`}
                  >
                    {company.intent_level}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={company.review_status}
                    onChange={(e) =>
                      void updateReviewStatus(
                        company.id,
                        e.target.value as ReviewStatus,
                      )
                    }
                    className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  >
                    <option value="new">new</option>
                    <option value="reviewing">reviewing</option>
                    <option value="qualified">qualified</option>
                    <option value="not_relevant">not relevant</option>
                    <option value="contacted">contacted</option>
                  </select>
                </td>
                <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400">
                  {company.first_discovered_at
                    ? new Date(company.first_discovered_at).toLocaleDateString()
                    : "—"}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    disabled={bulkBusy || enrichingId === company.id}
                    onClick={() => void onEnrich(company.id)}
                    className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
                  >
                    {enrichingId === company.id ? "Enriching…" : "Enrich"}
                  </button>
                </td>
              </tr>
            ))}
            {!loading && emptyConfigured && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-zinc-500 dark:text-zinc-400">
                  <p>{EMPTY_LEADS_COPY}</p>
                  <Link
                    href="/discover"
                    className="mt-3 inline-block rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                  >
                    {EMPTY_LEADS_CTA}
                  </Link>
                </td>
              </tr>
            )}
            {!loading && !emptyConfigured && filtered.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-10 text-center text-zinc-500 dark:text-zinc-400"
                >
                  No companies match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-3 text-sm">
          <button
            type="button"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-md border border-zinc-300 bg-white px-3 py-1 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            Previous
          </button>
          <span className="text-zinc-700 dark:text-zinc-300">
            Page {safePage} of {pageCount}
          </span>
          <button
            type="button"
            disabled={safePage >= pageCount}
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            className="rounded-md border border-zinc-300 bg-white px-3 py-1 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900/90">
      <div className="text-sm text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
        {value}
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-zinc-500 dark:text-zinc-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 capitalize dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === "all" ? "All" : option.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}
