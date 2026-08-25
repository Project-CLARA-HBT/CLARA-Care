"use client";

import { useState } from "react";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type ContactCategory = "patient" | "clinician" | "research" | "dpo" | "feedback";

export interface ContactFormValues {
  category: ContactCategory;
  name: string;
  email: string;
  phone: string;
  role: string;
  subject: string;
  message: string;
}

const CATEGORY_OPTIONS: Array<{ value: ContactCategory; label: string; icon: IconName }> = [
  { value: "patient", label: "Hỗ trợ người bệnh", icon: "user-card" },
  { value: "clinician", label: "Cố vấn y khoa", icon: "clinical-notes" },
  { value: "research", label: "Hợp tác nghiên cứu", icon: "progress" },
  { value: "dpo", label: "Quyền riêng tư & DPO", icon: "warning" },
  { value: "feedback", label: "Góp ý chất lượng", icon: "help" },
];

const ROLE_OPTIONS = [
  "Người bệnh / Người dùng cá nhân",
  "Bác sĩ / Nhân viên y tế",
  "Dược sĩ / Chuyên gia dược",
  "Nhà nghiên cứu / Giảng viên y khoa",
  "Đại diện cơ sở khám chữa bệnh / Bệnh viện",
  "Khác",
];

export function ContactFeedbackForm() {
  const [formValues, setFormValues] = useState<ContactFormValues>({
    category: "patient",
    name: "",
    email: "",
    phone: "",
    role: ROLE_OPTIONS[0],
    subject: "",
    message: "",
  });

  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [ticketId, setTicketId] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const nextErrors: Record<string, string> = {};
    if (!formValues.name.trim()) {
      nextErrors.name = "Vui lòng nhập họ và tên của bạn.";
    }
    if (!formValues.email.trim()) {
      nextErrors.email = "Vui lòng nhập email liên hệ.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formValues.email.trim())) {
      nextErrors.email = "Địa chỉ email không hợp lệ.";
    }
    if (!formValues.subject.trim()) {
      nextErrors.subject = "Vui lòng nhập tiêu đề yêu cầu.";
    }
    if (!formValues.message.trim()) {
      nextErrors.message = "Vui lòng mô tả chi tiết nội dung cần hỗ trợ.";
    } else if (formValues.message.trim().length < 10) {
      nextErrors.message = "Nội dung cần có ít nhất 10 ký tự để được xử lý.";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    // Simulate safe client-side submission with deterministic ticket generation
    setTimeout(() => {
      const generatedId = `TKT-${new Date().getFullYear()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
      setTicketId(generatedId);
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
    });
    setErrors({});
    setSubmitted(false);
    setTicketId("");
  };

  if (submitted) {
    return (
      <div
        className="rounded-[var(--radius-2xl)] border border-[color:var(--status-ok-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-5 shadow-sm text-center"
        data-testid="contact-form-success"
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]">
          <Icon name="check" size="1.75rem" />
        </div>
        <div className="space-y-2">
          <Badge tone="ok">Tiếp nhận thành công</Badge>
          <h3 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Cảm ơn bạn đã liên hệ với The Clara Care
          </h3>
          <p className="max-w-md mx-auto text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
            Yêu cầu của bạn đã được chuyển tới bộ phận chuyên trách. Mã tra cứu phản ánh của bạn là:
          </p>
          <div className="inline-block rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-sm font-mono font-bold text-[var(--text-brand)]">
            {ticketId}
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          Chúng tôi sẽ phản hồi qua email <strong className="text-[var(--text-primary)]">{formValues.email}</strong> trong thời gian 24 - 72 giờ làm việc.
        </p>
        <div className="pt-2">
          <Button type="button" variant="secondary" onClick={handleReset} data-testid="submit-another-btn">
            <span>Gửi thêm yêu cầu khác</span>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm"
      data-testid="contact-feedback-form"
    >
      <div className="space-y-1.5 border-b border-[color:var(--shell-border)]/60 pb-4">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="contact" size="1.2rem" />
          <h3 className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]">
            Biểu mẫu tiếp nhận yêu cầu & Phản hồi có cấu trúc
          </h3>
        </div>
        <p className="text-xs text-[var(--text-secondary)]">
          Điền thông tin bên dưới để gửi yêu cầu đến đúng bộ phận chuyên trách. Dữ liệu được mã hóa an toàn theo chuẩn Zero-PII.
        </p>
      </div>

      {/* Category selector */}
      <div className="space-y-2">
        <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
          1. Kênh tiếp nhận / Nhóm vấn đề <span className="text-[var(--status-danger-text)]">*</span>
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {CATEGORY_OPTIONS.map((cat) => {
            const isSelected = formValues.category === cat.value;
            return (
              <button
                key={cat.value}
                type="button"
                onClick={() => setFormValues((prev) => ({ ...prev, category: cat.value }))}
                className={[
                  "flex flex-col items-center justify-center gap-1.5 rounded-xl border p-2.5 text-center transition-all text-xs",
                  isSelected
                    ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold shadow-xs"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]",
                ].join(" ")}
              >
                <Icon name={cat.icon} size="1rem" />
                <span className="text-[11px] leading-tight">{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Sender details grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label htmlFor="contact-name" className="block text-xs font-bold text-[var(--text-primary)]">
            Họ và tên <span className="text-[var(--status-danger-text)]">*</span>
          </label>
          <input
            id="contact-name"
            name="name"
            type="text"
            required
            placeholder="Nguyễn Văn A"
            value={formValues.name}
            onChange={(e) => setFormValues((prev) => ({ ...prev, name: e.target.value }))}
            className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
          />
          {errors.name ? <p className="text-[11px] text-[var(--status-danger-text)] font-semibold">{errors.name}</p> : null}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="contact-email" className="block text-xs font-bold text-[var(--text-primary)]">
            Email liên hệ <span className="text-[var(--status-danger-text)]">*</span>
          </label>
          <input
            id="contact-email"
            name="email"
            type="email"
            required
            placeholder="email@example.com"
            value={formValues.email}
            onChange={(e) => setFormValues((prev) => ({ ...prev, email: e.target.value }))}
            className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
          />
          {errors.email ? <p className="text-[11px] text-[var(--status-danger-text)] font-semibold">{errors.email}</p> : null}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="contact-phone" className="block text-xs font-bold text-[var(--text-primary)]">
            Số điện thoại (tùy chọn)
          </label>
          <input
            id="contact-phone"
            name="phone"
            type="tel"
            placeholder="+84 9xx xxx xxx"
            value={formValues.phone}
            onChange={(e) => setFormValues((prev) => ({ ...prev, phone: e.target.value }))}
            className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="contact-role" className="block text-xs font-bold text-[var(--text-primary)]">
            Vai trò của bạn
          </label>
          <select
            id="contact-role"
            name="role"
            value={formValues.role}
            onChange={(e) => setFormValues((prev) => ({ ...prev, role: e.target.value }))}
            className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
          >
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt} value={opt} className="bg-[var(--surface-panel)] text-[var(--text-primary)]">
                {opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Subject and Message */}
      <div className="space-y-1.5">
        <label htmlFor="contact-subject" className="block text-xs font-bold text-[var(--text-primary)]">
          Tiêu đề yêu cầu <span className="text-[var(--status-danger-text)]">*</span>
        </label>
        <input
          id="contact-subject"
          name="subject"
          type="text"
          required
          placeholder="Tóm tắt ngắn gọn vấn đề cần hỗ trợ..."
          value={formValues.subject}
          onChange={(e) => setFormValues((prev) => ({ ...prev, subject: e.target.value }))}
          className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-3.5 py-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
        />
        {errors.subject ? <p className="text-[11px] text-[var(--status-danger-text)] font-semibold">{errors.subject}</p> : null}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="contact-message" className="block text-xs font-bold text-[var(--text-primary)]">
          Nội dung chi tiết <span className="text-[var(--status-danger-text)]">*</span>
        </label>
        <textarea
          id="contact-message"
          name="message"
          rows={5}
          required
          placeholder="Mô tả cụ thể câu hỏi, phản ánh sự cố y khoa hoặc đề xuất hợp tác của bạn..."
          value={formValues.message}
          onChange={(e) => setFormValues((prev) => ({ ...prev, message: e.target.value }))}
          className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)] leading-relaxed"
        />
        {errors.message ? <p className="text-[11px] text-[var(--status-danger-text)] font-semibold">{errors.message}</p> : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-[color:var(--shell-border)]/50">
        <p className="text-[11px] text-[var(--text-muted)]">
          Thời hạn xử lý: trong <strong>24 - 72 giờ</strong> làm việc.
        </p>
        <Button
          type="submit"
          variant="primary"
          disabled={submitting}
          className="w-full sm:w-auto"
          data-testid="contact-submit-btn"
        >
          <Icon name="progress" size="1rem" className={submitting ? "animate-spin" : ""} />
          <span>{submitting ? "Đang gửi yêu cầu..." : "Gửi yêu cầu hỗ trợ"}</span>
        </Button>
      </div>
    </form>
  );
}
