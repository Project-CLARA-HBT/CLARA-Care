"use client";

import Button from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface PrivacyModalProps {
  open: boolean;
  onClose: () => void;
}

export function PrivacyModal({ open, onClose }: PrivacyModalProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        isEn
          ? "Community Privacy & Moderation Policy"
          : "Chính sách kiểm duyệt & Quyền riêng tư"
      }
      size="md"
      footer={
        <Button variant="primary" size="sm" onClick={onClose}>
          {copy("community.dialog.close")}
        </Button>
      }
    >
      <div className="space-y-3.5 text-xs leading-relaxed text-[var(--text-secondary)]">
        <div className="space-y-1">
          <p className="font-bold text-sm text-[var(--text-primary)]">
            {isEn ? "Zero-PII Isolation Standard" : "Tiêu chuẩn cách ly Zero-PII"}
          </p>
          <p>
            {isEn
              ? "Your personal health records (PHR), medication cabinet, and private clinical consultations are completely isolated from your community profile. Community posts and comments contain zero health records unless explicitly shared by you in text."
              : "Hồ sơ sức khỏe cá nhân (PHR), tủ thuốc và các cuộc trò chuyện tư vấn của bạn được cách ly hoàn toàn khỏi tài khoản cộng đồng. Dữ liệu y tế riêng tư không bao giờ bị liên kết tự động."}
          </p>
        </div>

        <div className="space-y-1 pt-1">
          <p className="font-bold text-sm text-[var(--text-primary)]">
            {isEn ? "Automated ML Safety Gate" : "Kiểm duyệt an toàn tự động (ML)"}
          </p>
          <p>
            {isEn
              ? "Every post and comment is screened by the CLARA Safety Engine (ML POST /v1/social/moderate) before publishing. Content containing prohibited medical prescriptions, clinical diagnosis, dosage instructions, or private personal data fails closed and cannot be published."
              : "Toàn bộ bài viết và bình luận đều được rà soát qua cổng kiểm duyệt an toàn của CLARA trước khi xuất bản. Nội dung vi phạm quy định kê đơn, chẩn đoán thay bác sĩ hoặc chứa thông tin cá nhân nhạy cảm sẽ bị chặn xuất bản."}
          </p>
        </div>

        <div className="space-y-1 pt-1">
          <p className="font-bold text-sm text-[var(--text-primary)]">
            {isEn ? "Emergency Fast-Path" : "Phát hiện khẩn cấp y tế"}
          </p>
          <p>
            {isEn
              ? "If a submission contains indicators of acute emergency symptoms, the system immediately returns an emergency escalation alert directing the user to call 115 rather than publishing it as community discussion."
              : "Nếu nội dung có dấu hiệu tình huống cấp cứu nguy kịch, hệ thống sẽ cảnh báo hướng dẫn liên hệ ngay đường dây nóng 115 thay vì hiển thị như một cuộc thảo luận thông thường."}
          </p>
        </div>
      </div>
    </Modal>
  );
}

export default PrivacyModal;
