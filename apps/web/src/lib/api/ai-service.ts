const AI_SERVICE_URL =
  process.env.NEXT_PUBLIC_AI_SERVICE_URL ?? "http://localhost:8000";

export type DiscoveryIcp = {
  industries?: string[];
  employee_ranges?: string[];
  stages?: string[];
  countries?: string[];
};

export async function startDiscovery(payload: {
  industries: string[];
  keywords?: string[];
  country?: string;
  max_companies?: number;
  run_id?: string;
  discovery_only?: boolean;
  icp?: DiscoveryIcp;
}): Promise<{ run_id: string; status: string }> {
  const response = await fetch(`${AI_SERVICE_URL}/v1/discovery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      discovery_only: false,
      ...payload,
    }),
  });
  if (!response.ok) {
    throw new Error(`AI service error: ${response.status}`);
  }
  return response.json();
}

export type SearchDiscoveryResult = {
  run_id: string;
  status: string;
  queries_generated: number;
  search_results_found: number;
  companies_discovered: number;
  companies: Array<{
    id: string | null;
    name: string;
    domain: string | null;
    website: string | null;
    source_url: string | null;
    confidence: number | null;
    intent_score: number | null;
    intent_level: string | null;
    source?: string | null;
  }>;
  provider: string;
  used_mock_fallback?: boolean;
  error: string | null;
  costs?: {
    llm_calls: number;
    llm_tokens: number;
    search_requests: number;
    crawl_requests: number;
  } | null;
};

export async function runSearchDiscovery(payload: {
  industries: string[];
  keywords?: string[];
  country?: string;
  max_companies?: number;
  run_id?: string;
  discovery_only?: boolean;
  icp?: DiscoveryIcp;
}): Promise<SearchDiscoveryResult> {
  const response = await fetch(`${AI_SERVICE_URL}/v1/discovery/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ discovery_only: false, ...payload }),
  });
  if (!response.ok) {
    throw new Error(`AI service error: ${response.status}`);
  }
  return response.json();
}

export async function getDiscoveryRun(runId: string): Promise<SearchDiscoveryResult> {
  const response = await fetch(
    `${AI_SERVICE_URL}/v1/discovery/${runId}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`AI service error: ${response.status}`);
  }
  return response.json();
}

export async function enrichCompany(companyId: string): Promise<{
  company_id: string;
  status: string;
  intent_score: number | null;
  intent_level: string | null;
}> {
  const response = await fetch(
    `${AI_SERVICE_URL}/v1/companies/${companyId}/enrich`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`AI service error: ${response.status}`);
  }
  return response.json();
}

export async function enrichUnscored(): Promise<{ enriched: number; failed: number }> {
  const response = await fetch(`${AI_SERVICE_URL}/v1/companies/enrich-unscored`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`AI service error: ${response.status}`);
  }
  return response.json();
}

export async function checkAiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/health`, {
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
}
