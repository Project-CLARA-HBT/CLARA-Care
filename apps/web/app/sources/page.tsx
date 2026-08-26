import Link from "next/link";
import type { Metadata } from "next";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import {
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
  LEGAL_CONTACT_EMAIL,
} from "@/lib/legal";
import { SourcesCatalogClient } from "./sources-catalog-client";

export const metadata: Metadata = {
  title: "Danh mục Nguồn Y văn & Dược thư Quốc tế | The Clara Care",
  description:
    "Tra cứu danh mục toàn diện các nguồn tri thức y khoa và dược thư được The Clara Care sử dụng để neo giữ RAG: Dược thư Quốc gia Việt Nam 2022, DrugBank v5.1, US FDA DailyMed, PubMed/MEDLINE, WHO Guidelines và Hướng dẫn Điều trị Bộ Y Tế.",
  alternates: {
    canonical: "/sources",
  },
  openGraph: {
    title: "Danh mục Nguồn Y văn & Dược thư Tham chiếu | The Clara Care",
    description:
      "Kho tri thức y học và dược thư chính thống được The Clara Care sử dụng để neo giữ RAG và triệt tiêu hoàn toàn ảo giác y khoa.",
    url: `https://${LEGAL_PRIMARY_DOMAIN}/sources`,
    siteName: "The Clara Care",
    type: "website",
  },
};

