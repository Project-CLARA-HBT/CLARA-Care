import Link from "next/link";
import type { Metadata } from "next";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import {
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

export const metadata: Metadata = {
  title: "Tuyên ngôn an toàn lâm sàng & Khung bảo vệ đa tầng | The Clara Care",
  description:
    "Tìm hiểu kiến trúc an toàn bất biến của The Clara Care: Ma trận xác thực FIDES, hàng rào chống ảo giác Zero-CoT, và 5 tầng phân cấp an toàn lâm sàng theo Luật Khám bệnh 2023.",
};

const SAFETY_TIERS = [
  {
    tier: "Tầng 1",
    title: "Phân loại & Chuyển hướng Cấp cứu Khẩn cấp (115 Fast-Path)",
    badge: "Ưu tiên cao nhất",
    badgeTone: "danger" as const,
    icon: "warning",
    summary:
      "Tự động phát hiện các triệu chứng đe dọa tính mạng (cờ đỏ cấp cứu) và chuyển hướng ngay lập tức tới đầu số 115, bỏ qua độ trễ suy luận AI.",
    details: [
      "Bộ quét từ khóa triệu chứng nguy cấp thời gian thực (đau thắt ngực, khó thở cấp, dấu hiệu đột quỵ FAST, sốc phản vệ, co giật, xuất huyết ồ ạt).",
      "Kích hoạt giao diện cấp cứu khẩn cấp với nút bấm gọi trực tiếp 115 chỉ bằng một chạm.",
      "Chặn toàn bộ chu trình sinh văn bản chẩn đoán nhằm tuyệt đối tránh làm chậm trễ thời gian vàng cấp cứu của người bệnh.",
    ],
  },
  {
    tier: "Tầng 2",
    title: "Hàng rào Pháp lý & Ranh giới Lâm sàng (Legal Hard-Guards)",
    badge: "Luật Khám bệnh 2023",
    badgeTone: "warn" as const,
    icon: "clinical-notes",
    summary:
      "Ngăn chặn mô hình AI tự ý đưa ra kết luận chẩn đoán xác định hoặc kê đơn thuốc độc lập trái thẩm quyền.",
    details: [
      "Áp dụng bộ lọc phân loại ý định (Intent Classifier) chặn các yêu cầu yêu cầu kê đơn, chỉ định liều lượng cá nhân hóa độc lập hoặc khẳng định chẩn đoán bệnh lý hiểm nghèo.",
      "Luôn đính kèm khuyến cáo ranh giới y tế: CLARA là công cụ hỗ trợ thông tin và đối chiếu bằng chứng, không thay thế quyền ra y lệnh của bác sĩ có chứng chỉ hành nghề.",
      "Tuân thủ nghiêm ngặt Điều 15 Luật Khám bệnh, chữa bệnh số 15/2023/QH15 và Luật AI số 134/2025/QH15.",
    ],
  },
  {
    tier: "Tầng 3",
    title: "Hệ thống Xác thực Dược lý FIDES (Drug Interaction & Dosage Guard)",
    badge: "FIDES Engine",
    badgeTone: "brand" as const,
    icon: "check",
    summary:
      "Ma trận xác thực thuốc xác định tương tác thuốc bất lợi (DDI), kiểm tra chống chỉ định và giới hạn liều an toàn.",
    details: [
      "Bóc tách từng tuyên bố dược lý thành các bộ tham số chuẩn hóa (Hoạt chất, Đường dùng, Liều tối đa/24h, Khoảng cách liều).",
      "Đối chiếu chéo tự động với kho dữ liệu Dược thư Quốc gia Việt Nam 2022 và DrugBank v5.1+ với hơn 450,000 cặp tương tác thuốc.",
      "Nguyên tắc Fail-Closed: Bất kỳ khuyến nghị nào vi phạm cảnh báo mức độ CRITICAL (chống chỉ định tuyệt đối) sẽ bị chặn ngay lập tức trước khi hiển thị cho người dùng.",
    ],
  },
  {
    tier: "Tầng 4",
    title: "Hội chẩn Đa tác tử & Neo giữ Y văn (Multi-Agent Council & Grounding)",
    badge: "Living Evidence",
    badgeTone: "ok" as const,
    icon: "progress",
    summary:
      "Mô phỏng hội đồng chuyên môn đa chuyên khoa với cơ chế phản biện chéo nhằm loại trừ điểm mù và triệt tiêu ảo giác tri thức.",
    details: [
      "Phân rã ca bệnh cho các tác tử chuyên khoa (Nội khoa, Tim mạch, Dược lâm sàng, Y học cổ truyền) phân tích độc lập.",
      "Chỉ sử dụng ngữ cảnh RAG được truy xuất từ các hướng dẫn điều trị của Bộ Y Tế, PubMed/MEDLINE và cơ sở dữ liệu Living Evidence đã qua thẩm định.",
      "Áp dụng chuẩn Zero-CoT (Zero Chain-of-Thought Retention): toàn bộ chuỗi suy luận nội bộ được tiêu hủy ngay sau phiên làm việc, không lưu trữ vĩnh viễn.",
    ],
  },
  {
    tier: "Tầng 5",
    title: "Giám sát & Xác nhận Chuyên môn Bác sĩ (Human-In-The-Loop Sign-Off)",
    badge: "Bác sĩ kiểm duyệt",
    badgeTone: "neutral" as const,
    icon: "user-card",
    summary:
      "Mọi quyết định can thiệp điều trị, thay đổi thuốc hay ghi nhận hồ sơ bệnh án bắt buộc phải do bác sĩ kiểm duyệt và ký duyệt.",
    details: [
      "Bản nháp tóm tắt bệnh án từ Trợ lý Scribe luôn ở trạng thái 'Chờ duyệt' (Draft / Unconfirmed) cho đến khi bác sĩ chỉnh sửa và xác nhận.",
      "Các đề xuất bổ sung thuốc vào hồ sơ điều trị (Medication Course) yêu cầu thao tác xác nhận chủ động từ phía người dùng hoặc bác sĩ phụ trách.",
      "Lưu vết kiểm toán bất biến (Immutable Audit Ledger) cho mọi thao tác can thiệp dữ liệu lâm sàng.",
    ],
  },
];

const SAFETY_INVARIANTS = [
  {
    title: "1. Nguyên tắc Fail-Closed (Đóng khi nghi ngờ)",
    desc: "Khi gặp lỗi mạng, dịch vụ suy giảm hoặc xung đột dữ liệu dược lực học không thể giải quyết, hệ thống luôn chọn phương án an toàn nhất: cảnh báo người dùng và từ chối đưa ra suy luận không chắc chắn.",
  },
  {
    title: "2. Chuẩn Zero-PII Telemetry",
    desc: "Toàn bộ hệ thống giám sát hiệu năng, log sự kiện và số liệu vận hành tuyệt đối không chứa thông tin định danh cá nhân (tên, số điện thoại, đơn thuốc cá nhân, nội dung hội thoại tự do).",
  },
  {
    title: "3. Bảo mật Chuỗi Suy luận Zero-CoT",
    desc: "Các bước suy luận nháp (Chain-of-Thought) của mô hình ngôn ngữ lớn được xử lý trong môi trường bộ nhớ cô lập và hủy ngay sau khi trả lời, ngăn ngừa việc rò rỉ dữ liệu hoặc học vẹt dữ liệu nhạy cảm.",
  },
  {
    title: "4. Phân quyền RBAC Thẩm quyền Cứng",
    desc: "Các tính năng chuyên môn sâu (Hội chẩn Council, Trợ lý Scribe, Quản trị nguồn tri thức) được kiểm soát nghiêm ngặt bằng cơ chế kiểm tra quyền hạn (Role-Based Access Control) tại Gateway API.",
  },
];

export default function SafetyManifestoPage() {
  return (
    <div
      className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      data-shell-mode="PUBLIC_LEGAL"
      data-layout-archetype="Safety Manifesto"
    >
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-14 lg:px-8 space-y-12">
        {/* 1. Header */}
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
                href="/sources"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="folder" size="1rem" />
                <span>Danh mục nguồn y văn</span>
              </Link>
              <Link
                href="/legal/consent"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="clinical-notes" size="1rem" />
                <span>Đồng thuận y tế</span>
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
              The Clara Care · Clinical Safety & Verification Framework
            </p>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Tuyên ngôn An toàn Lâm sàng & Hàng rào Bảo vệ Đa tầng
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              An toàn của người bệnh là kim chỉ nam bất biến trong mọi dòng mã và thuật toán của The Clara Care.
              Chúng tôi kết hợp trí tuệ nhân tạo tiên tiến với các hàng rào kiểm định dược lý tất định (deterministic guards)
              nhằm triệt tiêu ảo giác và bảo vệ ranh giới chuyên môn y khoa.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Badge tone="brand" icon="check">
              Xác thực FIDES v2.4
            </Badge>
            <Badge tone="ok" icon="warning">
              Chuẩn Zero-CoT & Zero-PII
            </Badge>
            <Badge tone="neutral" icon="clinical-notes">
              Luật Khám bệnh 2023 (Luật 15/2023)
            </Badge>
            <Badge tone="neutral" icon="folder">
              {LEGAL_PRIMARY_DOMAIN} · {LEGAL_POLICY_VERSION}
            </Badge>
          </div>
        </header>

        {/* 2. Emergency Notice */}
        <section aria-label="Cảnh báo cấp cứu">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/25 p-5 sm:p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-[var(--status-danger-text)] font-bold text-sm">
                <Icon name="warning" size="1.1rem" />
                <span className="uppercase tracking-wider">Cấp cứu y tế khẩn cấp:</span>
              </div>
              <p className="text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed max-w-2xl">
                Nếu gặp các dấu hiệu nguy kịch (đau ngực dữ dội, khó thở cấp, tai biến mạch máu não, co giật, hôn mê),
                vui lòng không sử dụng AI để tra cứu mà hãy liên hệ ngay dịch vụ y tế khẩn cấp.
              </p>
            </div>
          <a
            href="tel:115"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-4 py-2 text-xs font-bold text-[var(--status-danger-text)] shadow-sm hover:brightness-110 transition active:scale-95"
          >
            <Icon name="emergency" size="1rem" />
            <span>GỌI NGAY CẤP CỨU 115</span>
          </a>
          </div>
        </section>

        {/* 3. The 5 Clinical Safety Tiers */}
        <section className="space-y-6" aria-labelledby="safety-tiers-heading">
          <div className="space-y-2 border-b border-[color:var(--shell-border)]/60 pb-3">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="progress" size="1.25rem" />
              <h2
                id="safety-tiers-heading"
                className="text-lg sm:text-xl font-bold tracking-tight text-[var(--text-primary)]"
              >
                Khung 5 Tầng An toàn Lâm sàng (5-Tier Safety Architecture)
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              Mỗi yêu cầu và câu trả lời trong hệ thống đều phải vượt qua 5 lớp phòng vệ tuần tự trước khi đến tay người dùng:
            </p>
          </div>

          <div className="space-y-4">
            {SAFETY_TIERS.map((tier) => (
              <div
                key={tier.tier}
                className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-4 shadow-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-black uppercase tracking-wider text-[var(--text-brand)]">
                      {tier.tier}
                    </span>
                    <span className="text-[var(--text-muted)]">·</span>
                    <h3 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
                      {tier.title}
                    </h3>
                  </div>
                  <Badge tone={tier.badgeTone}>{tier.badge}</Badge>
                </div>

                <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                  {tier.summary}
                </p>

                <div className="rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/50 p-4 space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    Cơ chế bảo vệ kỹ thuật:
                  </span>
                  <ul className="list-disc space-y-1.5 pl-4 text-xs text-[var(--text-secondary)] leading-relaxed">
                    {tier.details.map((detail, idx) => (
                      <li key={idx}>{detail}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Deep Dive: FIDES Verification Matrix */}
        <section className="space-y-4" aria-labelledby="fides-matrix-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="check" size="1.25rem" />
            <h2
              id="fides-matrix-heading"
              className="text-lg sm:text-xl font-bold tracking-tight text-[var(--text-primary)]"
            >
              Hệ thống Xác minh Dược lâm sàng FIDES (Verification Matrix)
            </h2>
          </div>

          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-500)]/30 bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm">
            <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
              FIDES (Fast & Interpretable Drug Evidence Synthesis) là động cơ xác thực tất định hoạt động song song
              với mô hình ngôn ngữ lớn. Thay vì tin cậy tuyệt đối vào xác suất sinh từ của LLM, FIDES bóc tách mọi
              tuyên bố liên quan đến thuốc thành cấu trúc toán học để kiểm tra chéo:
            </p>

            <div className="grid gap-4 sm:grid-cols-3 text-xs">
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-[var(--text-brand)] font-bold">
                  <Icon name="scan" size="1rem" />
                  <span>1. Bóc tách Tuyên bố</span>
                </div>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Tự động trích xuất tên hoạt chất, liều lượng (mg/ml), đường dùng và nhóm bệnh nhân chỉ định.
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-[var(--status-ok-text)] font-bold">
                  <Icon name="progress" size="1rem" />
                  <span>2. Đối chiếu Y văn Số hóa</span>
                </div>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Kiểm tra chéo với hơn 450,000 tương tác DrugBank v5.1+ và chuyên luận Dược thư Quốc gia VN 2022.
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-[var(--status-danger-text)] font-bold">
                  <Icon name="warning" size="1rem" />
                  <span>3. Ngắt mạch An toàn (Kill-Switch)</span>
                </div>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Tự động chặn câu trả lời nếu phát hiện nguy cơ quá liều độc tính hoặc tương tác thuốc mức độ CRITICAL.
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-[color:var(--status-ok-border)]/70 bg-[var(--status-ok-bg)]/20 p-4 text-xs text-[var(--status-ok-text)] leading-relaxed">
              <strong>Cam kết không ảo giác (Zero-Hallucination Guard):</strong> Mọi khuyến cáo điều trị bắt buộc phải có
              mã định danh trích dẫn y văn (Citation ID) trỏ tới tài liệu nguồn có thật. Nếu không tìm thấy bằng chứng phù hợp,
              hệ thống sẽ thông báo rõ ràng rằng chưa có đủ dữ liệu lâm sàng tin cậy.
            </div>
          </div>
        </section>

        {/* 5. Safety Invariants & Engineering Guarantees */}
        <section className="space-y-4" aria-labelledby="invariants-heading">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="clinical-notes" size="1.25rem" />
            <h2
              id="invariants-heading"
              className="text-lg sm:text-xl font-bold tracking-tight text-[var(--text-primary)]"
            >
              Các nguyên tắc Bất biến trong Kỹ thuật (Safety Invariants)
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {SAFETY_INVARIANTS.map((inv) => (
              <div
                key={inv.title}
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-2 shadow-sm"
              >
                <h3 className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                  {inv.title}
                </h3>
                <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                  {inv.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* 6. Navigation Footer */}
        <section className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-4">
          <h3 className="text-sm font-bold text-[var(--text-primary)]">
            Tìm hiểu thêm về Chuẩn mực & Nguồn dữ liệu của The Clara Care
          </h3>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Chúng tôi công khai toàn bộ danh mục tài liệu y khoa tham chiếu và các điều khoản đồng thuận để người dùng
            và cộng đồng y tế dễ dàng tra cứu, kiểm chứng.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              href="/sources"
              className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--brand-600)] px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-[var(--brand-700)] transition"
            >
              <Icon name="folder" size="0.9rem" />
              <span>Khám phá Danh mục nguồn y văn</span>
            </Link>
            <Link
              href="/legal/consent"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition"
            >
              <Icon name="clinical-notes" size="0.9rem" />
              <span>Xem Thỏa thuận đồng thuận y tế</span>
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-2 text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition"
            >
              <Icon name="contact" size="0.9rem" />
              <span>Liên hệ Ban cố vấn y khoa</span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
