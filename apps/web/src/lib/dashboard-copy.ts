export const EMPTY_LEADS_CTA = "Run discovery";
export const EMPTY_LEADS_COPY =
  "No companies yet. Run discovery to find outbound leads from public intent signals.";
export const PAGE_SIZE = 25;

export function bulkEnrichButtonLabel(
  busy: boolean,
  current: number,
  total: number,
  unscored: number,
): string {
  if (busy && total > 0) return `Enriching ${current}/${total}`;
  if (busy) return "Enriching…";
  return `Enrich unscored (${unscored})`;
}
