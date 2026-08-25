import Link from "next/link";
import type { Metadata } from "next";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";
import { ContactFeedbackForm } from "./contact-form";

export const metadata: Metadata = {
  title: "Liên hệ & Trung tâm hỗ trợ chuyên môn | The Clara Care",
  description:
    "Kết nối với các kênh hỗ trợ chính thức của The Clara Care: Hỗ trợ người bệnh, Ban cố vấn lâm sàng, Hợp tác nghiên cứu y học chứng cứ và Cán bộ bảo vệ dữ liệu (DPO).",
};

interface ContactChannel {
  id: string;
  icon: IconName;
  title: string;
  badge: string;
  badgeTone: "brand" | "ok" | "warn" | "neutral";
  email: string;
  phone?: string;
  sla: string;
  scope: string;
}

const CONTACT_CHANNELS: ContactChannel[] = [
  {
    id: "patient-support",
    icon: "user-card",
    title: "1. Hỗ trợ người bệnh & Người dùng cá nhân",
    badge: "Patient Support",
    badgeTone: "brand",
    email: "support@thiennn.icu",
    phone: LEGAL_CONTACT_PHONE,
    sla: "Trong vòng 24 giờ",
    scope: "Hướng dẫn cài đặt Tủ thuốc, kết nối chia sẻ hồ sơ người thân, giải đáp thắc mắc tài khoản và sử dụng tính năng tra cứu thông tin thuốc.",
  },
  {
    id: "clinician-advisory",
    icon: "clinical-notes",
    title: "2. Ban cố vấn y khoa & Bác sĩ lâm sàng",
    badge: "Clinician Advisory",
    badgeTone: "ok",
    email: "clinical@thiennn.icu",
    phone: LEGAL_CONTACT_PHONE,
    sla: "Trong vòng 48 giờ",
    scope: "Tiếp nhận phản hồi chuyên môn từ các bác sĩ/dược sĩ, đánh giá phác đồ hội chẩn Council, kiểm thử độ chuẩn xác của trợ lý Scribe và báo cáo y văn cập nhật.",
  },
  {
    id: "research-inquiries",
    icon: "progress",
    title: "3. Hợp tác nghiên cứu & Dữ liệu y học",
    badge: "Research Inquiries",
    badgeTone: "warn",
    email: "research@thiennn.icu",
    sla: "Trong vòng 72 giờ",
    scope: "Hợp tác đào tạo mô hình AI y tế, đối chiếu bằng chứng Living Evidence, thử nghiệm lâm sàng độc lập và tài trợ các dự án nghiên cứu học thuật y khoa.",
  },
  {
    id: "dpo-compliance",
    icon: "warning",
    title: "4. Cán bộ bảo vệ dữ liệu (DPO) & DSAR",
    badge: "Data Protection Officer",
    badgeTone: "neutral",
    email: LEGAL_CONTACT_EMAIL,
    phone: LEGAL_CONTACT_PHONE,
    sla: "Tối đa 72 giờ (theo luật)",
    scope: "Tiếp nhận và thực thi 11 quyền của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP (DSAR), yêu cầu trích xuất dữ liệu (Data Portability), xóa hoặc hạn chế xử lý dữ liệu y tế cá nhân.",
  },
];

