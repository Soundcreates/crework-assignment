"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { seedCompanies, seedSignals } from "@/data/seed";
import type { Company, Contact, Signal } from "@/types/company";
import { intentBadgeClass, signalLabel } from "@/lib/utils";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { SCORE_EXPLAINER } from "@/lib/scoring";
import { enrichCompany } from "@/lib/api/ai-service";

export function CompanyDetail({ id }: { id: string }) {
  const seedCompany = seedCompanies.find((c) => c.id === id) ?? null;
  const [company, setCompany] = useState<Company | null>(seedCompany);
  const [signals, setSignals] = useState<Signal[]>(
    seedSignals.filter((s) => s.company_id === id),
  );
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(() => Boolean(getSupabaseBrowserClient()));
  const [error, setError] = useState<string | null>(
    getSupabaseBrowserClient() || seedCompany
      ? null
      : "Company not found in demo seed data.",
  );
  const [enriching, setEnriching] = useState(false);

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client) return;

    async function load(db: NonNullable<ReturnType<typeof getSupabaseBrowserClient>>) {
      const [companyRes, signalRes, contactRes] = await Promise.all([
        db.from("companies").select("*").eq("id", id).limit(1).maybeSingle(),
        db.from("signals").select("*").eq("company_id", id),
        db.from("contacts").select("*").eq("company_id", id),
      ]);
      if (companyRes.error) {
        setError(companyRes.error.message);
        setLoading(false);
        return;
      }
      if (companyRes.data) {
        setCompany(companyRes.data as Company);
        setSignals((signalRes.data as Signal[]) ?? []);
        setContacts((contactRes.data as Contact[]) ?? []);
      } else if (!seedCompany) {
        setError("Company not found.");
        setCompany(null);
      }
      setLoading(false);
    }
    void load(client);
  }, [id, seedCompany]);

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading company…</p>;
  }

  if (!company) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard" className="text-sm text-zinc-500 hover:underline">
          ← Back to dashboard
        </Link>
        <h1 className="text-2xl font-semibold">Company not found</h1>
        <p className="text-zinc-600">{error ?? "No company record for this id."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Link href="/dashboard" className="text-sm text-zinc-500 hover:underline">
        ← Back to dashboard
      </Link>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
            {company.name}
            {company.source === "mock" ? (
              <span className="ml-3 align-middle rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-amber-900">
                mock
              </span>
            ) : null}
          </h1>
          <p className="mt-2 text-zinc-600">{company.description}</p>
          {company.website && (
            <a
              href={company.website}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-block text-sm text-zinc-900 underline"
            >
              {company.website}
            </a>
          )}
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white px-5 py-4 text-center">
          <div className="text-sm text-zinc-500">Intent score</div>
          <div className="mt-1 text-4xl font-semibold">{company.intent_score}</div>
          <span
            className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${intentBadgeClass(company.intent_level)}`}
          >
            {company.intent_level}
          </span>
          <button
            type="button"
            disabled={enriching}
            onClick={() => {
              setEnriching(true);
              void enrichCompany(company.id)
                .catch((err: unknown) =>
                  setError(err instanceof Error ? err.message : "Enrich failed"),
                )
                .finally(() => setEnriching(false));
            }}
            className="mt-3 block w-full rounded-md border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-50 disabled:opacity-60"
          >
            {enriching ? "Enriching…" : "Re-enrich"}
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Meta label="Industry" value={company.industry} />
        <Meta label="Stage" value={company.estimated_stage} />
        <Meta label="Size" value={company.estimated_employee_range} />
        <Meta label="HQ" value={company.headquarters} />
      </div>

      <section className="rounded-xl border border-zinc-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-zinc-900">
          Why this lead matters
        </h2>
        <p className="mt-3 leading-7 text-zinc-700">{company.ai_summary}</p>
        <p className="mt-4 text-sm leading-6 text-zinc-500">{SCORE_EXPLAINER}</p>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-zinc-900">Detected signals</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {signals.map((signal) => (
            <article
              key={signal.id}
              className="rounded-xl border border-zinc-200 bg-white p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-medium capitalize text-zinc-900">
                  {signalLabel(signal.signal_type)}
                </h3>
                <span className="text-sm text-zinc-500">
                  Strength {(Number(signal.strength) * 100).toFixed(0)}%
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-zinc-700">
                {signal.explanation}
              </p>
              <blockquote className="mt-4 border-l-2 border-zinc-300 pl-3 text-sm italic text-zinc-600">
                “{signal.evidence}”
              </blockquote>
              {signal.source_url && (
                <a
                  href={signal.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-sm text-zinc-900 underline"
                >
                  Source
                </a>
              )}
            </article>
          ))}
          {signals.length === 0 && (
            <p className="text-sm text-zinc-500">No signals stored yet.</p>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900">
          Relevant contacts
        </h2>
        {contacts.length > 0 ? (
          <ul className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white">
            {contacts.map((contact) => (
              <li key={contact.id} className="px-4 py-3">
                <div className="font-medium text-zinc-900">{contact.name}</div>
                <div className="text-sm text-zinc-500">
                  {contact.title ?? "Role unknown"}
                </div>
                {contact.source_url && (
                  <a
                    href={contact.source_url}
                    className="text-xs underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Source
                  </a>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">
            No public contacts stored yet. Apply supabase/migrations/002_contacts.sql
            and re-enrich this company.
          </p>
        )}
      </section>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="text-sm text-zinc-500">{label}</div>
      <div className="mt-1 font-medium text-zinc-900">{value ?? "—"}</div>
    </div>
  );
}
