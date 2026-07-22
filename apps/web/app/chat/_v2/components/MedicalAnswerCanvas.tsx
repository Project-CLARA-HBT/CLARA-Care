import type { UserRole } from "@/lib/auth-store";
import type { ClinicalAnswerPackage } from "@/lib/chat";
import type { UILanguage } from "@/lib/ui-language";
import type { ReactNode } from "react";

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
  const isEn = uiLanguage === "en";
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
      aria-label={isEn ? "Medical answer canvas" : "Bảng câu trả lời y khoa"}
    >
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-[color:var(--shell-border)] px-3.5 py-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-brand)]">
            {isClinical
              ? isEn
                ? "Clinical decision canvas"
                : "Bảng hỗ trợ quyết định lâm sàng"
              : isEn
                ? "Your health action plan"
                : "Kế hoạch sức khỏe của bạn"}
          </p>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">
            {isEn
              ? "Urgency, actions, evidence and uncertainty—kept separate."
              : "Tách rõ mức khẩn cấp, hành động, bằng chứng và độ bất định."}
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
          title={isEn ? "Urgency" : "Mức khẩn cấp"}
          className={urgencyTone}
        >
          <p>
            {answer.triage.policy_action ||
              (isEn
                ? "No escalation instruction returned."
                : "Chưa có hướng dẫn chuyển tuyến.")}
          </p>
        </CanvasSection>

        <CanvasSection
          icon="checklist"
          title={isEn ? "What to do next" : "Việc nên làm tiếp theo"}
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
              {isEn
                ? "No specific action was returned."
                : "Chưa có hành động cụ thể."}
            </p>
          )}
        </CanvasSection>

        <CanvasSection
          icon="verified"
          title={isEn ? "Evidence behind this" : "Bằng chứng hỗ trợ"}
        >
          <div className="mb-2 flex flex-wrap gap-1.5">
            <Metric
              label={isEn ? "sources" : "nguồn"}
              value={String(answer.provenance.evidence_count)}
            />
            <Metric
              label={isEn ? "support" : "hỗ trợ"}
              value={answer.claim_support.status.replaceAll("_", " ")}
            />
          </div>
          {answer.evidence_ledger.length ? (
            <details>
              <summary className="cursor-pointer font-semibold text-[var(--text-brand)]">
                {isEn ? "Inspect evidence ledger" : "Xem sổ bằng chứng"}
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
                        · Tier {item.trust_tier}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <p className="text-[var(--status-warn-text)]">
              {isEn
                ? "No retrievable evidence; do not treat this as decision-ready."
                : "Không có bằng chứng truy xuất được; chưa thể dùng để ra quyết định."}
            </p>
          )}
        </CanvasSection>

        <CanvasSection
          icon="uncertainty"
          title={
            isEn
              ? "Uncertainty & missing context"
              : "Độ bất định & dữ kiện còn thiếu"
          }
        >
          <Metric
            label={isEn ? "uncertainty" : "bất định"}
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
                {isEn
                  ? `${answer.missing_information.length} details to add`
                  : `${answer.missing_information.length} dữ kiện cần bổ sung`}
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
          title={isEn ? "Medicine safety" : "An toàn thuốc"}
          className="md:col-span-2"
        >
          <p>
            {isEn
              ? "This answer is not a medication reconciliation or interaction screen. Include every medicine, supplement, dose and allergy before acting; do not start or stop prescriptions without a clinician or pharmacist."
              : "Câu trả lời này không thay thế đối chiếu thuốc hoặc kiểm tra tương tác. Hãy cung cấp đủ thuốc, thực phẩm bổ sung, liều và dị ứng; không tự bắt đầu hoặc ngừng thuốc kê đơn."}
          </p>
        </CanvasSection>
      </div>
    </section>
  );
}

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
        <span
          className="material-symbols-outlined text-[16px] text-[var(--text-brand)]"
          aria-hidden="true"
        >
          {icon}
        </span>
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
