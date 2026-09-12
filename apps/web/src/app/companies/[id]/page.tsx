import { CompanyDetail } from "@/components/company/company-detail";

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CompanyDetail id={id} />;
}
