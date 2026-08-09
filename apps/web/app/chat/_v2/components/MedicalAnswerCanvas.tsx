import type { UserRole } from "@/lib/auth-store";
import type { ClinicalAnswerPackage } from "@/lib/chat";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import type { ReactNode } from "react";
import Icon, { type IconName } from "@/components/ui/icon";

type MedicalAnswerCanvasProps = {
  answer: ClinicalAnswerPackage;
  role: UserRole;
  uiLanguage: UILanguage;
};

export default function MedicalAnswerCanvas({
  answer,
  role,
  uiLanguage,
}: MedicalAnswerCanvasProps) {
  const copy = (
    key: UITranslationKey,
    values: Record<string, string | number> = {},
  ) => t(uiLanguage, key, values);
  const isClinical = role === "doctor" || role === "admin";
  const urgent =
    answer.triage.emergency || answer.triage.level === "urgent_review";
  const urgencyTone = answer.triage.emergency
    ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]"
    : urgent
      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]"
      : "border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)]";

  return (
    <section
      className="mt-4 overflow-hidden rounded-2xl border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)]"
      aria-label={copy("chat.answerCanvas.aria")}
    >
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-[color:var(--shell-border)] px-3.5 py-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-brand)]">
            {copy(
              isClinical
                ? "chat.answerCanvas.eyebrow.clinical"
                : "chat.answerCanvas.eyebrow.personal",
            )}
          </p>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">
            {copy("chat.answerCanvas.description")}
          </p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${urgencyTone}`}
        >
          {answer.triage.level.replaceAll("_", " ")}
        </span>
      </header>

      <div className="grid gap-2.5 p-2.5 md:grid-cols-2">
        <CanvasSection
          icon="emergency_home"
          title={copy("chat.answerCanvas.urgency.title")}
          className={urgencyTone}
        >
          <p>
            {answer.triage.policy_action ||
              copy("chat.answerCanvas.urgency.empty")}
          </p>
        </CanvasSection>

        <CanvasSection
          icon="checklist"
          title={copy("chat.answerCanvas.nextActions.title")}
        >
          {answer.next_actions.length ? (
            <ol className="space-y-1.5">
              {answer.next_actions.map((item, index) => (
                <li key={`${item.action}-${index}`} className="flex gap-2">
                  <span className="font-semibold text-[var(--text-brand)]">
                    {index + 1}.
                  </span>
                  <span>{item.action}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p>
              {copy("chat.answerCanvas.nextActions.empty")}
            </p>
          )}
        </CanvasSection>

        <CanvasSection
          icon="verified"
          title={copy("chat.answerCanvas.evidence.title")}
        >
          <div className="mb-2 flex flex-wrap gap-1.5">
            <Metric
              label={copy("chat.answerCanvas.evidence.sources")}
              value={String(answer.provenance.evidence_count)}
            />
            <Metric
              label={copy("chat.answerCanvas.evidence.support")}
              value={answer.claim_support.status.replaceAll("_", " ")}
            />
          </div>
          {answer.evidence_ledger.length ? (
            <details>
              <summary className="cursor-pointer font-semibold text-[var(--text-brand)]">
                {copy("chat.answerCanvas.evidence.inspectLedger")}
              </summary>
              <ol className="mt-2 space-y-2">
                {answer.evidence_ledger.map((item) => (
                  <li key={item.evidence_id}>
                    <strong>{item.evidence_id}</strong>{" "}
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--text-brand)] hover:underline"
                      >
                        {item.title || item.source || item.url}
                      </a>
                    ) : (
                      item.title || item.source || "—"
                    )}
                    {typeof item.trust_tier === "number" ? (
                      <span className="text-[var(--text-muted)]">
                        {" "}
                        · {copy("chat.answerCanvas.evidence.trustTier", {
                          tier: item.trust_tier,
                        })}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <p className="text-[var(--status-warn-text)]">
              {copy("chat.answerCanvas.evidence.empty")}
            </p>
          )}
        </CanvasSection>

        <CanvasSection
          icon="uncertainty"
          title={copy("chat.answerCanvas.uncertainty.title")}
        >
          <Metric
            label={copy("chat.answerCanvas.uncertainty.label")}
            value={answer.uncertainty.level.replaceAll("_", " ")}
          />
          {answer.uncertainty.reasons.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-4">
              {answer.uncertainty.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {answer.missing_information.length ? (
            <details className="mt-2">
              <summary className="cursor-pointer font-semibold text-[var(--text-brand)]">
                {copy("chat.answerCanvas.uncertainty.missingCount", {
                  count: answer.missing_information.length,
                })}
              </summary>
              <ul className="mt-2 list-disc space-y-1 pl-4">
                {answer.missing_information.map((item) => (
                  <li key={item.field}>
                    <strong>{item.field}</strong> — {item.why_it_matters}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </CanvasSection>

        <CanvasSection
          icon="medication"
          title={copy("chat.answerCanvas.medicineSafety.title")}
          className="md:col-span-2"
        >
          <p>
            {copy("chat.answerCanvas.medicineSafety.description")}
          </p>
        </CanvasSection>
      </div>
    </section>
  );
}

const CANVAS_SECTION_ICONS: Record<string, IconName> = {
  emergency_home: "emergency",
  checklist: "clinical-notes",
  verified: "check",
  uncertainty: "help",
  medication: "medication",
};

function CanvasSection({
  icon,
  title,
  className = "",
  children,
}: {
  icon: string;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 ${className}`}
    >
      <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-primary)]">
        <Icon
          name={CANVAS_SECTION_ICONS[icon] ?? "clinical-notes"}
          size={16}
          className="text-[var(--text-brand)]"
          aria-hidden="true"
        />
        {title}
      </h3>
      <div className="text-xs leading-5 text-[var(--text-secondary)]">
        {children}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)]">
      {value} {label}
    </span>
  );
}
