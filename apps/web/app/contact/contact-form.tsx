"use client";

import { useState, useId } from "react";
import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

export type ContactCategory =
  | "patient"
  | "clinician"
  | "research"
  | "dpo"
  | "feedback";

export interface ContactFormValues {
  category: ContactCategory;
  name: string;
  email: string;
  phone: string;
  role: string;
  subject: string;
  message: string;
  consent: boolean;
}

export interface CategoryMeta {
  value: ContactCategory;
  label: string;
  channelName: string;
  sla: string;
  badgeTone: BadgeTone;
  icon: IconName;
  description: string;
}

export const CATEGORY_OPTIONS: CategoryMeta[] = [
  {
    value: "patient",
    label: "Hỗ trợ người bệnh",
    channelName: "1. Hỗ trợ người bệnh & Người dùng cá nhân",
    sla: "24 giờ",
    badgeTone: "brand",
    icon: "user-card",
    description: "Tủ thuốc cá nhân, chia sẻ người thân, tài khoản & tra cứu thuốc.",
  },
  {
    value: "clinician",
    label: "Cố vấn y khoa",
    channelName: "2. Ban cố vấn y khoa & Bác sĩ lâm sàng",
    sla: "48 giờ",
    badgeTone: "ok",
    icon: "clinical-notes",
    description: "Doctor onboarding, Council review, Scribe verification & y văn.",
  },
  {
    value: "research",
    label: "Hợp tác nghiên cứu",
    channelName: "3. Hợp tác nghiên cứu & Dữ liệu y học",
    sla: "72 giờ",
    badgeTone: "warn",
    icon: "progress",
    description: "Living Evidence RAG, thử nghiệm lâm sàng & hợp tác học thuật.",
  },
  {
    value: "dpo",
    label: "Quyền riêng tư & DPO",
    channelName: "4. Cán bộ bảo vệ dữ liệu (DPO) & DSAR",
    sla: "72 giờ (theo luật)",
    badgeTone: "neutral",
    icon: "warning",
    description: "Nghị định 13/2023/NĐ-CP (DSAR), trích xuất & xóa dữ liệu y tế.",
  },
  {
    value: "feedback",
    label: "Góp ý chất lượng",
    channelName: "Góp ý & Đóng góp phản hồi chung",
    sla: "48 giờ",
    badgeTone: "neutral",
    icon: "help",
    description: "Đề xuất cải tiến trải nghiệm, báo cáo giao diện hoặc tính năng.",
  },
];

export const ROLE_OPTIONS = [
  "Người bệnh / Người dùng cá nhân",
  "Bác sĩ / Nhân viên y tế",
  "Dược sĩ / Chuyên gia dược",
  "Nhà nghiên cứu / Giảng viên y khoa",
  "Đại diện cơ sở khám chữa bệnh / Bệnh viện",
  "Cán bộ phụ trách dữ liệu / Pháp chế",
  "Khác",
] as const;

