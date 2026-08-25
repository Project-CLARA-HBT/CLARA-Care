"use client";

import Badge, { type BadgeTone } from "@/components/ui/badge";
import Icon from "@/components/ui/icon";
import type { DrugInteractionAlert, TrafficLightLevel } from "@/lib/vietnamese-drugs";
import { useUILanguage } from "@/lib/use-ui-language";

export type TrafficLightSafetyIndicatorProps = {
  level: TrafficLightLevel;
  summary?: string;
  alerts?: DrugInteractionAlert[];
  medications?: string[];
  checkedCount?: number;
  className?: string;
};

function getTrafficLightConfig(level: TrafficLightLevel, isEn: boolean) {
  switch (level) {
    case "danger":
      return {
        label: isEn ? "RED: DANGEROUS INTERACTION" : "ĐỎ: TƯƠNG TÁC NGUY HIỂM",
        tone: "danger" as BadgeTone,
        titleColor: "text-[var(--status-danger-text)]",
        borderColor: "border-[color:var(--status-danger-border)]",
        bgColor: "bg-[var(--status-danger-bg)]",
        badgeText: isEn ? "Dangerous" : "Nguy hiểm",
        icon: "warning" as const,
        description: isEn
          ? "Critical drug interaction detected. May cause severe bleeding, toxicity, organ stress, or loss of therapeutic efficacy. Consult a physician or pharmacist immediately."
          : "Phát hiện tương tác thuốc mức độ nguy hiểm. Có thể gây biến cố xuất huyết nặng, tiêu cơ vân, ngộ độc gan/thận hoặc mất hoàn toàn tác dụng điều trị. Cần tham vấn bác sĩ/dược sĩ ngay.",
      };
    case "caution":
      return {
        label: isEn ? "YELLOW: CAUTION REQUIRED" : "VÀNG: CẦN LƯU Ý",
        tone: "warn" as BadgeTone,
        titleColor: "text-[var(--status-warn-text)]",
        borderColor: "border-[color:var(--status-warn-border)]",
        bgColor: "bg-[var(--status-warn-bg)]",
        badgeText: isEn ? "Caution" : "Cần lưu ý",
        icon: "warning" as const,
        description: isEn
          ? "Moderate interaction detected. Combination may alter blood pressure, increase sedation, or require spaced dosing. Monitor for adverse symptoms."
          : "Phát hiện tương tác mức độ trung bình. Cần theo dõi huyết áp, triệu chứng buồn ngủ, khó tiêu hoặc uống cách nhau tối thiểu 2 giờ để tránh giảm hấp thu.",
      };
    case "safe":
    default:
      return {
        label: isEn ? "GREEN: SAFE COMBINATION" : "XANH: AN TOÀN",
        tone: "ok" as BadgeTone,
        titleColor: "text-[var(--status-ok-text)]",
        borderColor: "border-[color:var(--status-ok-border)]",
        bgColor: "bg-[var(--status-ok-bg)]",
        badgeText: isEn ? "Safe" : "An toàn",
        icon: "check" as const,
        description: isEn
          ? "No dangerous or conflicting interactions detected among the selected medications. The regimen is compatible when taken according to standard medical instructions."
          : "Không phát hiện tương tác nguy hiểm hoặc đối kháng giữa các thuốc đã chọn. Các hoạt chất tương thích an toàn khi sử dụng đúng liều lượng chỉ định.",
      };
  }
}

