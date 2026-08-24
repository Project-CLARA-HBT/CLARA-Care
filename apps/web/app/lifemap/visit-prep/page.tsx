import { redirect } from "next/navigation";

/**
 * Spec v5 Section 6.19: /lifemap/visit-prep
 * Shell: ALIAS_CONTEXT -> Canonical Redirect to /care/prepare or /visits/new.
 * Preserves query parameters and transitions directly to the canonical destination.
 */
export default async function LifeMapVisitPrepPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedParams = searchParams ? await searchParams : undefined;
  const visitId =
    typeof resolvedParams?.visitId === "string"
      ? resolvedParams.visitId
      : typeof resolvedParams?.visit === "string"
        ? resolvedParams.visit
        : "";

  if (visitId) {
    redirect(`/care/prepare?visitId=${encodeURIComponent(visitId)}`);
  }
  redirect("/care/prepare");
}