export function ContactFeedbackForm({
  initialCategory = "patient",
}: {
  initialCategory?: ContactCategory;
}) {
  const formUid = useId();

  const [formValues, setFormValues] = useState<ContactFormValues>({
    category: initialCategory,
    name: "",
    email: "",
    phone: "",
    role: ROLE_OPTIONS[0],
    subject: "",
    message: "",
    consent: true,
  });

  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [ticketId, setTicketId] = useState("");
  const [submittedAt, setSubmittedAt] = useState("");
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const selectedCategoryMeta =
    CATEGORY_OPTIONS.find((c) => c.value === formValues.category) ||
    CATEGORY_OPTIONS[0];

  const validateField = (field: keyof ContactFormValues, value: unknown): string => {
    switch (field) {
      case "name":
        if (typeof value !== "string" || !value.trim()) {
          return "Vui lòng nhập họ và tên của bạn.";
        }
        if (value.trim().length < 2) {
          return "Họ và tên cần có ít nhất 2 ký tự.";
        }
        return "";
      case "email":
        if (typeof value !== "string" || !value.trim()) {
          return "Vui lòng nhập email liên hệ.";
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())) {
          return "Địa chỉ email không hợp lệ (ví dụ: ten@domain.com).";
        }
        return "";
      case "phone":
        if (typeof value === "string" && value.trim()) {
          if (!/^[0-9+()\-.\s]{8,20}$/.test(value.trim())) {
            return "Số điện thoại không đúng định dạng.";
          }
        }
        return "";
      case "subject":
        if (typeof value !== "string" || !value.trim()) {
          return "Vui lòng nhập tiêu đề yêu cầu.";
        }
        if (value.trim().length < 4) {
          return "Tiêu đề cần có ít nhất 4 ký tự.";
        }
        return "";
      case "message":
        if (typeof value !== "string" || !value.trim()) {
          return "Vui lòng mô tả chi tiết nội dung cần hỗ trợ.";
        }
        if (value.trim().length < 10) {
          return "Nội dung cần có ít nhất 10 ký tự để được xử lý.";
        }
        return "";
      case "consent":
        if (!value) {
          return "Bạn cần đồng ý với điều khoản xử lý thông tin để tiếp tục.";
        }
        return "";
      default:
        return "";
    }
  };

  const validateAll = (): boolean => {
    const nextErrors: Record<string, string> = {};
    const fields: (keyof ContactFormValues)[] = [
      "name",
      "email",
      "phone",
      "subject",
      "message",
      "consent",
    ];

    fields.forEach((field) => {
      const err = validateField(field, formValues[field]);
      if (err) {
        nextErrors[field] = err;
      }
    });

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleBlur = (field: keyof ContactFormValues) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    const errorMsg = validateField(field, formValues[field]);
    setErrors((prev) => {
      if (errorMsg) {
        return { ...prev, [field]: errorMsg };
      }
      const updated = { ...prev };
      delete updated[field];
      return updated;
    });
  };

  const handleChange = (field: keyof ContactFormValues, value: unknown) => {
    setFormValues((prev) => ({ ...prev, [field]: value }));
    if (touched[field]) {
      const errorMsg = validateField(field, value);
      setErrors((prev) => {
        if (errorMsg) {
          return { ...prev, [field]: errorMsg };
        }
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({
      name: true,
      email: true,
      phone: true,
      subject: true,
      message: true,
      consent: true,
    });

    if (!validateAll()) return;

    setSubmitting(true);
    // Deterministic simulation adhering to Zero-PII pipeline
    setTimeout(() => {
      const currentYear = new Date().getFullYear();
      const randomHex = Math.random().toString(36).substring(2, 8).toUpperCase();
      const generatedId = `TKT-${currentYear}-${randomHex}`;
      setTicketId(generatedId);
      setSubmittedAt(
        new Date().toLocaleString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
        }),
      );
      setSubmitting(false);
      setSubmitted(true);
    }, 600);
  };

  const handleReset = () => {
    setFormValues({
      category: "patient",
      name: "",
      email: "",
      phone: "",
      role: ROLE_OPTIONS[0],
      subject: "",
      message: "",
      consent: true,
    });
    setErrors({});
    setTouched({});
    setSubmitted(false);
    setTicketId("");
    setSubmittedAt("");
    setShowReceiptModal(false);
  };

  if (submitted) {
    return (
      <div
        className="rounded-[var(--radius-2xl)] border border-[color:var(--status-ok-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm text-center"
        data-testid="contact-form-success"
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)] shadow-xs">
          <Icon name="check" size="2rem" />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-center gap-2">
            <Badge tone="ok" icon="check">
              Tiếp nhận thành công
            </Badge>
            <Badge tone="neutral" icon="folder">
              Mã hồ sơ tự động
            </Badge>
          </div>
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Cảm ơn bạn đã liên hệ với The Clara Care
          </h3>
          <p className="max-w-lg mx-auto text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
            Yêu cầu của bạn đã được chuyển an toàn tới bộ phận chuyên trách{" "}
            <strong className="text-[var(--text-primary)]">
              &ldquo;{selectedCategoryMeta.channelName}&rdquo;
            </strong>
            .
          </p>
        </div>

        <div className="mx-auto max-w-md rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-3 text-left">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
            <span className="text-xs text-[var(--text-muted)] font-medium">
              Mã tra cứu phiếu:
            </span>
            <span className="font-mono text-sm font-black text-[var(--text-brand)]">
              {ticketId}
            </span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2 text-xs">
            <span className="text-[var(--text-muted)]">Kênh tiếp nhận:</span>
            <span className="font-semibold text-[var(--text-primary)]">
              {selectedCategoryMeta.label}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--text-muted)]">Cam kết SLA:</span>
            <span className="font-semibold text-[var(--status-ok-text)]">
              {selectedCategoryMeta.sla}
            </span>
          </div>
        </div>

        <div className="space-y-1 text-xs text-[var(--text-muted)] max-w-md mx-auto leading-relaxed">
          <p>
            Chúng tôi sẽ phản hồi qua email{" "}
            <strong className="text-[var(--text-primary)]">{formValues.email}</strong>{" "}
            trong thời gian quy định theo SLA cam kết.
          </p>
          <p className="text-[11px] text-[var(--text-muted)]/80">
            Dữ liệu được lưu vết mã hóa Zero-PII và tuân thủ Nghị định 13/2023/NĐ-CP.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowReceiptModal(true)}
            data-testid="view-receipt-btn"
          >
            <Icon name="clinical-notes" size="1rem" />
            <span>Xem biên nhận chi tiết</span>
          </Button>

          <Button
            type="button"
            variant="primary"
            onClick={handleReset}
            data-testid="submit-another-btn"
          >
            <Icon name="plus" size="1rem" />
            <span>Gửi thêm yêu cầu khác</span>
          </Button>
        </div>

        {/* Modal Receipt Dialog */}
        <Modal
          open={showReceiptModal}
          onClose={() => setShowReceiptModal(false)}
          title="Biên nhận yêu cầu hỗ trợ (Support Ticket Receipt)"
          description="Thông tin chi tiết phiếu tiếp nhận đã được hệ thống tạo tự động."
          size="md"
          footer={
            <div className="flex justify-end gap-2 w-full">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowReceiptModal(false)}
              >
                <span>Đóng biên nhận</span>
              </Button>
            </div>
          }
        >
          <div className="space-y-4 text-xs">
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-2">
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Mã phiếu:</span>
                <span className="font-mono font-bold text-[var(--text-brand)]">{ticketId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Thời gian tiếp nhận:</span>
                <span className="font-medium text-[var(--text-primary)]">{submittedAt || "Vừa tiếp nhận"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Người gửi:</span>
                <span className="font-semibold text-[var(--text-primary)]">{formValues.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Email:</span>
                <span className="font-semibold text-[var(--text-primary)]">{formValues.email}</span>
              </div>
              {formValues.phone ? (
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Số điện thoại:</span>
                  <span className="font-semibold text-[var(--text-primary)]">{formValues.phone}</span>
                </div>
              ) : null}
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Vai trò:</span>
                <span className="font-semibold text-[var(--text-primary)]">{formValues.role}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Kênh tiếp nhận:</span>
                <span className="font-semibold text-[var(--text-primary)]">{selectedCategoryMeta.label}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Cam kết SLA:</span>
                <span className="font-semibold text-[var(--status-ok-text)]">{selectedCategoryMeta.sla}</span>
              </div>
            </div>

            <div className="space-y-1.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5">
              <span className="font-bold text-[var(--text-primary)] block">Tiêu đề:</span>
              <p className="font-semibold text-[var(--text-primary)]">{formValues.subject}</p>
              <span className="font-bold text-[var(--text-primary)] block pt-2">Nội dung tóm tắt:</span>
              <p className="text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed">
                {formValues.message}
              </p>
            </div>

            <div className="rounded-xl border border-[color:var(--brand-500)]/30 bg-[var(--surface-brand-soft)]/50 p-3 space-y-1 text-[11px] text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5 font-bold text-[var(--text-brand)]">
                <Icon name="check" size="0.9rem" />
                <span>Bảo mật & Thực thi DSAR</span>
              </div>
              <p>
                Phiếu hỗ trợ này được bảo vệ bởi chuẩn Zero-PII. Bạn có quyền yêu cầu tra cứu, chỉnh sửa hoặc xóa dữ liệu bất kỳ lúc nào theo Nghị định 13/2023/NĐ-CP.
              </p>
            </div>
          </div>
        </Modal>
      </div>
    );
  }

  return (
    <form
      id="feedback-form"
      onSubmit={handleSubmit}
      noValidate
      className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm transition-all"
      data-testid="contact-feedback-form"
    >
      {/* Form Header */}
      <div className="space-y-1.5 border-b border-[color:var(--shell-border)]/60 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="contact" size="1.25rem" />
            <h3 className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]">
              Biểu mẫu tiếp nhận yêu cầu & Phản hồi có cấu trúc
            </h3>
          </div>
          <Badge tone="ok" icon="check">
            Mã hóa Zero-PII
          </Badge>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          Vui lòng điền thông tin bên dưới để gửi yêu cầu đến đúng bộ phận chuyên trách. Đội ngũ The Clara Care cam kết phản hồi trong thời hạn SLA tương ứng.
        </p>
      </div>

      {/* 1. Category Selector matching 4 channels + feedback */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            1. Kênh tiếp nhận / Nhóm vấn đề <span className="text-[var(--status-danger-text)]">*</span>
          </label>
          <span className="text-[11px] font-semibold text-[var(--status-ok-text)]">
            SLA: {selectedCategoryMeta.sla}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {CATEGORY_OPTIONS.map((cat) => {
            const isSelected = formValues.category === cat.value;
            return (
              <button
                key={cat.value}
                type="button"
                onClick={() => handleChange("category", cat.value)}
                className={[
                  "flex items-start gap-3 rounded-xl border p-3 text-left transition-all text-xs cursor-pointer",
                  isSelected
                    ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-primary)] font-bold shadow-xs ring-1 ring-[color:var(--brand-500)]/40"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                <div
                  className={[
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                    isSelected
                      ? "bg-[var(--surface-panel)] text-[var(--text-brand)] border-[color:var(--brand-500)]/30"
                      : "bg-[var(--surface-panel)] text-[var(--text-muted)] border-[color:var(--shell-border)]",
                  ].join(" ")}
                >
                  <Icon name={cat.icon} size="1.1rem" />
                </div>
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold leading-tight line-clamp-1">
                      {cat.label}
                    </span>
                  </div>
                  <p className="text-[11px] font-normal text-[var(--text-muted)] line-clamp-2 leading-tight">
                    {cat.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Sender Details Grid */}
      <div className="space-y-3">
        <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
          2. Thông tin người gửi
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Full Name */}
          <div className="space-y-1.5">
            <label
              htmlFor={`${formUid}-name`}
              className="block text-xs font-bold text-[var(--text-primary)]"
            >
              Họ và tên <span className="text-[var(--status-danger-text)]">*</span>
            </label>
            <input
              id={`${formUid}-name`}
              name="name"
              type="text"
              required
              placeholder="Nguyễn Văn A"
              value={formValues.name}
              onBlur={() => handleBlur("name")}
              onChange={(e) => handleChange("name", e.target.value)}
              className={[
                "w-full rounded-xl border bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:outline-none focus:ring-1",
                errors.name
                  ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)] focus:ring-[color:var(--status-danger-border)]"
                  : "border-[color:var(--shell-border)] focus:border-[color:var(--brand-500)] focus:ring-[color:var(--brand-500)]",
              ].join(" ")}
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? `${formUid}-name-error` : undefined}
            />
            {errors.name ? (
              <p
                id={`${formUid}-name-error`}
                className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1"
              >
                <Icon name="warning" size="0.75rem" />
                <span>{errors.name}</span>
              </p>
            ) : null}
          </div>

          {/* Email */}
          <div className="space-y-1.5">
            <label
              htmlFor={`${formUid}-email`}
              className="block text-xs font-bold text-[var(--text-primary)]"
            >
              Email liên hệ <span className="text-[var(--status-danger-text)]">*</span>
            </label>
            <input
              id={`${formUid}-email`}
              name="email"
              type="email"
              required
              placeholder="email@example.com"
              value={formValues.email}
              onBlur={() => handleBlur("email")}
              onChange={(e) => handleChange("email", e.target.value)}
              className={[
                "w-full rounded-xl border bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:outline-none focus:ring-1",
                errors.email
                  ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)] focus:ring-[color:var(--status-danger-border)]"
                  : "border-[color:var(--shell-border)] focus:border-[color:var(--brand-500)] focus:ring-[color:var(--brand-500)]",
              ].join(" ")}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? `${formUid}-email-error` : undefined}
            />
            {errors.email ? (
              <p
                id={`${formUid}-email-error`}
                className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1"
              >
                <Icon name="warning" size="0.75rem" />
                <span>{errors.email}</span>
              </p>
            ) : null}
          </div>

          {/* Phone */}
          <div className="space-y-1.5">
            <label
              htmlFor={`${formUid}-phone`}
              className="block text-xs font-bold text-[var(--text-primary)]"
            >
              Số điện thoại (tùy chọn)
            </label>
            <input
              id={`${formUid}-phone`}
              name="phone"
              type="tel"
              placeholder="+84 9xx xxx xxx"
              value={formValues.phone}
              onBlur={() => handleBlur("phone")}
              onChange={(e) => handleChange("phone", e.target.value)}
              className={[
                "w-full rounded-xl border bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:outline-none focus:ring-1",
                errors.phone
                  ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)] focus:ring-[color:var(--status-danger-border)]"
                  : "border-[color:var(--shell-border)] focus:border-[color:var(--brand-500)] focus:ring-[color:var(--brand-500)]",
              ].join(" ")}
              aria-invalid={Boolean(errors.phone)}
              aria-describedby={errors.phone ? `${formUid}-phone-error` : undefined}
            />
            {errors.phone ? (
              <p
                id={`${formUid}-phone-error`}
                className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1"
              >
                <Icon name="warning" size="0.75rem" />
                <span>{errors.phone}</span>
              </p>
            ) : null}
          </div>

          {/* Role */}
          <div className="space-y-1.5">
            <label
              htmlFor={`${formUid}-role`}
              className="block text-xs font-bold text-[var(--text-primary)]"
            >
              Vai trò của bạn
            </label>
            <select
              id={`${formUid}-role`}
              name="role"
              value={formValues.role}
              onChange={(e) => handleChange("role", e.target.value)}
              className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
            >
              {ROLE_OPTIONS.map((opt) => (
                <option
                  key={opt}
                  value={opt}
                  className="bg-[var(--surface-panel)] text-[var(--text-primary)]"
                >
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 3. Subject and Message */}
      <div className="space-y-3">
        <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
          3. Nội dung yêu cầu
        </label>

        {/* Subject */}
        <div className="space-y-1.5">
          <label
            htmlFor={`${formUid}-subject`}
            className="block text-xs font-bold text-[var(--text-primary)]"
          >
            Tiêu đề yêu cầu <span className="text-[var(--status-danger-text)]">*</span>
          </label>
          <input
            id={`${formUid}-subject`}
            name="subject"
            type="text"
            required
            placeholder="Tóm tắt ngắn gọn vấn đề cần hỗ trợ hoặc đề xuất..."
            value={formValues.subject}
            onBlur={() => handleBlur("subject")}
            onChange={(e) => handleChange("subject", e.target.value)}
            className={[
              "w-full rounded-xl border bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:outline-none focus:ring-1",
              errors.subject
                ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)] focus:ring-[color:var(--status-danger-border)]"
                : "border-[color:var(--shell-border)] focus:border-[color:var(--brand-500)] focus:ring-[color:var(--brand-500)]",
            ].join(" ")}
            aria-invalid={Boolean(errors.subject)}
            aria-describedby={errors.subject ? `${formUid}-subject-error` : undefined}
          />
          {errors.subject ? (
            <p
              id={`${formUid}-subject-error`}
              className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1"
            >
              <Icon name="warning" size="0.75rem" />
              <span>{errors.subject}</span>
            </p>
          ) : null}
        </div>

        {/* Message */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor={`${formUid}-message`}
              className="block text-xs font-bold text-[var(--text-primary)]"
            >
              Nội dung chi tiết <span className="text-[var(--status-danger-text)]">*</span>
            </label>
            <span className="text-[11px] text-[var(--text-muted)]">
              {formValues.message.length} ký tự (tối thiểu 10)
            </span>
          </div>
          <textarea
            id={`${formUid}-message`}
            name="message"
            rows={5}
            required
            placeholder="Mô tả cụ thể câu hỏi, phản ánh sự cố kỹ thuật, đăng ký bác sĩ hoặc đề xuất hợp tác nghiên cứu y khoa của bạn..."
            value={formValues.message}
            onBlur={() => handleBlur("message")}
            onChange={(e) => handleChange("message", e.target.value)}
            className={[
              "w-full rounded-xl border bg-[var(--surface-muted)]/50 p-3.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:outline-none focus:ring-1 leading-relaxed",
              errors.message
                ? "border-[color:var(--status-danger-border)] focus:border-[color:var(--status-danger-border)] focus:ring-[color:var(--status-danger-border)]"
                : "border-[color:var(--shell-border)] focus:border-[color:var(--brand-500)] focus:ring-[color:var(--brand-500)]",
            ].join(" ")}
            aria-invalid={Boolean(errors.message)}
            aria-describedby={errors.message ? `${formUid}-message-error` : undefined}
          />
          {errors.message ? (
            <p
              id={`${formUid}-message-error`}
              className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1"
            >
              <Icon name="warning" size="0.75rem" />
              <span>{errors.message}</span>
            </p>
          ) : null}
        </div>
      </div>

      {/* 4. Consent Checkbox */}
      <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/30 p-3.5">
        <label
          htmlFor={`${formUid}-consent`}
          className="flex items-start gap-2.5 text-xs text-[var(--text-secondary)] cursor-pointer select-none"
        >
          <input
            id={`${formUid}-consent`}
            name="consent"
            type="checkbox"
            checked={formValues.consent}
            onChange={(e) => handleChange("consent", e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-[color:var(--shell-border)] text-[var(--brand-500)] focus:ring-[color:var(--brand-500)]"
          />
          <span className="leading-relaxed">
            Tôi đồng ý cho phép <strong>The Clara Care</strong> tiếp nhận và xử lý thông tin trên để giải quyết yêu cầu, tuân thủ{" "}
            <Link
              href="/legal/privacy"
              className="text-[var(--text-brand)] underline hover:text-[var(--brand-600)]"
              target="_blank"
            >
              Chính sách Quyền riêng tư
            </Link>{" "}
            và tiêu chuẩn <strong>Zero-PII</strong> theo Nghị định 13/2023/NĐ-CP.
          </span>
        </label>
        {errors.consent ? (
          <p className="text-[11px] text-[var(--status-danger-text)] font-semibold flex items-center gap-1 pl-6">
            <Icon name="warning" size="0.75rem" />
            <span>{errors.consent}</span>
          </p>
        ) : null}
      </div>

      {/* Footer & Submit */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-[color:var(--shell-border)]/50">
        <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
          <Icon name="clinical-notes" size="0.95rem" />
          <span>
            Cam kết phản hồi theo SLA: <strong>{selectedCategoryMeta.sla}</strong> làm việc.
          </span>
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={submitting}
          className="w-full sm:w-auto"
          data-testid="contact-submit-btn"
        >
          <Icon
            name={submitting ? "progress" : "send"}
            size="1rem"
            className={submitting ? "animate-spin" : ""}
          />
          <span>{submitting ? "Đang gửi yêu cầu..." : "Gửi yêu cầu hỗ trợ"}</span>
        </Button>
      </div>
    </form>
  );
}

export default ContactFeedbackForm;
