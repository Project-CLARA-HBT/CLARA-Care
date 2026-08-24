import Link from "next/link";
import type { Metadata } from "next";
import { Icon } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

export const metadata: Metadata = {
  title: "Thỏa thuận người dùng & Trung tâm pháp lý | The Clara Care",
  description:
    "Tổng hợp văn bản pháp lý The Clara Care: Thỏa thuận người dùng, Chính sách quyền riêng tư, Đồng thuận y tế và Chính sách cookie theo chuẩn bảo vệ dữ liệu và minh bạch AI.",
};

interface LegalTopicItem {
  href: string;
  category: string;
  title: string;
  description: string;
  updatedAt: string;
  version: string;
  badgeTone: BadgeTone;
}

const LEGAL_TOPICS: LegalTopicItem[] = [
  {
    href: "/legal/terms",
    category: "Thỏa thuận dịch vụ",
    title: "Điều khoản sử dụng (Terms of Service)",
    description:
      "Quy định quyền và nghĩa vụ pháp lý khi sử dụng dịch vụ The Clara Care, phạm vi sử dụng hợp lệ, giới hạn trách nhiệm y tế và điều kiện duy trì tài khoản.",
    updatedAt: LEGAL_UPDATED_AT,
    version: LEGAL_POLICY_VERSION,
    badgeTone: "brand",
  },
  {
    href: "/legal/privacy",
    category: "Bảo vệ dữ liệu & DSAR",
    title: "Chính sách quyền riêng tư (Privacy Policy)",
    description:
      "Mô tả chi tiết cách thức thu thập, xử lý, bảo vệ dữ liệu cá nhân & PHR theo Nghị định 13/2023/NĐ-CP, danh sách bên xử lý dữ liệu và quy trình thực hiện quyền DSAR.",
    updatedAt: LEGAL_UPDATED_AT,
    version: LEGAL_POLICY_VERSION,
    badgeTone: "ok",
  },
  {
    href: "/legal/consent",
    category: "An toàn lâm sàng",
    title: "Đồng thuận y tế (Medical Consent)",
    description:
      "Điều khoản bắt buộc trước khi sử dụng các tính năng có tác động lâm sàng. Nêu rõ vai trò hỗ trợ của AI và yêu cầu xác nhận chuyên môn y tế trước quyết định điều trị.",
    updatedAt: LEGAL_UPDATED_AT,
    version: LEGAL_POLICY_VERSION,
    badgeTone: "warn",
  },
  {
    href: "/legal/cookies",
    category: "Phiên làm việc & Tùy chọn",
    title: "Chính sách cookie (Cookie Policy)",
    description:
      "Chi tiết về cookie cần thiết, cookie chức năng lưu tùy chọn giao diện, cơ chế quản lý tại trình duyệt và cam kết không chia sẻ dữ liệu vì mục đích quảng cáo.",
    updatedAt: LEGAL_UPDATED_AT,
    version: LEGAL_POLICY_VERSION,
    badgeTone: "neutral",
  },
];

const EDITORIAL_PILLARS = [
  {
    icon: "warning",
    title: "1. Quyền riêng tư & Chuẩn Zero-CoT",
    description:
      "Dữ liệu sức khỏe cá nhân (PHR) và các nội dung trao đổi lâm sàng được bảo vệ nghiêm ngặt theo Nghị định 13/2023/NĐ-CP. CLARA áp dụng nguyên tắc thu thập tối thiểu, không lưu vết chuỗi suy luận nội bộ nhạy cảm và tuyệt đối không chia sẻ hay kinh doanh dữ liệu người dùng.",
  },
  {
    icon: "clinical-notes",
    title: "2. Minh bạch hệ thống AI (Luật 134/2025)",
    description:
      "Mọi khuyến nghị y khoa đều minh bạch về họ mô hình AI suy luận và trích dẫn rõ nguồn y văn đã được xác thực (Living Evidence, PubMed, Dược thư quốc gia). Người dùng luôn nhận biết rõ ràng khi hệ thống vận hành ở trạng thái suy giảm hoặc tuyến dự phòng nội bộ.",
  },
  {
    icon: "contact",
    title: "3. Ranh giới dữ liệu & Trách nhiệm lâm sàng",
    description:
      "CLARA là trợ lý tham vấn và hỗ trợ ra quyết định lâm sàng, không thay thế bác sĩ hoặc nhân viên y tế có giấy phép hành nghề. Hệ thống không tự ý kê đơn hay chẩn đoán xác định; các tình huống triệu chứng cấp cứu được kích hoạt luồng chuyển hướng y tế khẩn cấp ngay lập tức.",
  },
] as const;

