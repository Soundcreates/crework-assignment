import { describe, expect, it } from "vitest";
import { seedCompanies, seedSignals } from "@/data/seed";
import {
  emptyFilters,
  filterCompanies,
  findCompany,
  sortCompanies,
} from "@/lib/leads";
import {
  EMPTY_LEADS_COPY,
  EMPTY_LEADS_CTA,
  PAGE_SIZE,
  bulkEnrichButtonLabel,
} from "@/lib/dashboard-copy";
import { enrichCompany, enrichUnscored } from "@/lib/api/ai-service";

describe("lead filters and sort", () => {
  it("filters by public_demand using live signal rows", () => {
    const filtered = filterCompanies(seedCompanies, seedSignals, {
      ...emptyFilters,
      signalType: "public_demand",
    });
    expect(filtered.map((c) => c.name)).toEqual(["Brightpath Commerce"]);
  });

  it("sorts by name", () => {
    const sorted = sortCompanies(seedCompanies, "name");
    expect(sorted[0]?.name).toBe("Acme AI");
  });

  it("resolves a non-seed-style id from injected company data", () => {
    const live = {
      ...seedCompanies[0],
      id: "11111111-2222-3333-4444-555555555555",
      name: "Live Co",
    };
    expect(findCompany([live], live.id)?.name).toBe("Live Co");
  });
});

describe("dashboard empty state and enrich client", () => {
  it("exposes empty-state copy and pagination size", () => {
    expect(EMPTY_LEADS_CTA).toBe("Run discovery");
    expect(EMPTY_LEADS_COPY.toLowerCase()).toContain("no companies");
    expect(PAGE_SIZE).toBeGreaterThan(0);
  });

  it("exports enrich API helpers", () => {
    expect(typeof enrichCompany).toBe("function");
    expect(typeof enrichUnscored).toBe("function");
  });

  it("shows bulk enrich progress as Enriching current/total", () => {
    expect(bulkEnrichButtonLabel(true, 1, 30, 30)).toBe("Enriching 1/30");
    expect(bulkEnrichButtonLabel(true, 12, 30, 18)).toBe("Enriching 12/30");
    expect(bulkEnrichButtonLabel(false, 0, 0, 7)).toBe("Enrich unscored (7)");
  });
});