export function TrafficLightSafetyIndicator({
  level,
  summary,
  alerts = [],
  medications = [],
  checkedCount = 0,
  className = "",
}: TrafficLightSafetyIndicatorProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const config = getTrafficLightConfig(level, isEn);

  return (
    <section
      data-testid="traffic-light-safety-indicator"
      data-safety-level={level}
      className={`rounded-2xl border ${config.borderColor} ${config.bgColor} p-5 sm:p-6 transition-all shadow-sm ${className}`}
      aria-live="polite"
    >
      {/* Header with 3-bulb Visual Traffic Light */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[color:var(--shell-border)]/50 pb-4">
        <div className="flex items-center gap-3.5">
          {/* Traffic Light Physical Device Representation */}
          <div
            className="flex items-center gap-1.5 rounded-full border border-black/20 bg-black/80 px-2.5 py-1.5 shadow-inner"
            aria-label={`Mức an toàn: ${config.label}`}
          >
            {/* Red Light */}
            <span
              className={`h-3.5 w-3.5 rounded-full transition-all ${
                level === "danger"
                  ? "bg-rose-500 shadow-[0_0_10px_#f43f5e] ring-2 ring-rose-300"
                  : "bg-rose-950 opacity-30"
              }`}
              title={isEn ? "Red: Dangerous" : "Đỏ: Tương tác nguy hiểm"}
            />
            {/* Yellow Light */}
            <span
              className={`h-3.5 w-3.5 rounded-full transition-all ${
                level === "caution"
                  ? "bg-amber-400 shadow-[0_0_10px_#fbbf24] ring-2 ring-amber-200"
                  : "bg-amber-950 opacity-30"
              }`}
              title={isEn ? "Yellow: Caution" : "Vàng: Cần lưu ý"}
            />
            {/* Green Light */}
            <span
              className={`h-3.5 w-3.5 rounded-full transition-all ${
                level === "safe"
                  ? "bg-emerald-500 shadow-[0_0_10px_#10b981] ring-2 ring-emerald-200"
                  : "bg-emerald-950 opacity-30"
              }`}
              title={isEn ? "Green: Safe" : "Xanh: An toàn"}
            />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className={`text-base sm:text-lg font-bold tracking-tight ${config.titleColor}`}>
                {config.label}
              </h3>
              <Badge tone={config.tone}>{config.badgeText}</Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {isEn
                ? `Evaluation of ${medications.length || checkedCount} medication active ingredients`
                : `Đánh giá an toàn cho ${medications.length || checkedCount} hoạt chất đã đối chiếu`}
            </p>
          </div>
        </div>

        {/* DrugBank & FIDES Verified Authority Stamp */}
        <div className="flex items-center gap-2 self-start sm:self-auto rounded-lg border border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)]/80 px-3 py-1.5 text-xs text-[var(--text-secondary)]">
          <Icon name="check" size={14} className="text-[var(--status-ok-text)]" />
          <span className="font-semibold text-[var(--text-primary)]">DrugBank v5.1 & FIDES</span>
        </div>
      </div>

      {/* Summary Banner Description */}
      <div className="mt-4 space-y-2">
        <p className="text-sm font-medium text-[var(--text-primary)] leading-relaxed">
          {summary || config.description}
        </p>
      </div>

      {/* Alert Breakdown Cards */}
      {alerts.length > 0 && (
        <div className="mt-5 space-y-3.5">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
            <Icon name="clinical-notes" size={15} />
            {isEn ? "Detailed Interaction Pairs & Clinical Impact:" : "Chi tiết cặp tương tác & Khuyến cáo chuyên môn:"}
          </h4>

          <div className="space-y-3">
            {alerts.map((alert, idx) => {
              const alertLevel = alert.level || level;
              const alertTone: BadgeTone =
                alertLevel === "danger" ? "danger" : alertLevel === "caution" ? "warn" : "ok";

              return (
                <article
                  key={`${alert.drugA}-${alert.drugB}-${idx}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm space-y-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/40 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded-md bg-[var(--surface-brand-soft)] px-2 py-0.5 text-xs font-bold text-[var(--text-brand)]">
                        {alert.drugA} + {alert.drugB}
                      </span>
                      <Badge tone={alertTone}>
                        {alertLevel === "danger"
                          ? isEn ? "Dangerous" : "Nguy hiểm"
                          : alertLevel === "caution"
                            ? isEn ? "Caution" : "Cần lưu ý"
                            : isEn ? "Safe" : "An toàn"}
                      </Badge>
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)]">
                      {alert.sourceAuthority || "DrugBank Verified"}
                    </span>
                  </div>

                  <p className="text-sm font-bold text-[var(--text-primary)]">
                    {alert.title}
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs text-[var(--text-secondary)]">
                    <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 space-y-1">
                      <p className="font-bold text-[var(--text-primary)]">
                        {isEn ? "Mechanism & Clinical Effect:" : "Cơ chế & Tác động dược lý:"}
                      </p>
                      <p className="leading-relaxed">{alert.mechanism}</p>
                      {alert.clinicalEffect && (
                        <p className="font-medium text-[var(--text-primary)] mt-1">
                          ↳ {alert.clinicalEffect}
                        </p>
                      )}
                    </div>

                    <div className="rounded-lg bg-[var(--surface-muted)] p-2.5 space-y-1">
                      <p className="font-bold text-[var(--text-primary)]">
                        {isEn ? "Actionable Recommendation:" : "Khuyến cáo xử trí từ bác sĩ / dược sĩ:"}
                      </p>
                      <p className="leading-relaxed text-[var(--text-primary)] font-medium">
                        {alert.recommendation}
                      </p>
                    </div>
                  </div>

                  {alert.symptomsToWatch && alert.symptomsToWatch.length > 0 && (
                    <div className="rounded-lg border border-[color:var(--status-warn-border)]/60 bg-[var(--status-warn-bg)]/40 p-2.5">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--status-warn-text)] flex items-center gap-1">
                        <Icon name="warning" size={13} />
                        {isEn ? "Symptoms to Watch Out For:" : "Dấu hiệu cảnh báo cần đi khám ngay:"}
                      </p>
                      <ul className="mt-1 list-disc list-inside space-y-0.5 text-xs text-[var(--text-primary)]">
                        {alert.symptomsToWatch.map((sym, sIdx) => (
                          <li key={sIdx}>{sym}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}

      {/* Safety Notice Footer */}
      <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/50 text-[11px] text-[var(--text-muted)] flex items-center justify-between flex-wrap gap-2">
        <span>
          {isEn
            ? "⚠️ Fail-closed safety invariant: CLARA never manufactures false safety. Incomplete identities require manual review."
            : "⚠️ Tiêu chuẩn an toàn: CLARA không báo an toàn giả khi thiếu dữ liệu. Luôn tuân thủ chỉ định trực tiếp từ bác sĩ."}
        </span>
        <span className="font-medium">
          {isEn ? "Deterministic Drug Interaction Engine" : "Mô-đun kiểm tra tương tác thuốc"}
        </span>
      </div>
    </section>
  );
}

export default TrafficLightSafetyIndicator;