export default function ContactPage() {
  return (
    <div
      className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      data-shell-mode="PUBLIC_LEGAL"
      data-layout-archetype="Contact Hub"
    >
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-14 lg:px-8 space-y-10 sm:space-y-12">
        {/* 1. Header & Navigation */}
        <header className="space-y-5 border-b border-[color:var(--shell-border)]/70 pb-8 sm:pb-10">
          <nav className="flex flex-wrap items-center justify-between gap-3 text-xs font-semibold">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              <Icon name="arrow-left" size="1rem" />
              <span>Về trang chủ</span>
            </Link>
            <div className="flex items-center gap-2">
              <Link
                href="/huong-dan"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="help" size="1rem" />
                <span>Trung tâm hướng dẫn</span>
              </Link>
              <Link
                href="/legal"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="clinical-notes" size="1rem" />
                <span>Trung tâm pháp lý</span>
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
              >
                <span>Đăng nhập</span>
              </Link>
            </div>
          </nav>

          <div className="space-y-3">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
              The Clara Care · Contact & Support Channels
            </p>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Liên hệ & Trung tâm hỗ trợ chuyên môn
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              Chúng tôi luôn sẵn sàng lắng nghe và đồng hành cùng người bệnh, y bác sĩ và các đối tác y tế.
              Vui lòng lựa chọn kênh liên hệ tương ứng hoặc điền biểu mẫu để nhận được phản hồi chính xác nhất.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Badge tone="brand" icon="clinical-notes">
              Phản hồi: 24 - 72h
            </Badge>
            <Badge tone="ok" icon="calendar">
              Cập nhật: {LEGAL_UPDATED_AT}
            </Badge>
            <Badge tone="neutral" icon="warning">
              Bảo mật Zero-PII
            </Badge>
            <Badge tone="neutral" icon="folder">
              {LEGAL_PRIMARY_DOMAIN}
            </Badge>
          </div>
        </header>

        {/* 2. Prominent Emergency 115 Disclaimer Banner */}
        <section aria-labelledby="emergency-disclaimer-heading" className="space-y-2">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/25 p-5 sm:p-6 shadow-sm space-y-3">
            <div className="flex items-center gap-2.5 text-[var(--status-danger-text)] font-bold text-sm sm:text-base">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--status-danger-text)] opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--status-danger-text)]" />
              </span>
              <h2 id="emergency-disclaimer-heading" className="uppercase tracking-wide">
                Cảnh báo cấp cứu y tế khẩn cấp (115)
              </h2>
            </div>
            <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-primary)]">
              Các kênh liên hệ và biểu mẫu phản hồi dưới đây <strong>KHÔNG PHỤC VỤ CẤP CỨU Y TẾ</strong>.
              Nếu bạn hoặc người thân đang xuất hiện các dấu hiệu đe dọa tính mạng (đau thắt ngực dữ dội, khó thở cấp,
              yếu liệt nửa người, hôn mê, co giật, sốc phản vệ hoặc chấn thương nặng):
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <a
                href="tel:115"
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-4 py-2 text-xs font-bold text-[var(--status-danger-text)] shadow-sm hover:brightness-110 transition active:scale-95"
              >
                <Icon name="emergency" size="1rem" />
                <span>GỌI NGAY CẤP CỨU 115</span>
              </a>
              <span className="text-xs text-[var(--text-muted)] font-medium">
                Hoặc di chuyển ngay đến khoa Cấp cứu của bệnh viện gần nhất
              </span>
            </div>
          </div>
        </section>

        {/* 3. 4 Dedicated Contact Channels Grid */}
        <section className="space-y-4" aria-labelledby="contact-channels-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="contact" size="1.25rem" />
            <h2
              id="contact-channels-heading"
              className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
            >
              Các kênh tiếp nhận chuyên trách
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {CONTACT_CHANNELS.map((channel) => (
              <div
                key={channel.id}
                className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm hover:border-[color:var(--brand-500)]/50 transition"
              >
                <div className="space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={channel.badgeTone}>{channel.badge}</Badge>
                    <span className="text-[11px] text-[var(--status-ok-text)] font-semibold">
                      SLA: {channel.sla}
                    </span>
                  </div>
                  <h3 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
                    {channel.title}
                  </h3>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {channel.scope}
                  </p>
                </div>

                <div className="space-y-1.5 border-t border-[color:var(--shell-border)]/50 pt-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--text-muted)]">Email:</span>
                    <a
                      href={`mailto:${channel.email}`}
                      className="font-bold text-[var(--text-brand)] hover:underline"
                    >
                      {channel.email}
                    </a>
                  </div>
                  {channel.phone ? (
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--text-muted)]">Hotline:</span>
                      <a
                        href={`tel:${channel.phone.replace(/\s+/g, "")}`}
                        className="font-bold text-[var(--text-primary)] hover:underline"
                      >
                        {channel.phone}
                      </a>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Structured Feedback & Inquiry Form */}
        <section className="space-y-4" aria-labelledby="feedback-form-heading">
          <ContactFeedbackForm />
        </section>

        {/* 5. Compliance Address & Legal Entity Details */}
        <section className="space-y-4" aria-labelledby="compliance-address-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="folder" size="1.25rem" />
            <h2
              id="compliance-address-heading"
              className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
            >
              Địa chỉ tuân thủ pháp lý & Thông tin đơn vị vận hành
            </h2>
          </div>

          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6">
            <div className="grid gap-6 md:grid-cols-2 text-xs sm:text-sm">
              <div className="space-y-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <h3 className="font-bold text-[var(--text-primary)]">Thông tin chủ thể vận hành</h3>
                <div className="space-y-2 text-xs text-[var(--text-secondary)]">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Chủ thể quản trị:</span>
                    <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Nền tảng:</span>
                    <span className="font-semibold text-[var(--text-primary)]">The Clara Care</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Tên miền chính thức:</span>
                    <span className="font-mono text-[var(--text-brand)]">https://{LEGAL_PRIMARY_DOMAIN}</span>
                  </div>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-[var(--text-muted)]">Phiên bản chính sách:</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">{LEGAL_POLICY_VERSION}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <h3 className="font-bold text-[var(--text-primary)]">Thời gian làm việc & Căn cứ tuân thủ</h3>
                <div className="space-y-2 text-xs text-[var(--text-secondary)]">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Giờ tiếp nhận:</span>
                    <span className="font-semibold text-[var(--text-primary)]">08:00 - 18:00 (Thứ 2 - Thứ 6)</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Bảo vệ dữ liệu y tế:</span>
                    <span className="font-semibold text-[var(--status-ok-text)]">Nghị định 13/2023/NĐ-CP</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Ranh giới lâm sàng:</span>
                    <span className="font-semibold text-[var(--text-primary)]">Luật Khám bệnh số 15/2023</span>
                  </div>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-[var(--text-muted)]">Minh bạch AI:</span>
                    <span className="font-semibold text-[var(--text-brand)]">Luật AI số 134/2025/QH15</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/60 pt-4 text-xs">
              <span className="text-[var(--text-muted)]">
                Bạn cần xem lại các điều khoản pháp lý hoặc quyền riêng tư?
              </span>
              <div className="flex items-center gap-3">
                <Link href="/legal/privacy" className="font-bold text-[var(--text-brand)] hover:underline">
                  Quyền riêng tư & DSAR
                </Link>
                <span className="text-[var(--text-muted)]">·</span>
                <Link href="/legal/consent" className="font-bold text-[var(--text-brand)] hover:underline">
                  Đồng thuận y tế
                </Link>
                <span className="text-[var(--text-muted)]">·</span>
                <Link href="/safety" className="font-bold text-[var(--text-brand)] hover:underline">
                  Tuyên ngôn an toàn
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
