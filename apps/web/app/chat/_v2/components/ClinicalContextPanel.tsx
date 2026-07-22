"use client";

import type { UserRole } from "@/lib/auth-store";
import type { UILanguage } from "@/lib/ui-language";
import type { ClinicalContext } from "@/app/chat/_v2/lib/clinical-context";

type ClinicalContextPanelProps = {
  context: ClinicalContext;
  onChange: (context: ClinicalContext) => void;
  role: UserRole;
  uiLanguage: UILanguage;
};

export default function ClinicalContextPanel({
  context,
  onChange,
  role,
  uiLanguage,
}: ClinicalContextPanelProps) {
  const isEn = uiLanguage === "en";
  const isResearcher = role === "researcher";
  const labels = isResearcher
    ? {
        person: isEn ? "Population" : "Quần thể",
        concern: isEn ? "Intervention / exposure" : "Can thiệp / phơi nhiễm",
        timeline: isEn ? "Comparator" : "Đối chứng",
        medicines: isEn ? "Study constraints" : "Giới hạn nghiên cứu",
        goal: isEn ? "Outcome" : "Kết cục",
      }
    : {
        person: isEn
          ? "Age, sex, relevant conditions"
          : "Tuổi, giới, bệnh nền liên quan",
        concern: isEn
          ? "Main symptom or concern"
          : "Triệu chứng hoặc vấn đề chính",
        timeline: isEn
          ? "When it started and how it changed"
          : "Khởi phát và diễn tiến",
        medicines: isEn
          ? "Medicines, dose, allergies"
          : "Thuốc, liều dùng, dị ứng",
        goal: isEn
          ? "What decision do you need?"
          : "Bạn cần quyết định điều gì?",
      };

  const filled = Object.values(context).filter((value) => value.trim()).length;
  return (
    <details className="group rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/65">
      <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 px-3 text-xs font-semibold text-[var(--text-primary)]">
        <span className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[17px] text-[var(--text-brand)]"
            aria-hidden="true"
          >
            clinical_notes
          </span>
          {isResearcher
            ? isEn
              ? "Frame the research question"
              : "Định hình câu hỏi nghiên cứu"
            : isEn
              ? "Add clinical context"
              : "Thêm bối cảnh y khoa"}
        </span>
        <span className="rounded-full bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">
          {filled ? `${filled}/5` : isEn ? "Optional" : "Không bắt buộc"}
        </span>
      </summary>
      <div className="grid gap-2 border-t border-[color:var(--shell-border)] p-2.5 sm:grid-cols-2">
        {(Object.keys(labels) as Array<keyof ClinicalContext>).map((field) => (
          <label
            key={field}
            className={field === "goal" ? "sm:col-span-2" : ""}
          >
            <span className="mb-1 block text-[10px] font-semibold text-[var(--text-muted)]">
              {labels[field]}
            </span>
            <input
              value={context[field]}
              onChange={(event) =>
                onChange({ ...context, [field]: event.target.value })
              }
              className="min-h-9 w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[color:var(--brand-500)]"
            />
          </label>
        ))}
        <p className="sm:col-span-2 text-[10px] leading-4 text-[var(--text-muted)]">
          {isEn
            ? "Only include details needed for this question. CLARA will mark gaps instead of inventing facts."
            : "Chỉ thêm dữ kiện cần cho câu hỏi này. CLARA sẽ đánh dấu khoảng trống thay vì tự suy đoán."}
        </p>
      </div>
    </details>
  );
}
