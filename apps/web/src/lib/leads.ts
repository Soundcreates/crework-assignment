import type { Company, IntentLevel, Signal, SignalType } from "@/types/company";

export type SortKey = "intent_score" | "first_discovered_at" | "name";

export type LeadFilters = {
  industry: string;
  intentLevel: string;
  signalType: string;
  stage: string;
  minScore: number;
};

export const emptyFilters: LeadFilters = {
  industry: "all",
  intentLevel: "all",
  signalType: "all",
  stage: "all",
  minScore: 0,
};

export function buildSignalMap(signals: Signal[]): Map<string, SignalType[]> {
  const map = new Map<string, SignalType[]>();
  for (const signal of signals) {
    const existing = map.get(signal.company_id) ?? [];
    if (!existing.includes(signal.signal_type)) {
      existing.push(signal.signal_type);
    }
    map.set(signal.company_id, existing);
  }
  return map;
}

export function filterCompanies(
  companies: Company[],
  signals: Signal[],
  filters: LeadFilters,
): Company[] {
  const signalMap = buildSignalMap(signals);
  return companies.filter((c) => {
    if (filters.industry !== "all" && c.industry !== filters.industry) return false;
    if (
      filters.intentLevel !== "all" &&
      c.intent_level !== (filters.intentLevel as IntentLevel)
    ) {
      return false;
    }
    if (filters.stage !== "all" && c.estimated_stage !== filters.stage) return false;
    if (c.intent_score < filters.minScore) return false;
    if (filters.signalType !== "all") {
      const types = signalMap.get(c.id) ?? [];
      if (!types.includes(filters.signalType as SignalType)) return false;
    }
    return true;
  });
}

export function findCompany(companies: Company[], id: string): Company | undefined {
  return companies.find((company) => company.id === id);
}

export function sortCompanies(
  companies: Company[],
  sortKey: SortKey,
): Company[] {
  return [...companies].sort((a, b) => {
    if (sortKey === "name") {
      return a.name.localeCompare(b.name);
    }
    if (sortKey === "first_discovered_at") {
      return (
        new Date(b.first_discovered_at).getTime() -
        new Date(a.first_discovered_at).getTime()
      );
    }
    return b.intent_score - a.intent_score;
  });
}