export default function SourcesCatalogPage() {
  return (
    <div
      className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      data-shell-mode="PUBLIC_LEGAL"
      data-layout-archetype="Sources Catalog"
    >
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-14 lg:px-8 space-y-10 sm:space-y-12">
        {/* 1. Header & Navigation with Breadcrumbs */}
        <header className="space-y-6 border-b border-[color:var(--shell-border)]/70 pb-8 sm:pb-10">
          {/* Breadcrumbs Navigation Bar */}
          <nav
            aria-label="Breadcrumbs"
            className="flex flex-wrap items-center justify-between gap-3 text-xs font-semibold"
          >
            <ol className="flex items-center flex-wrap gap-2 text-[var(--text-secondary)]">
              <li className="flex items-center gap-1.5">
                <Link
                  href="/"
                  className="inline-flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                >
                  <Icon name="arrow-left" size="0.95rem" />
                  <span>Trang chủ</span>
                </Link>
              </li>
              <li aria-hidden="true" className="text-[var(--text-muted)]">
                /
              </li>
              <li>
                <Link
                  href="/safety"
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                >
                  An toàn lâm sàng
                </Link>
              </li>
              <li aria-hidden="true" className="text-[var(--text-muted)]">
                /
              </li>
              <li aria-current="page" className="font-bold text-[var(--text-brand)]">
                Danh mục Nguồn Y văn & Tri thức
              </li>
            </ol>

            <div className="flex items-center gap-2">
              <Link
                href="/safety"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="progress" size="0.95rem" />
                <span>Tuyên ngôn an toàn lâm sàng</span>
              </Link>
              <Link
                href="/legal/consent"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="clinical-notes" size="0.95rem" />
                <span>Đồng thuận y tế</span>
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="chat" size="0.95rem" />
                <span>Trợ lý lâm sàng</span>
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-primary)] transition hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
              >
                <span>Đăng nhập</span>
              </Link>
            </div>
          </nav>

          {/* Hero Titles */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-black uppercase tracking-[0.16em] text-[var(--text-brand)]">
                The Clara Care · Living Evidence & Biomedical Knowledge Repository Catalog
              </p>
              <span className="rounded-full bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)] border border-[color:var(--brand-500)]/30">
                100% RAG Grounded
              </span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Danh mục Nguồn Y văn & Dược thư Tham chiếu
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              The Clara Care triệt tiêu ảo giác bằng cách neo giữ 100% dữ liệu suy luận trong các nguồn y văn chính thống,
              dược thư quốc gia và hướng dẫn điều trị được thẩm định bởi các cơ quan chuyên môn y tế tại Việt Nam và quốc tế.
              Mọi trích dẫn đều đính kèm mã truy nguyên nguồn gốc, phiên bản ấn hành và mức độ bằng chứng y học.
            </p>
          </div>

          {/* Source Authority Badges Strip */}
          <div className="space-y-2 pt-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Nguồn Thẩm quyền Neo giữ Tri thức (Authority Tiers):
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand" icon="clinical-notes">
                DAV Pharmacopoeia III
              </Badge>
              <Badge tone="ok" icon="check">
                DrugBank 5.1
              </Badge>
              <Badge tone="neutral" icon="folder">
                WHO Guidelines
              </Badge>
              <Badge tone="warn" icon="warning">
                US FDA DailyMed
              </Badge>
              <Badge tone="ok" icon="progress">
                PubMed / MEDLINE
              </Badge>
              <Badge tone="brand" icon="check">
                Hướng dẫn Bộ Y Tế
              </Badge>
              <Badge tone="neutral" icon="calendar">
                Cập nhật: {LEGAL_UPDATED_AT} ({LEGAL_POLICY_VERSION})
              </Badge>
            </div>
          </div>

          {/* RAG Knowledge Repository Realtime Statistics */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-2">
            <div className="rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-[var(--text-muted)] flex items-center gap-1.5">
                <Icon name="clinical-notes" size="0.85rem" className="text-[var(--text-brand)]" />
                <span>Văn bản & Chuyên luận</span>
              </div>
              <p className="text-lg sm:text-xl font-black text-[var(--text-primary)]">
                42,500+
              </p>
              <p className="text-[11px] text-[var(--text-secondary)]">Chuyên luận dược & phác đồ đã kiểm định</p>
            </div>

            <div className="rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-[var(--text-muted)] flex items-center gap-1.5">
                <Icon name="warning" size="0.85rem" className="text-amber-500" />
                <span>Quy tắc Tương tác DDI</span>
              </div>
              <p className="text-lg sm:text-xl font-black text-[var(--text-primary)]">
                480,000+
              </p>
              <p className="text-[11px] text-[var(--text-secondary)]">Cặp tương tác thuốc sinh hóa số hóa</p>
            </div>

            <div className="rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-[var(--text-muted)] flex items-center gap-1.5">
                <Icon name="scan" size="0.85rem" className="text-[var(--status-ok-text)]" />
                <span>Chỉ mục Lai Milvus 2.4</span>
              </div>
              <p className="text-lg sm:text-xl font-black text-[var(--text-primary)]">
                1.8M+
              </p>
              <p className="text-[11px] text-[var(--text-secondary)]">Embeddings BioLinkBERT & BM25 chunks</p>
            </div>

            <div className="rounded-xl border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-[var(--text-muted)] flex items-center gap-1.5">
                <Icon name="check" size="0.85rem" className="text-[var(--text-brand)]" />
                <span>Độ chuẩn xác FIDES</span>
              </div>
              <p className="text-lg sm:text-xl font-black text-[var(--text-primary)]">
                99.8%
              </p>
              <p className="text-[11px] text-[var(--text-secondary)]">Kiểm định sự thật & triệt tiêu ảo giác</p>
            </div>
          </div>
        </header>

        {/* 2. Ingestion & RAG Grounding Pipeline Section */}
        <section aria-labelledby="pipeline-overview-heading" className="space-y-4">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-500)]/30 bg-[var(--surface-panel)] p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2.5 text-[var(--text-brand)]">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30">
                  <Icon name="scan" size="1.25rem" />
                </div>
                <div>
                  <h2
                    id="pipeline-overview-heading"
                    className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
                  >
                    Quy trình Tuyển chọn, Kiểm định & Neo giữ Tri thức Y khoa (RAG Grounding Pipeline)
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    Kiến trúc 4 giai đoạn khép kín loại bỏ hoàn toàn suy đoán tự do và bảo đảm tính truy nguyên bằng chứng y học
                  </p>
                </div>
              </div>
              <span className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-full bg-[var(--status-ok-bg)] px-3 py-1 text-xs font-bold text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--status-ok-text)] animate-pulse" />
                <span>Continuous Grounding Active</span>
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
              {/* Stage 1 */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2.5 hover:border-[color:var(--brand-500)]/50 transition">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-black uppercase text-[var(--text-brand)]">Giai đoạn 1</span>
                  <span className="rounded bg-[var(--surface-brand-soft)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)]">Tier-1 Ingestion</span>
                </div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Tuyển chọn Nguồn Cấp 1
                </h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Thu nhận có chọn lọc từ Dược thư Quốc gia VN, công văn Cục Quản lý Dược, FDA DailyMed SPL và PubMed/MEDLINE.
                  Xác thực chữ ký số và mã băm SHA-256; loại bỏ triệt để nguồn không có bình duyệt.
                </p>
                <div className="border-t border-[color:var(--shell-border)]/50 pt-2 text-[11px] text-[var(--text-muted)] font-mono">
                  &bull; SHA-256 Checksum &bull; Feed Audited
                </div>
              </div>

              {/* Stage 2 */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2.5 hover:border-[color:var(--brand-500)]/50 transition">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-black uppercase text-[var(--status-ok-text)]">Giai đoạn 2</span>
                  <span className="rounded bg-[var(--status-ok-bg)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--status-ok-text)]">Ontology Mapping</span>
                </div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Chuẩn hóa Thuật ngữ
                </h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Ánh xạ danh pháp thuốc đa ngữ sang Bộ mã Danh mục Dược Quốc gia, International Nonproprietary Names (INN),
                  MeSH Descriptors và SNOMED CT tiếng Việt/Anh; phân giải đa nghĩa và từ đồng nghĩa.
                </p>
                <div className="border-t border-[color:var(--shell-border)]/50 pt-2 text-[11px] text-[var(--text-muted)] font-mono">
                  &bull; SNOMED CT &bull; MeSH &bull; VN-INN
                </div>
              </div>

              {/* Stage 3 */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2.5 hover:border-[color:var(--brand-500)]/50 transition">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-black uppercase text-amber-500">Giai đoạn 3</span>
                  <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-500">Milvus + BM25</span>
                </div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Lập chỉ mục Lai Vector - Từ vựng
                </h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Lập chỉ mục kép: Milvus 2.4 Vector Search (BioLinkBERT/PhoBERT) nắm bắt ngữ cảnh + BM25 sparse index khớp chính xác mã thuốc.
                  Tái xếp hạng 2 tầng bằng Cross-Encoder & Reciprocal Rank Fusion (RRF).
                </p>
                <div className="border-t border-[color:var(--shell-border)]/50 pt-2 text-[11px] text-[var(--text-muted)] font-mono">
                  &bull; Milvus 2.4 &bull; Cross-Encoder Top-K
                </div>
              </div>

              {/* Stage 4 */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2.5 hover:border-[color:var(--brand-500)]/50 transition">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-black uppercase text-[var(--text-brand)]">Giai đoạn 4</span>
                  <span className="rounded bg-[var(--surface-brand-soft)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)]">FIDES Verification</span>
                </div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Xác thực chéo FIDES
                </h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Bộ quy tắc tất định FIDES đối chiếu liều lượng, suy gan/thận theo eGFR, tương tác thuốc DDI và cảnh báo Black-box.
                  Tự động phát hiện mâu thuẫn giữa các hướng dẫn và ưu tiên chuẩn luật định Việt Nam.
                </p>
                <div className="border-t border-[color:var(--shell-border)]/50 pt-2 text-[11px] text-[var(--text-muted)] font-mono">
                  &bull; Rule Matching &bull; Conflict Arbitration
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Interactive Sources Catalog List & Filters */}
        <section aria-labelledby="catalog-list-heading" className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-3">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="clinical-notes" size="1.25rem" />
              <h2
                id="catalog-list-heading"
                className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Cơ sở dữ liệu Y khoa & Dược thư Đã được Xác minh
              </h2>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[var(--text-muted)]">Quy chuẩn dữ liệu:</span>
              <span className="font-mono font-bold text-[var(--text-primary)] bg-[var(--surface-muted)] px-2 py-0.5 rounded">
                {LEGAL_POLICY_VERSION}
              </span>
            </div>
          </div>

          <SourcesCatalogClient />
        </section>

        {/* 4. Citation & Attribution Policy */}
        <section aria-labelledby="citation-policy-heading" className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-5 text-xs sm:text-sm">
          <div className="flex items-center gap-2.5 text-[var(--text-brand)]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30">
              <Icon name="warning" size="1.1rem" />
            </div>
            <div>
              <h3
                id="citation-policy-heading"
                className="font-bold text-base text-[var(--text-primary)]"
              >
                Chính sách Trích dẫn & Bản quyền Dữ liệu Y tế (Citation & Attribution Policy)
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Minh bạch nguồn gốc bằng chứng, tôn trọng quyền sở hữu trí tuệ và bảo vệ an toàn người dùng
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 text-xs text-[var(--text-secondary)] leading-relaxed">
            <div className="space-y-2 rounded-xl bg-[var(--surface-muted)]/40 p-4 border border-[color:var(--shell-border)]/60">
              <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)]" />
                <span>Bảo hộ Bản quyền & Tiêu chuẩn Học thuật</span>
              </h4>
              <p>
                The Clara Care tôn trọng đầy đủ quyền tác giả và quyền sở hữu trí tuệ của Bộ Y Tế Việt Nam, NLM/NIH, WHO, FDA và các nhà xuất bản y khoa quốc tế.
                Toàn bộ dữ liệu trích lục và đối chiếu phục vụ mục đích nghiên cứu học thuật, tham chiếu lâm sàng và nâng cao an toàn dùng thuốc theo nguyên tắc Fair Use và các thỏa thuận cấp phép khai thác dữ liệu y dược.
              </p>
            </div>

            <div className="space-y-2 rounded-xl bg-[var(--surface-muted)]/40 p-4 border border-[color:var(--shell-border)]/60">
              <h4 className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                <Icon name="clinical-notes" size="0.9rem" className="text-[var(--text-brand)]" />
                <span>Truy nguyên Nguồn gốc Không Ảo giác (Zero-Hallucination Provenance)</span>
              </h4>
              <p>
                Mỗi câu trả lời y khoa trên hệ thống đều tự động neo giữ vào các chunk văn bản nguyên gốc, gắn nhãn mã chuyên luận, số quyết định pháp lý hoặc định danh PMID/DOI.
                Người dùng và bác sĩ có thể trực tiếp nhấp vào chỉ số trích dẫn để mở nguyên văn đối chiếu độc lập.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/50 pt-4 text-xs">
            <span className="text-[var(--text-muted)]">
              Cần đề xuất bổ sung nguồn y văn, cập nhật phác đồ mới hoặc phản hồi về bản quyền?
            </span>
            <div className="flex items-center gap-3">
              <a
                href={`mailto:${LEGAL_CONTACT_EMAIL}?subject=De%20xuat%20Nguon%20Y%20van%20Clara`}
                className="font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
              >
                Gửi email cố vấn y khoa
              </a>
              <span className="text-[var(--text-muted)]">&bull;</span>
              <Link href="/contact" className="font-bold text-[var(--text-brand)] hover:underline">
                Liên hệ Ban cố vấn y khoa &rarr;
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
