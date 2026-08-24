import Link from "next/link";
import { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { SectionIndex, type SectionIndexItem, type SectionIndexStatus } from "@/components/ui/section-index";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

export type LegalPolicyKey = "hub" | "privacy" | "terms" | "consent" | "cookies";

export interface LegalNavItem {
  key: Exclude<LegalPolicyKey, "hub">;
  href: string;
  shortLabel: string;
  title: string;
  description: string;
  badgeTone: BadgeTone;
}

export interface LegalSectionMeta {
  id: string;
  title?: string;
  label?: string;
  subtitle?: string;
  badge?: ReactNode;
  status?: SectionIndexStatus;
}

export interface LegalPageShellProps {
  title: string;
  eyebrow?: string;
  summary: string;
  updatedAt?: string;
  version?: string;
  policyKey: LegalPolicyKey;
  sections?: LegalSectionMeta[];
  highlights?: string[];
  relatedControls?: Array<{
    href: string;
    label: string;
    description?: string;
    badge?: string;
  }>;
  children: ReactNode;
}

export interface LegalSectionProps {
  id: string;
  title: string;
  subtitle?: string;
  badge?: string;
  children: ReactNode;
}

export const POLICY_NAV_ITEMS: LegalNavItem[] = [
  {
    key: "privacy",
    href: "/legal/privacy",
    shortLabel: "Riêng tư",
    title: "Chính sách quyền riêng tư",
    description: "Bảo vệ dữ liệu, DSAR & chuẩn Zero-CoT (Nghị định 13/2023)",
    badgeTone: "ok",
  },
  {
    key: "terms",
    href: "/legal/terms",
    shortLabel: "Điều khoản",
    title: "Điều khoản sử dụng",
    description: "Quy định dịch vụ, thanh toán & ranh giới y tế",
    badgeTone: "brand",
  },
  {
    key: "consent",
    href: "/legal/consent",
    shortLabel: "Đồng thuận",
    title: "Đồng thuận y tế",
    description: "Điều khoản bắt buộc trước can thiệp & xác nhận chuyên môn",
    badgeTone: "warn",
  },
  {
    key: "cookies",
    href: "/legal/cookies",
    shortLabel: "Cookie",
    title: "Chính sách cookie",
    description: "Phiên đăng nhập an toàn & tùy chọn giao diện",
    badgeTone: "neutral",
  },
];

export function LegalSection({
  id,
  title,
  subtitle,
  badge,
  children,
}: LegalSectionProps) {
  return (
    <article
      id={id}
      aria-labelledby={`${id}-heading`}
      className="scroll-mt-24 rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-4 shadow-sm"
    >
      <div className="space-y-1.5 border-b border-[color:var(--shell-border)]/60 pb-3.5">
        {badge ? (
          <div className="mb-1.5">
            <Badge tone="brand">{badge}</Badge>
          </div>
        ) : null}
        <h2
          id={`${id}-heading`}
          className="text-lg sm:text-xl font-bold tracking-tight text-[var(--text-primary)]"
        >
          {title}
        </h2>
        {subtitle ? (
          <p className="text-xs text-[var(--text-muted)] font-medium">{subtitle}</p>
        ) : null}
      </div>
      <div className="space-y-4 text-sm sm:text-[15px] leading-7 text-[var(--text-secondary)]">
        {children}
      </div>
    </article>
  );
}

export default function LegalPageShell({
  title,
  eyebrow = "The Clara Care · Legal Document Reader",
  summary,
  updatedAt = LEGAL_UPDATED_AT,
  version = LEGAL_POLICY_VERSION,
  policyKey,
  sections = [],
  highlights = [],
  relatedControls = [],
  children,
}: LegalPageShellProps) {
  const sectionIndexItems: SectionIndexItem[] = sections.map((s) => ({
    id: s.id,
    title: s.title || s.label || "",
    subtitle: s.subtitle,
    badge: s.badge,
    status: s.status,
  }));

  return (
    <div className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pb-16 pt-8 sm:px-6 sm:pb-20 sm:pt-10 lg:px-8">
        {/* 1. Header & Navigation */}
        <header className="space-y-6 border-b border-[color:var(--shell-border)]/70 pb-8 sm:pb-10">
          <nav className="flex flex-wrap items-center justify-between gap-3 text-xs font-semibold">
            <div className="flex items-center gap-2">
              <Link
                href="/legal"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="arrow-left" size="1rem" />
                <span>Trung tâm pháp lý</span>
              </Link>
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-muted)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] hidden sm:inline-flex"
              >
                <span>Trang chủ</span>
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/huong-dan"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="help" size="1rem" />
                <span>Trung tâm hướng dẫn</span>
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
              {eyebrow}
            </p>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-3xl lg:text-4xl">
              {title}
            </h1>
            <div className="rounded-[var(--radius-xl)] border border-[color:var(--brand-500)]/25 bg-[var(--surface-brand-soft)]/50 p-4 sm:p-5">
              <p className="max-w-4xl text-sm leading-relaxed text-[var(--text-primary)] sm:text-[15px]">
                {summary}
              </p>
            </div>
          </div>

          {/* Revision Metadata & Statutory Badges */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Badge tone="brand" icon="clinical-notes">
              Phiên bản: {version}
            </Badge>
            <Badge tone="ok" icon="calendar">
              Cập nhật: {updatedAt}
            </Badge>
            <Badge tone="neutral" icon="check">
              Luật Khám bệnh 2023 · NĐ 13/2023 · Luật AI 134/2025
            </Badge>
            <Badge tone="neutral" icon="warning">
              Bảo đảm Zero-CoT · Zero-PII Telemetry
            </Badge>
            <Badge tone="neutral" icon="folder">
              {LEGAL_PRIMARY_DOMAIN}
            </Badge>
          </div>

          {/* Quick Policy Switcher Tabs */}
          <nav
            aria-label="Điều hướng danh mục văn bản pháp lý"
            className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4 pt-2"
          >
            {POLICY_NAV_ITEMS.map((item) => {
              const active = policyKey === item.key;
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  className={[
                    "flex flex-col justify-between rounded-[var(--radius-xl)] border p-3.5 transition-all",
                    active
                      ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-sm"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:border-[color:var(--shell-border)]/80 hover:bg-[var(--surface-muted)]",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-black uppercase tracking-[0.14em]">
                      {item.shortLabel}
                    </span>
                    <Badge tone={active ? "brand" : item.badgeTone}>
                      {active ? "Đang đọc" : "Chính thức"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                    {item.title}
                  </p>
                  <p className="mt-1 text-[11px] leading-normal text-[var(--text-muted)] line-clamp-1">
                    {item.description}
                  </p>
                </Link>
              );
            })}
          </nav>

          {/* Key Highlights / Editorial Guarantees */}
          {highlights.length > 0 ? (
            <div className="grid gap-3 pt-2 sm:grid-cols-2 lg:grid-cols-4">
              {highlights.map((highlight, index) => (
                <div
                  key={index}
                  className="flex items-start gap-2.5 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 text-xs font-semibold leading-relaxed text-[var(--text-secondary)] shadow-sm"
                >
                  <div className="mt-0.5 shrink-0 text-[var(--status-ok-text)]">
                    <Icon name="check" size="0.95rem" />
                  </div>
                  <span>{highlight}</span>
                </div>
              ))}
            </div>
          ) : null}
        </header>

        {/* 2. Main Content Grid: Constrained Editorial Reader + Sticky Sidebar */}
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px] items-start">
          {/* Main Legal Body: Constrained editorial width (max-w-3xl) */}
          <main className="w-full max-w-3xl space-y-6 sm:space-y-8">
            {children}
          </main>

          {/* Sticky Sidebar: SectionIndex + Legal Citations & Contacts */}
          <aside className="space-y-6 lg:sticky lg:top-6 lg:self-start w-full">
            {/* Table of Contents / Section Index */}
            {sectionIndexItems.length > 0 ? (
              <SectionIndex
                items={sectionIndexItems}
                title="Mục lục điều khoản"
                description="Nhấp để chuyển nhanh đến điều khoản tương ứng"
                autoScrollSpy={true}
                density="compact"
                sticky={false}
              />
            ) : null}

            {/* Vietnamese Legal Citations & Guarantees Card */}
            <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
              <div className="flex items-center gap-2 text-[var(--text-brand)]">
                <Icon name="clinical-notes" size="1.1rem" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  Căn cứ pháp lý & Chuẩn an toàn
                </h3>
              </div>
              <ul className="space-y-2.5 text-xs leading-relaxed text-[var(--text-secondary)] list-none p-0 m-0">
                <li className="flex items-start gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
                  <span className="font-bold text-[var(--text-primary)] shrink-0">•</span>
                  <span>
                    <strong>Luật Khám bệnh 2023 (15/2023/QH15):</strong> Trợ lý thông tin, không thay thế bác sĩ khám chữa bệnh.
                  </span>
                </li>
                <li className="flex items-start gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
                  <span className="font-bold text-[var(--text-primary)] shrink-0">•</span>
                  <span>
                    <strong>Nghị định 13/2023/NĐ-CP (PDPD):</strong> Bảo vệ dữ liệu nhạy cảm & 11 quyền chủ thể dữ liệu (DSAR).
                  </span>
                </li>
                <li className="flex items-start gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
                  <span className="font-bold text-[var(--text-primary)] shrink-0">•</span>
                  <span>
                    <strong>Luật AI 134/2025/QH15:</strong> Phân loại AI rủi ro cao trong y tế, giám sát con người liên tục.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-bold text-[var(--status-ok-text)] shrink-0">✓</span>
                  <span>
                    <strong>Zero-CoT & Zero-PII:</strong> Tuyệt đối không lưu vết chuỗi suy luận và không thu thập PII telemetry.
                  </span>
                </li>
              </ul>
            </div>

            {/* DPO & Compliance Contact */}
            <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 shadow-sm text-xs">
              <div className="flex items-center gap-2 text-[var(--text-brand)]">
                <Icon name="contact" size="1.1rem" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  Cán bộ bảo vệ dữ liệu (DPO)
                </h3>
              </div>
              <div className="space-y-2 pt-1 text-[var(--text-secondary)]">
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                  <span className="text-[var(--text-muted)]">Email DPO:</span>
                  <a
                    href={`mailto:${LEGAL_CONTACT_EMAIL}`}
                    className="font-bold text-[var(--text-brand)] hover:underline"
                  >
                    {LEGAL_CONTACT_EMAIL}
                  </a>
                </div>
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                  <span className="text-[var(--text-muted)]">Hotline:</span>
                  <a
                    href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`}
                    className="font-bold text-[var(--text-primary)] hover:underline"
                  >
                    {LEGAL_CONTACT_PHONE}
                  </a>
                </div>
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-1.5">
                  <span className="text-[var(--text-muted)]">Chủ thể:</span>
                  <span className="font-semibold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
                </div>
                <div className="flex items-center justify-between pt-0.5">
                  <span className="text-[var(--text-muted)]">SLA xử lý DSAR:</span>
                  <span className="font-semibold text-[var(--status-ok-text)]">Trong 72h làm việc</span>
                </div>
              </div>
            </div>

            {/* Related Controls Link */}
            {relatedControls.length > 0 ? (
              <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-2.5">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  Công cụ & Kiểm soát liên quan
                </p>
                <div className="space-y-2">
                  {relatedControls.map((ctrl) => (
                    <Link
                      key={ctrl.href}
                      href={ctrl.href}
                      className="group flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2.5 text-xs font-semibold transition hover:border-[color:var(--brand-500)]/60 hover:bg-[var(--surface-hover)]"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                          {ctrl.label}
                        </p>
                        {ctrl.description ? (
                          <p className="text-[11px] text-[var(--text-muted)] truncate">
                            {ctrl.description}
                          </p>
                        ) : null}
                      </div>
                      <Icon
                        name="arrow-right"
                        size="0.9rem"
                        className="text-[var(--text-muted)] group-hover:text-[var(--text-brand)] group-hover:translate-x-0.5 transition-all shrink-0"
                      />
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>
        </div>
      </div>
    </div>
  );
}