export default function LegalHubPage() {
  return (
    <div className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 sm:py-14 lg:px-8 space-y-10 sm:space-y-12">
        {/* 1. Public Legal Header */}
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
                href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
              >
                <span>Đăng nhập</span>
              </Link>
            </div>
          </nav>

          <div className="space-y-3">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
              The Clara Care · Legal Index
            </p>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Thỏa thuận người dùng & Trung tâm pháp lý
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              Nguồn tham chiếu chính thức quy định quyền, nghĩa vụ, tiêu chuẩn bảo mật dữ liệu y tế
              và ranh giới trách nhiệm lâm sàng cho toàn bộ người dùng, chuyên gia y tế và quản trị viên của The Clara Care.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Badge tone="brand" icon="clinical-notes">
              Phiên bản: {LEGAL_POLICY_VERSION}
            </Badge>
            <Badge tone="ok" icon="calendar">
              Cập nhật: {LEGAL_UPDATED_AT}
            </Badge>
            <Badge tone="neutral" icon="check">
              Nghị định 13/2023/NĐ-CP & Luật AI 134/2025
            </Badge>
            <Badge tone="neutral" icon="folder">
              {LEGAL_PRIMARY_DOMAIN}
            </Badge>
          </div>
        </header>

        {/* 2. Editorial Intro: Privacy, Transparency, and Data Boundaries */}
        <section className="space-y-4" aria-labelledby="editorial-intro-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="clinical-notes" size="1.25rem" />
            <h2
              id="editorial-intro-heading"
              className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
            >
              Cam kết bảo vệ dữ liệu, tính minh bạch và ranh giới lâm sàng
            </h2>
          </div>

          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6">
            <p className="text-sm leading-7 text-[var(--text-secondary)] sm:text-[15px]">
              The Clara Care được thiết kế dựa trên nguyên tắc đặt an toàn bệnh nhân và quyền riêng tư cá nhân lên hàng đầu.
              Mọi tương tác trong hệ thống đều tuân thủ khuôn khổ pháp lý chặt chẽ và các giới hạn kỹ thuật được thiết lập sẵn:
            </p>

            <div className="grid gap-4 sm:grid-cols-3">
              {EDITORIAL_PILLARS.map((pillar) => (
                <div
                  key={pillar.title}
                  className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)]/50 p-4 sm:p-5 space-y-2.5"
                >
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name={pillar.icon} size="1.1rem" />
                    <h3 className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                      {pillar.title}
                    </h3>
                  </div>
                  <p className="text-xs sm:text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    {pillar.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 3. Legal Topics as Vertical List Rows */}
        <section className="space-y-4" aria-labelledby="legal-topics-heading">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size="1.25rem" />
              <h2
                id="legal-topics-heading"
                className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Danh mục văn bản pháp lý chính thức
              </h2>
            </div>
            <span className="text-xs text-[var(--text-muted)] font-medium">
              4 văn bản hiệu lực
            </span>
          </div>

          <ul className="space-y-3 list-none p-0 m-0" role="list">
            {LEGAL_TOPICS.map((topic) => (
              <li key={topic.href}>
                <Link
                  href={topic.href}
                  className="group flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6 transition-all hover:border-[color:var(--brand-500)]/60 hover:bg-[var(--surface-hover)] hover:shadow-sm"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={topic.badgeTone}>{topic.category}</Badge>
                      <h3 className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                        {topic.title}
                      </h3>
                    </div>
                    <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
                      {topic.description}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-[var(--text-muted)]">
                      <span>Phiên bản: {topic.version}</span>
                      <span aria-hidden="true">·</span>
                      <span>Cập nhật: {topic.updatedAt}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                    <span className="text-xs font-bold text-[var(--text-brand)] opacity-0 group-hover:opacity-100 transition-opacity hidden sm:inline">
                      Xem văn bản
                    </span>
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--surface-muted)] text-[var(--text-muted)] group-hover:bg-[var(--surface-brand-soft)] group-hover:text-[var(--text-brand)] transition-all">
                      <Icon
                        name="arrow-right"
                        size="1.1rem"
                        className="transition-transform group-hover:translate-x-0.5"
                      />
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {/* 4. Data Protection Officer (DPO) and Compliance Contact Block */}
        <section className="space-y-4" aria-labelledby="dpo-compliance-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="contact" size="1.25rem" />
            <h2
              id="dpo-compliance-heading"
              className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
            >
              Cán bộ bảo vệ dữ liệu (DPO) & Thông tin tuân thủ
            </h2>
          </div>

          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* DPO & DSAR Channel */}
              <div className="space-y-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="clinical-notes" size="1.1rem" />
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    Kênh tiếp nhận DPO & Yêu cầu DSAR
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                  Theo Nghị định 13/2023/NĐ-CP, bạn có quyền tra cứu, trích xuất (Data Portability),
                  yêu cầu chỉnh sửa hoặc xóa dữ liệu cá nhân bất kỳ lúc nào.
                </p>
                <div className="space-y-2 pt-2 text-xs">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
                    <span className="text-[var(--text-muted)]">Email DPO:</span>
                    <a
                      href={`mailto:${LEGAL_CONTACT_EMAIL}`}
                      className="font-bold text-[var(--text-brand)] hover:underline"
                    >
                      {LEGAL_CONTACT_EMAIL}
                    </a>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
                    <span className="text-[var(--text-muted)]">Hotline tuân thủ:</span>
                    <a
                      href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`}
                      className="font-bold text-[var(--text-primary)] hover:underline"
                    >
                      {LEGAL_CONTACT_PHONE}
                    </a>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[var(--text-muted)]">Thời hạn xử lý (SLA):</span>
                    <span className="font-semibold text-[var(--status-ok-text)]">Trong 72 giờ làm việc</span>
                  </div>
                </div>
              </div>

              {/* Operator & Legal Entity */}
              <div className="space-y-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-5">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="folder" size="1.1rem" />
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    Thông tin chủ thể vận hành
                  </h3>
                </div>
                <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                  The Clara Care được vận hành tuân thủ quy định pháp luật Việt Nam về giao dịch điện tử,
                  an toàn thông tin mạng và bảo vệ dữ liệu cá nhân.
                </p>
                <div className="space-y-2 pt-2 text-xs">
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
                    <span className="text-[var(--text-muted)]">Chủ thể vận hành:</span>
                    <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
                    <span className="text-[var(--text-muted)]">Domain chính thức:</span>
                    <span className="font-bold text-[var(--text-primary)]">https://{LEGAL_PRIMARY_DOMAIN}</span>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[var(--text-muted)]">Căn cứ pháp lý:</span>
                    <span className="font-semibold text-[var(--text-secondary)]">Luật GDD 2023 · NĐ 13/2023 · Luật AI</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-[color:var(--status-ok-border)]/60 bg-[var(--status-ok-bg)] p-4 text-xs leading-relaxed text-[var(--status-ok-text)]">
              <p>
                <strong>Cam kết tuân thủ:</strong> Trong trường hợp có bất kỳ thay đổi nào về chính sách bảo mật hoặc cơ chế xử lý dữ liệu y tế,
                phiên bản điều chỉnh sẽ được công bố tập trung tại trang này kèm thông báo xác nhận trước khi tiếp tục truy cập các dịch vụ chuyên môn.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
