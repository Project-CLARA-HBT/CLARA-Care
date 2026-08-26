"use client";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface SafetyBannerProps {
  onOpenPrivacyPolicy: () => void;
}

export function SafetyBanner({ onOpenPrivacyPolicy }: SafetyBannerProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  return (
    <section
      aria-labelledby="community-safety-banner-heading"
      className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/60 p-4 sm:p-5 space-y-2 transition shadow-sm"
    >
      <div className="flex items-start gap-3.5">
        <div className="rounded-xl bg-[var(--status-warn-bg)] p-2.5 text-[var(--status-warn-text)] shrink-0 border border-[color:var(--status-warn-border)] shadow-xs">
          <Icon name="warning" size="1.25rem" />
        </div>
        <div className="space-y-1.5 flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2
              id="community-safety-banner-heading"
              className="text-sm font-bold text-[var(--text-primary)] flex flex-wrap items-center gap-2"
            >
              <span>
                {isEn ? "Medical Safety & Peer Sharing Notice" : "Lưu ý an toàn y tế & Chia sẻ đồng cấp"}
              </span>
            </h2>
            <Badge tone="ok" icon="check" className="text-[10px] py-0.5 font-semibold">
              {isEn ? "Pre-publish AI Screening Active" : "Đã kích hoạt kiểm duyệt AI"}
            </Badge>
          </div>
          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
            {copy("community.disclaimer")}
          </p>
          <div className="pt-1 flex flex-wrap items-center gap-4 text-xs">
            <button
              type="button"
              onClick={onOpenPrivacyPolicy}
              className="font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1.5 cursor-pointer transition focus:outline-none"
            >
              <Icon name="help" size="0.9rem" />
              <span>
                {isEn
                  ? "Zero-PII Isolation & Moderation Policy"
                  : "Chính sách bảo mật Zero-PII & Kiểm duyệt"}
              </span>
            </button>
            <span className="text-[11px] text-[var(--text-muted)] flex items-center gap-1">
              <Icon name="emergency" size="0.85rem" className="text-[var(--status-danger-text)]" />
              <span>{isEn ? "Emergency Hotline: 115" : "Cấp cứu khẩn cấp: 115"}</span>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

export default SafetyBanner;
