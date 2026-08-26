import Link from "next/link";
import type { Metadata } from "next";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
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
  categoryValue: "patient" | "clinician" | "research" | "dpo";
  icon: IconName;
  title: string;
  badge: string;
  badgeTone: BadgeTone;
  email: string;
  phone?: string;
  sla: string;
  scope: string;
  tags: string[];
}

const CONTACT_CHANNELS: ContactChannel[] = [
  {
    id: "patient-support",
    categoryValue: "patient",
    icon: "user-card",
    title: "1. Hỗ trợ người bệnh & Người dùng cá nhân",
    badge: "Patient & Community Support",
    badgeTone: "brand",
    email: "support@thiennn.icu",
    phone: LEGAL_CONTACT_PHONE,
    sla: "Trong vòng 24 giờ",
    scope:
      "Hướng dẫn cài đặt Tủ thuốc, kết nối chia sẻ hồ sơ người thân, giải đáp thắc mắc tài khoản và sử dụng tính năng tra cứu thông tin thuốc.",
    tags: ["Tủ thuốc cá nhân", "Chia sẻ người thân", "Tra cứu an toàn thuốc", "Tài khoản"],
  },
  {
    id: "clinician-advisory",
    categoryValue: "clinician",
    icon: "clinical-notes",
    title: "2. Ban cố vấn y khoa & Bác sĩ lâm sàng",
    badge: "Clinician & Medical Advisory",
    badgeTone: "ok",
    email: "clinical@thiennn.icu",
    phone: LEGAL_CONTACT_PHONE,
    sla: "Trong vòng 48 giờ",
    scope:
      "Tiếp nhận đăng ký bác sĩ (Doctor onboarding), phản hồi chuyên môn & đánh giá phác đồ hội chẩn Council, kiểm thử độ chuẩn xác của trợ lý Scribe và báo cáo y văn cập nhật.",
    tags: ["Doctor Onboarding", "Council Review", "Scribe Verification", "Cập nhật Y văn"],
  },
  {
    id: "research-inquiries",
    categoryValue: "research",
    icon: "progress",
    title: "3. Hợp tác nghiên cứu & Dữ liệu y học",
    badge: "Research & Data Partnerships",
    badgeTone: "warn",
    email: "research@thiennn.icu",
    phone: LEGAL_CONTACT_PHONE,
    sla: "Trong vòng 72 giờ",
    scope:
      "Hợp tác mô hình Living Evidence RAG, đối chiếu bằng chứng Living Evidence, thử nghiệm lâm sàng độc lập và tài trợ các dự án nghiên cứu học thuật y khoa.",
    tags: ["Living Evidence RAG", "Clinical Trials", "Học thuật y khoa", "Dữ liệu Y chứng"],
  },
  {
    id: "dpo-compliance",
    categoryValue: "dpo",
    icon: "warning",
    title: "4. Cán bộ bảo vệ dữ liệu (DPO) & DSAR",
    badge: "Data Protection Officer (DPO) & DSAR",
    badgeTone: "neutral",
    email: LEGAL_CONTACT_EMAIL,
    phone: LEGAL_CONTACT_PHONE,
    sla: "Tối đa 72 giờ (theo luật)",
    scope:
      "Tiếp nhận và thực thi 11 quyền của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP (DSAR), yêu cầu trích xuất dữ liệu (Data Portability), xóa hoặc hạn chế xử lý dữ liệu y tế cá nhân.",
    tags: ["Nghị định 13/2023/NĐ-CP", "11 Quyền Chủ thể (DSAR)", "Data Portability", "Quyền được quên"],
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
        {/* 1. Header with Breadcrumbs & SLA / Security Badges */}
        <header className="space-y-6 border-b border-[color:var(--shell-border)]/70 pb-8 sm:pb-10">
          {/* Breadcrumb & Navigation Utilities */}
          <nav
            aria-label="Breadcrumb"
            className="flex flex-wrap items-center justify-between gap-3 text-xs font-semibold"
          >
            <ol className="flex items-center gap-1.5 text-[var(--text-secondary)]">
              <li>
                <Link
                  href="/"
                  className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                >
                  <Icon name="arrow-left" size="0.95rem" />
                  <span>Trang chủ</span>
                </Link>
              </li>
              <li aria-hidden="true" className="text-[var(--text-muted)]">
                /
              </li>
              <li>
                <span className="font-bold text-[var(--text-primary)] px-1">
                  Trung tâm liên hệ & Hỗ trợ
                </span>
              </li>
            </ol>

            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              <Link
                href="/huong-dan"
                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="help" size="0.95rem" />
                <span>Trung tâm hướng dẫn</span>
              </Link>
              <Link
                href="/legal"
                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="clinical-notes" size="0.95rem" />
                <span>Trung tâm pháp lý</span>
              </Link>
              <Link
                href="/safety"
                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="check" size="0.95rem" />
                <span>Tuyên ngôn an toàn</span>
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
              >
                <span>Đăng nhập</span>
              </Link>
            </div>
          </nav>

          {/* Hero Header */}
          <div className="space-y-3 pt-1">
            <div className="inline-flex items-center gap-2">
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
                The Clara Care · Contact & Multi-Channel Support Hub
              </p>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Liên hệ & Trung tâm hỗ trợ chuyên môn
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              Chúng tôi luôn sẵn sàng lắng nghe và đồng hành cùng người bệnh, y bác sĩ và các đối tác y tế.
              Vui lòng lựa chọn kênh liên hệ tương ứng hoặc điền biểu mẫu để nhận được phản hồi chính xác nhất.
            </p>
          </div>

          {/* SLA, Security Zero-PII, and Status Badges */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Badge tone="brand" icon="clinical-notes">
              Phản hồi: 24 - 72h
            </Badge>
            <Badge tone="ok" icon="check">
              Bảo mật Zero-PII
            </Badge>
            <Badge tone="ok" icon="calendar">
              Cập nhật: {LEGAL_UPDATED_AT}
            </Badge>
            <Badge tone="neutral" icon="folder">
              Phiên bản: {LEGAL_POLICY_VERSION}
            </Badge>
            <Badge tone="neutral" icon="folder">
              {LEGAL_PRIMARY_DOMAIN}
            </Badge>
          </div>
        </header>

        {/* 2. Prominent 115 Emergency Medical Warning Banner with instant one-touch dialer */}
        <section aria-labelledby="emergency-disclaimer-heading" className="space-y-2">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/25 p-5 sm:p-6 shadow-sm space-y-3.5">
            <div className="flex items-center gap-2.5 text-[var(--status-danger-text)] font-bold text-sm sm:text-base">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--status-danger-text)] opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--status-danger-text)]" />
              </span>
              <h2 id="emergency-disclaimer-heading" className="uppercase tracking-wide font-extrabold">
                Cảnh báo cấp cứu y tế khẩn cấp (115)
              </h2>
            </div>

            <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-primary)]">
              Các kênh liên hệ và biểu mẫu phản hồi dưới đây <strong>KHÔNG PHỤC VỤ CẤP CỨU Y TẾ</strong>.
              Nếu bạn hoặc người thân đang xuất hiện các dấu hiệu đe dọa tính mạng (đau thắt ngực dữ dội, khó thở cấp,
              yếu liệt nửa người, rối loạn ngôn ngữ / đột quỵ FAST, hôn mê, co giật, sốc phản vệ hoặc chấn thương nặng):
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <a
                href="tel:115"
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-4 py-2.5 text-xs sm:text-sm font-bold text-[var(--status-danger-text)] shadow-sm hover:brightness-110 transition active:scale-95 cursor-pointer"
              >
                <Icon name="emergency" size="1.1rem" />
                <span>GỌI NGAY CẤP CỨU 115</span>
              </a>
              <span className="text-xs text-[var(--text-muted)] font-medium">
                Hoặc di chuyển ngay đến khoa Cấp cứu của bệnh viện gần nhất · Hotline 115 hoạt động 24/7 hoàn toàn miễn phí.
              </span>
            </div>
          </div>
        </section>

        {/* 3. 4 Dedicated Contact Channel Cards */}
        <section className="space-y-5" aria-labelledby="contact-channels-heading">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="contact" size="1.25rem" />
              <h2
                id="contact-channels-heading"
                className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Các kênh tiếp nhận chuyên trách
              </h2>
            </div>
            <span className="text-xs text-[var(--text-muted)]">
              4 luồng tiếp nhận độc lập tương ứng với các nhóm nghiệp vụ
            </span>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            {CONTACT_CHANNELS.map((channel) => (
              <div
                key={channel.id}
                className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm hover:border-[color:var(--brand-500)]/60 hover:shadow-md transition-all group"
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={channel.badgeTone} icon={channel.icon}>
                      {channel.badge}
                    </Badge>
                    <span className="text-[11px] font-bold text-[var(--status-ok-text)] bg-[var(--status-ok-bg)]/30 border border-[color:var(--status-ok-border)]/40 px-2 py-0.5 rounded-full">
                      SLA: {channel.sla}
                    </span>
                  </div>

                  <h3 className="text-sm sm:text-base font-bold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                    {channel.title}
                  </h3>

                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {channel.scope}
                  </p>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {channel.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-2 border-t border-[color:var(--shell-border)]/60 pt-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--text-muted)] flex items-center gap-1">
                      <Icon name="send" size="0.75rem" />
                      Email:
                    </span>
                    <a
                      href={`mailto:${channel.email}`}
                      className="font-bold text-[var(--text-brand)] hover:underline"
                    >
                      {channel.email}
                    </a>
                  </div>

                  {channel.phone ? (
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--text-muted)] flex items-center gap-1">
                        <Icon name="contact" size="0.75rem" />
                        Hotline:
                      </span>
                      <a
                        href={`tel:${channel.phone.replace(/\s+/g, "")}`}
                        className="font-bold text-[var(--text-primary)] hover:underline"
                      >
                        {channel.phone}
                      </a>
                    </div>
                  ) : null}

                  <div className="pt-1.5 flex justify-end">
                    <a
                      href="#feedback-form"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--text-brand)] hover:underline"
                    >
                      <span>Chọn kênh này trong biểu mẫu</span>
                      <Icon name="arrow-right" size="0.8rem" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Structured Support & Inquiry Form */}
        <section className="space-y-4" aria-labelledby="feedback-form-heading">
          <ContactFeedbackForm />
        </section>

        {/* 5. Operating Entity Details, Office Hours, Legal Bases & Quick Navigation */}
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

          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="grid gap-6 md:grid-cols-2 text-xs sm:text-sm">
              {/* Operator details */}
              <div className="space-y-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/60 pb-2">
                  <Icon name="user-card" size="1.1rem" className="text-[var(--text-brand)]" />
                  <h3 className="font-bold text-[var(--text-primary)] text-sm">
                    Thông tin chủ thể vận hành
                  </h3>
                </div>

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
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Email pháp lý:</span>
                    <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-mono text-[var(--text-brand)] hover:underline">
                      {LEGAL_CONTACT_EMAIL}
                    </a>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Hotline tiếp nhận:</span>
                    <span className="font-semibold text-[var(--text-primary)]">{LEGAL_CONTACT_PHONE}</span>
                  </div>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-[var(--text-muted)]">Phiên bản chính sách:</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">{LEGAL_POLICY_VERSION}</span>
                  </div>
                </div>
              </div>

              {/* Office hours and legal bases */}
              <div className="space-y-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/60 pb-2">
                  <Icon name="calendar" size="1.1rem" className="text-[var(--status-ok-text)]" />
                  <h3 className="font-bold text-[var(--text-primary)] text-sm">
                    Thời gian làm việc & Căn cứ tuân thủ
                  </h3>
                </div>

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
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                    <span className="text-[var(--text-muted)]">Minh bạch AI:</span>
                    <span className="font-semibold text-[var(--text-brand)]">Luật AI số 134/2025/QH15</span>
                  </div>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-[var(--text-muted)]">Chuẩn hóa dược thư:</span>
                    <span className="font-semibold text-[var(--text-primary)]">Dược thư Quốc gia VN 2022</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Navigation Links */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/60 pt-4 text-xs">
              <span className="text-[var(--text-muted)]">
                Bạn cần xem lại các điều khoản pháp lý, an toàn lâm sàng hoặc quyền riêng tư?
              </span>
              <div className="flex flex-wrap items-center gap-3">
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
                <span className="text-[var(--text-muted)]">·</span>
                <Link href="/legal/terms" className="font-bold text-[var(--text-brand)] hover:underline">
                  Điều khoản
                </Link>
                <span className="text-[var(--text-muted)]">·</span>
                <Link href="/legal/cookies" className="font-bold text-[var(--text-brand)] hover:underline">
                  Cookie
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
