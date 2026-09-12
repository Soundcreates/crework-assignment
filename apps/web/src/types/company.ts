export type IntentLevel = "HIGH" | "MEDIUM HIGH" | "MEDIUM" | "LOW";
export type ReviewStatus =
  | "new"
  | "reviewing"
  | "qualified"
  | "not_relevant"
  | "contacted";

export type SignalType =
  | "funding"
  | "sales_hiring"
  | "expansion"
  | "public_demand"
  | "other_growth";

export interface Company {
  id: string;
  name: string;
  normalized_name: string;
  website: string | null;
  normalized_domain: string | null;
  description: string | null;
  industry: string | null;
  estimated_employee_range: string | null;
  estimated_stage: string | null;
  business_model: string | null;
  headquarters: string | null;
  intent_score: number;
  intent_level: IntentLevel;
  ai_summary: string | null;
  review_status: ReviewStatus;
  first_discovered_at: string;
  last_updated_at: string;
  discovery_run_id?: string | null;
  source?: "live" | "mock" | "manual" | null;
  last_checked_at?: string | null;
}

export interface Signal {
  id: string;
  company_id: string;
  signal_type: SignalType;
  strength: number;
  title: string | null;
  explanation: string;
  evidence: string;
  source_url: string;
  source_domain: string | null;
  occurred_at: string | null;
  detected_at: string;
}

export interface Contact {
  id: string;
  company_id: string;
  name: string;
  title: string | null;
  source_url: string | null;
}

export interface DiscoveryRun {
  id: string;
  status:
    | "pending"
    | "searching"
    | "enriching"
    | "scoring"
    | "completed"
    | "completed_with_errors"
    | "failed";
  industries: string[] | null;
  country: string | null;
  max_companies: number | null;
  started_at: string;
  completed_at: string | null;
  queries_generated: number;
  search_results_found: number;
  companies_discovered: number;
  companies_enriched: number;
  companies_failed: number;
  error: string | null;
  search_provider?: string | null;
  used_mock_fallback?: boolean | null;
}
