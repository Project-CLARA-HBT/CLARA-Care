import { redirect } from "next/navigation";

/**
 * Spec v5 Section 6.19: /lifemap/visit-prep
 * Shell: ALIAS_CONTEXT -> Canonical Redirect to /care/prepare.
 * Cầu nối liền mạch từ LifeMap sang Trợ lý chuẩn bị buổi khám (/care/prepare).
 * Bảo toàn đầy đủ tham số truy vấn (visitId, episodeId, journey, focus, source)
 * và chuyển hướng trực tiếp đến đích chuẩn hoá.
 */
export default async function LifeMapVisitPrepPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedParams = searchParams ? await searchParams : undefined;
  const params = new URLSearchParams();

  if (resolvedParams) {
    for (const [key, value] of Object.entries(resolvedParams)) {
      if (typeof value === "string") {
        params.set(key, value);
      } else if (Array.isArray(value)) {
        value.forEach((v) => params.append(key, v));
      }
    }
  }

  // Handle visit parameter alias mapping (visit -> visitId)
  const visitId =
    typeof resolvedParams?.visitId === "string"
      ? resolvedParams.visitId
      : typeof resolvedParams?.visit === "string"
        ? resolvedParams.visit
        : "";

  if (visitId && !params.has("visitId")) {
    params.set("visitId", visitId);
  }

  const queryString = params.toString();
  if (queryString) {
    redirect(`/care/prepare?${queryString}`);
  }
  redirect("/care/prepare");
}
