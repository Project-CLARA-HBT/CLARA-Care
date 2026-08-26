"use client";

import { useState } from "react";
import Button from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { grantSocialConsent } from "@/lib/social";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface ConsentGateModalProps {
  open: boolean;
  onClose: () => void;
  onConsentGranted: () => void;
}

export function ConsentGateModal({
  open,
  onClose,
  onConsentGranted,
}: ConsentGateModalProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAgree = async () => {
    setLoading(true);
    setError(null);
    try {
      await grantSocialConsent();
      onConsentGranted();
      onClose();
    } catch {
      setError(copy("community.consentError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={copy("community.consent.title")}
      description={copy("community.consent.description")}
      size="md"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={loading}>
            {copy("community.compose.cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleAgree}
            loading={loading}
            disabled={loading}
          >
            {copy("community.consent.action")}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-xs leading-relaxed text-[var(--text-secondary)]">
        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30">
          <div className="p-2 rounded-lg bg-[var(--brand-600)] text-white shrink-0">
            <Icon name="contact" size="1.2rem" />
          </div>
          <div className="space-y-1">
            <p className="font-bold text-sm text-[var(--text-primary)]">
              {isEn ? "Healthy Peer Community Standards" : "Quy tắc văn hóa Cộng đồng Sức khỏe"}
            </p>
            <p className="text-[11px] text-[var(--text-secondary)]">
              {isEn
                ? "CLARA Community is built on mutual empathy, medical safety, and zero-PII privacy protection."
                : "Cộng đồng CLARA được xây dựng trên tinh thần đồng cảm, an toàn y tế và bảo vệ dữ liệu riêng tư Zero-PII."}
            </p>
          </div>
        </div>

        <ul className="space-y-2 pl-1">
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.95rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>
              <strong>{isEn ? "Zero-PII Isolation:" : "Cách ly dữ liệu bệnh án:"}</strong>{" "}
              {isEn
                ? "Your electronic health records and consultations are never linked to community posts."
                : "Hồ sơ bệnh án và lịch sử tư vấn riêng tư không bao giờ bị liên kết vào bài viết cộng đồng."}
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="warning" size="0.95rem" className="text-[var(--status-warn-text)] shrink-0 mt-0.5" />
            <span>
              <strong>{isEn ? "No Clinical Prescriptions:" : "Không kê đơn thuốc & liều dùng:"}</strong>{" "}
              {isEn
                ? "Peer experience only. Do not prescribe dosages or substitute for licensed medical care."
                : "Chỉ chia sẻ kinh nghiệm cá nhân. Tuyệt đối không kê đơn thuốc hay chỉ định liều dùng cho người khác."}
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.95rem" className="text-[var(--text-brand)] shrink-0 mt-0.5" />
            <span>
              <strong>{isEn ? "AI Safety Guardrails:" : "Kiểm duyệt an toàn AI:"}</strong>{" "}
              {isEn
                ? "All public posts and comments are screened automatically to prevent misinformation."
                : "Toàn bộ bài viết và bình luận được kiểm duyệt tự động để ngăn chặn thông tin sai lệch."}
            </span>
          </li>
        </ul>

        {error ? (
          <p className="text-xs font-semibold text-[var(--status-danger-text)] rounded-lg bg-[var(--status-danger-bg)] p-2.5 border border-[color:var(--status-danger-border)]">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

export default ConsentGateModal;
