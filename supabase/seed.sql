-- Seed data for dashboard development before AI pipeline exists

insert into public.companies (
  id, name, normalized_name, website, normalized_domain, description,
  industry, estimated_employee_range, estimated_stage, business_model,
  headquarters, intent_score, intent_level, ai_summary, review_status
) values
(
  'a1111111-1111-1111-1111-111111111111',
  'Acme AI',
  'acme ai',
  'https://acme.ai',
  'acme.ai',
  'B2B AI sales enablement platform for outbound teams.',
  'AI',
  '11-50',
  'Seed',
  'B2B SaaS',
  'San Francisco, US',
  87,
  'HIGH',
  'Acme AI recently raised funding and is actively hiring SDRs while expanding into North America. The combination suggests the company is investing in go-to-market infrastructure, making it a strong candidate for outbound sales support.',
  'new'
),
(
  'a2222222-2222-2222-2222-222222222222',
  'Northstar Labs',
  'northstar labs',
  'https://northstarlabs.io',
  'northstarlabs.io',
  'Developer tools for cloud infrastructure automation.',
  'Developer Tools',
  '51-200',
  'Series A',
  'B2B SaaS',
  'Austin, US',
  72,
  'MEDIUM HIGH',
  'Northstar Labs is hiring account executives and publicly discussing international expansion after a Series A raise, indicating rising outbound capacity needs.',
  'reviewing'
),
(
  'a3333333-3333-3333-3333-333333333333',
  'Brightpath Commerce',
  'brightpath commerce',
  'https://brightpath.com',
  'brightpath.com',
  'E-commerce analytics for mid-market retailers.',
  'SaaS',
  '11-50',
  'Seed',
  'B2B SaaS',
  'Toronto, CA',
  54,
  'MEDIUM',
  'Brightpath is expanding into US retail markets and posting growth content, though sales hiring signals are still moderate.',
  'new'
),
(
  'a4444444-4444-4444-4444-444444444444',
  'Orbit Metrics',
  'orbit metrics',
  'https://orbitmetrics.com',
  'orbitmetrics.com',
  'Product analytics for B2B SaaS companies.',
  'SaaS',
  '1-10',
  'Pre-seed',
  'B2B SaaS',
  'Berlin, DE',
  31,
  'LOW',
  'Orbit Metrics shows early growth discussion but lacks recent funding or sales hiring evidence.',
  'not_relevant'
),
(
  'a5555555-5555-5555-5555-555555555555',
  'Helix Stack',
  'helix stack',
  'https://helixstack.dev',
  'helixstack.dev',
  'API infrastructure for AI agent workflows.',
  'AI',
  '11-50',
  'Series A',
  'B2B SaaS',
  'New York, US',
  81,
  'HIGH',
  'Helix Stack closed a Series A and is aggressively hiring BDRs while launching in new European markets.',
  'qualified'
);

insert into public.signals (
  company_id, signal_type, strength, title, explanation, evidence,
  source_url, source_domain, occurred_at
) values
(
  'a1111111-1111-1111-1111-111111111111',
  'funding',
  0.920,
  'Seed round announced',
  'Company publicly announced a recent seed funding round.',
  'We raised a $4.2M seed round to accelerate go-to-market.',
  'https://techcrunch.com/acme-ai-seed',
  'techcrunch.com',
  now() - interval '12 days'
),
(
  'a1111111-1111-1111-1111-111111111111',
  'sales_hiring',
  0.950,
  'Hiring SDRs',
  'The company appears to be actively expanding its outbound sales organization.',
  'We are hiring three Sales Development Representatives.',
  'https://acme.ai/careers',
  'acme.ai',
  now() - interval '5 days'
),
(
  'a1111111-1111-1111-1111-111111111111',
  'expansion',
  0.780,
  'North America expansion',
  'Public messaging indicates geographic GTM expansion.',
  'Expanding into North America with a dedicated outbound team.',
  'https://acme.ai/blog/north-america',
  'acme.ai',
  now() - interval '20 days'
),
(
  'a2222222-2222-2222-2222-222222222222',
  'funding',
  0.880,
  'Series A closed',
  'Recent Series A funding supports GTM investment.',
  'Northstar Labs raises $18M Series A to scale sales.',
  'https://news.ycombinator.com/northstar-series-a',
  'news.ycombinator.com',
  now() - interval '40 days'
),
(
  'a2222222-2222-2222-2222-222222222222',
  'sales_hiring',
  0.840,
  'Hiring account executives',
  'Open AE roles suggest outbound capacity growth.',
  'We''re hiring Account Executives to build our sales team.',
  'https://northstarlabs.io/jobs',
  'northstarlabs.io',
  now() - interval '8 days'
),
(
  'a3333333-3333-3333-3333-333333333333',
  'expansion',
  0.760,
  'US market launch',
  'Company is expanding into the US market.',
  'Launching in new markets across the United States.',
  'https://brightpath.com/blog/us-expansion',
  'brightpath.com',
  now() - interval '25 days'
),
(
  'a3333333-3333-3333-3333-333333333333',
  'public_demand',
  0.550,
  'Looking for sales help',
  'Founder content mentions needing marketing/sales support.',
  'Looking for partners who can help us scale outbound.',
  'https://linkedin.com/posts/brightpath-growth',
  'linkedin.com',
  now() - interval '15 days'
),
(
  'a4444444-4444-4444-4444-444444444444',
  'other_growth',
  0.420,
  'Growth blog post',
  'General growth discussion without strong buying signals.',
  'We are thinking about how to grow faster next year.',
  'https://orbitmetrics.com/blog/growth',
  'orbitmetrics.com',
  now() - interval '110 days'
),
(
  'a5555555-5555-5555-5555-555555555555',
  'funding',
  0.910,
  'Series A announced',
  'Recent funding provides budget for outbound programs.',
  'Helix Stack announces $22M Series A led by top-tier VCs.',
  'https://techcrunch.com/helix-stack-series-a',
  'techcrunch.com',
  now() - interval '18 days'
),
(
  'a5555555-5555-5555-5555-555555555555',
  'sales_hiring',
  0.930,
  'Hiring BDRs',
  'Multiple BDR openings indicate outbound team build-out.',
  'Building our sales team — hiring Business Development Representatives.',
  'https://helixstack.dev/careers',
  'helixstack.dev',
  now() - interval '3 days'
),
(
  'a5555555-5555-5555-5555-555555555555',
  'expansion',
  0.800,
  'European launch',
  'Company is expanding into European markets.',
  'International expansion into Germany, France, and the UK.',
  'https://helixstack.dev/blog/europe',
  'helixstack.dev',
  now() - interval '22 days'
);

insert into public.discovery_runs (
  id, status, industries, started_at, completed_at,
  queries_generated, search_results_found,
  companies_discovered, companies_enriched, companies_failed
) values (
  'b1111111-1111-1111-1111-111111111111',
  'completed',
  array['SaaS', 'AI', 'Developer Tools'],
  now() - interval '2 hours',
  now() - interval '1 hour 40 minutes',
  12,
  64,
  5,
  5,
  0
);
