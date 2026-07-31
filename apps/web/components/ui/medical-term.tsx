import type { MedicalConceptId, MedicalGlossaryAudience } from "@/lib/medical-glossary";
import {
  MEDICAL_GLOSSARY_VERSION,
  getMedicalGlossaryEntry,
  getMedicalGlossaryText,
} from "@/lib/medical-glossary";
import type { UILanguage } from "@/lib/ui-language";

/**
 * Renders a structured medical concept supplied by a trusted response. It is
 * intentionally not a free-text highlighter: callers must never pass user
 * input, a model completion, or an inferred diagnosis as `concept`.
 */
export function MedicalTerm({
  concept,
  locale = "vi",
  audience = "lay",
  expandable = false,
  className = "",
}: {
  concept: MedicalConceptId | string;
  locale?: UILanguage;
  audience?: MedicalGlossaryAudience;
  expandable?: boolean;
  className?: string;
}) {
  const entry = getMedicalGlossaryEntry(concept);
  const text = getMedicalGlossaryText(concept, locale, audience);
  if (!entry || !text) return null;

  if (!expandable) {
    return (
      <span
        className={`font-medium text-[var(--text-primary)] ${className}`}
        title={text.description}
        data-medical-concept={entry.id}
        data-glossary-version={MEDICAL_GLOSSARY_VERSION}
      >
        {text.label}
      </span>
    );
  }

  const expanded = entry.text[locale].expanded;
  const professional = entry.text[locale].professional;
  const moreLabel = locale === "vi" ? "Xem giải thích" : "See explanation";
  const professionalLabel = locale === "vi" ? "Thuật ngữ chuyên môn" : "Professional term";

  return (
    <details
      className={`group rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/55 px-3 py-2 text-sm ${className}`}
      data-medical-concept={entry.id}
      data-glossary-version={MEDICAL_GLOSSARY_VERSION}
    >
      <summary className="cursor-pointer list-none font-medium text-[var(--text-primary)] marker:hidden">
        <span>{text.label}</span>
        <span className="ml-2 text-xs font-normal text-[var(--text-secondary)]">{moreLabel}</span>
      </summary>
      <p className="mt-2 leading-6 text-[var(--text-secondary)]">{expanded.description}</p>
      <p className="mt-2 border-t border-[color:var(--shell-border)] pt-2 text-xs leading-5 text-[var(--text-muted)]">
        <span className="font-semibold text-[var(--text-secondary)]">{professionalLabel}: </span>
        {professional.label}
      </p>
    </details>
  );
}
