import type { UserRole } from "@/lib/auth-store";
import type { UILanguage } from "@/lib/ui-language";

export type ClinicalContext = {
  person: string;
  concern: string;
  timeline: string;
  medicines: string;
  goal: string;
};

export const EMPTY_CLINICAL_CONTEXT: ClinicalContext = {
  person: "",
  concern: "",
  timeline: "",
  medicines: "",
  goal: "",
};

export function hasClinicalContext(context: ClinicalContext): boolean {
  return Object.values(context).some((value) => value.trim().length > 0);
}

/**
 * Existing chat/research APIs accept a single query. This creates a compact,
 * explicit context envelope without changing those contracts or hiding what
 * is sent from the user.
 */
export function buildContextualMedicalQuery(
  query: string,
  context: ClinicalContext,
  role: UserRole,
  language: UILanguage,
): string {
  const fields = [
    [
      language === "en" ? "Person / population" : "Người bệnh / quần thể",
      context.person,
    ],
    [
      language === "en" ? "Concern / intervention" : "Vấn đề / can thiệp",
      context.concern,
    ],
    [
      language === "en" ? "Timeline / comparator" : "Diễn tiến / đối chứng",
      context.timeline,
    ],
    [
      language === "en" ? "Medicines / exposures" : "Thuốc / phơi nhiễm",
      context.medicines,
    ],
    [
      language === "en" ? "Decision / outcome" : "Quyết định / kết cục",
      context.goal,
    ],
  ].filter(([, value]) => value.trim());

  if (!fields.length) return query.trim();
  const contextLabel =
    language === "en"
      ? "Structured medical context"
      : "Bối cảnh y khoa có cấu trúc";
  const roleLabel = language === "en" ? "Audience" : "Đối tượng";
  return [
    query.trim(),
    "",
    `[${contextLabel}]`,
    `${roleLabel}: ${role}`,
    ...fields.map(([label, value]) => `- ${label}: ${value.trim()}`),
    language === "en"
      ? "Use this context explicitly; identify missing information and do not infer absent facts."
      : "Hãy dùng rõ bối cảnh này; chỉ ra thông tin còn thiếu và không suy đoán dữ kiện chưa có.",
  ].join("\n");
}
