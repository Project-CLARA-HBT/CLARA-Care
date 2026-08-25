import Link from "next/link";
import type { Metadata } from "next";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import {
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";
import { SourcesCatalogClient } from "./sources-catalog-client";

export const metadata: Metadata = {
  title: "Danh mục Nguồn Y văn & Dược thư Quốc tế | The Clara Care",
  description:
    "Tra cứu danh mục toàn diện các nguồn tri thức y khoa và dược thư được The Clara Care sử dụng để neo giữ RAG: Dược thư Quốc gia Việt Nam 2022, DrugBank, US FDA DailyMed, PubMed/MEDLINE và Hướng dẫn Bộ Y Tế.",
};

export default function SourcesCatalogPage() {
  return (
    <div
      className="min-h-[100dvh] bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      data-shell-mode="PUBLIC_LEGAL"
      data-layout-archetype="Sources Catalog"
    >
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-14 lg:px-8 space-y-10 sm:space-y-12">
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
                href="/safety"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="progress" size="1rem" />
                <span>Tuyên ngôn an toàn lâm sàng</span>
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
              The Clara Care · Living Evidence & Knowledge Repository Catalog
            </p>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Danh mục Nguồn Y văn & Dược thư Tham chiếu
            </h1>
            <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              The Clara Care triệt tiêu ảo giác bằng cách neo giữ 100% dữ liệu suy luận trong các nguồn y văn chính thống,
              dược thư quốc gia và hướng dẫn điều trị được thẩm định bởi các cơ quan chuyên môn y tế tại Việt Nam và quốc tế.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Badge tone="brand" icon="clinical-notes">
              Dược thư Quốc gia VN 2022
            </Badge>
            <Badge tone="ok" icon="check">
              DrugBank v5.1+
            </Badge>
            <Badge tone="warn" icon="folder">
              US FDA DailyMed
            </Badge>
            <Badge tone="neutral" icon="progress">
              PubMed / MEDLINE
            </Badge>
            <Badge tone="brand" icon="check">
              Hướng dẫn Bộ Y Tế
            </Badge>
            <Badge tone="neutral" icon="calendar">
              {LEGAL_UPDATED_AT}
            </Badge>
          </div>
        </header>

        {/* 2. Ingestion & RAG Grounding Pipeline Card */}
        <section aria-labelledby="pipeline-overview-heading" className="space-y-3">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-500)]/30 bg-[var(--surface-panel)] p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="scan" size="1.25rem" />
              <h2
                id="pipeline-overview-heading"
                className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Quy trình Tuyển chọn, Kiểm định & Neo giữ Tri thức Y khoa (RAG Grounding)
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
              Mọi tài liệu trong kho tri thức của The Clara Care đều trải qua quy trình 4 bước thẩm định nghiêm ngặt:
            </p>

            <div className="grid gap-4 sm:grid-cols-4 text-xs">
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-1.5">
                <span className="font-mono text-[11px] font-black uppercase text-[var(--text-brand)]">Bước 1</span>
                <h3 className="font-bold text-[var(--text-primary)]">Tuyển chọn Nguồn Cấp 1</h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Chỉ thu thập từ các ấn bản luật định, dược thư quốc gia và tài liệu có phản biện bình duyệt.
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-1.5">
                <span className="font-mono text-[11px] font-black uppercase text-[var(--status-ok-text)]">Bước 2</span>
                <h3 className="font-bold text-[var(--text-primary)]">Chuẩn hóa Thuật ngữ</h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Ánh xạ danh pháp thuốc và triệu chứng theo Bộ mã Danh mục Dược Quốc gia & chuẩn MeSH/SNOMED.
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-1.5">
                <span className="font-mono text-[11px] font-black uppercase text-amber-500">Bước 3</span>
                <h3 className="font-bold text-[var(--text-primary)]">Lập chỉ mục Vector</h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Tạo embedding đoạn văn y khoa với độ trễ thấp và gắn nhãn bản quyền, phiên bản, ngày ban hành.
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-1.5">
                <span className="font-mono text-[11px] font-black uppercase text-[var(--text-brand)]">Bước 4</span>
                <h3 className="font-bold text-[var(--text-primary)]">Xác thực chéo FIDES</h3>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  Đối chiếu tự động giữa khuyến cáo và dữ liệu dược lý để loại bỏ hoàn toàn các sai số liều lượng.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Interactive Sources Catalog List & Filters */}
        <section aria-labelledby="catalog-list-heading" className="space-y-4">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <div className="flex items-center gap-2 text-[var(--text-brand)]">
              <Icon name="clinical-notes" size="1.25rem" />
              <h2
                id="catalog-list-heading"
                className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Cơ sở dữ liệu Y khoa & Dược thư Đã được Xác minh
              </h2>
            </div>
            <span className="text-xs font-medium text-[var(--text-muted)]">
              {LEGAL_POLICY_VERSION}
            </span>
          </div>

          <SourcesCatalogClient />
        </section>

        {/* 4. Statutory Disclaimer & Citation Policy */}
        <section className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-8 space-y-4 text-xs sm:text-sm">
          <div className="flex items-center gap-2 text-[var(--text-brand)]">
            <Icon name="warning" size="1.1rem" />
            <h3 className="font-bold text-[var(--text-primary)]">
              Chính sách Trích dẫn & Bản quyền Dữ liệu Y tế
            </h3>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Các tài liệu và nguồn y văn được liệt kê trên đây phục vụ mục đích tra cứu học thuật, đối chiếu lâm sàng
            và nâng cao an toàn dùng thuốc. The Clara Care tôn trọng đầy đủ quyền sở hữu trí tuệ của các cơ quan ban hành,
            nhà xuất bản và tổ chức y tế quốc tế. Mọi trích dẫn tự động trong hệ thống đều đính kèm mã định danh nguồn gốc
            để đảm bảo tính minh bạch và truy nguyên bằng chứng y khoa.
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/50 pt-3 text-xs">
            <span className="text-[var(--text-muted)]">
              Cần đề xuất bổ sung nguồn y văn hoặc báo cáo cập nhật chuyên môn?
            </span>
            <Link href="/contact" className="font-bold text-[var(--text-brand)] hover:underline">
              Liên hệ Ban cố vấn y khoa &rarr;
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
