"use client";

import { useState, useMemo } from "react";
import { Icon } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";

export type SourceCategory = "all" | "pharmacopoeia" | "guidelines" | "regulatory" | "literature" | "global";

export interface MedicalSourceItem {
  id: string;
  name: string;
  shortName: string;
  authority: string;
  country: string;
  version: string;
  category: Exclude<SourceCategory, "all">;
  categoryLabel: string;
  badgeTone: BadgeTone;
  evidenceGrade: string;
  updateFrequency: string;
  scope: string;
  keyTopics: string[];
  attribution: string;
  status: "active" | "live_sync" | "verified";
  citationExample: string;
}

const MEDICAL_SOURCES: MedicalSourceItem[] = [
  {
    id: "duoc-thu-vn-2022",
    name: "Dược thư Quốc gia Việt Nam",
    shortName: "Dược thư Quốc gia VN 2022",
    authority: "Hội đồng Dược thư Quốc gia — Bộ Y Tế Việt Nam",
    country: "Việt Nam (VN)",
    version: "Tái bản lần thứ III (2022) & Bổ sung",
    category: "pharmacopoeia",
    categoryLabel: "Dược thư Quốc gia",
    badgeTone: "brand",
    evidenceGrade: "Hạng A (Statutory National Standard)",
    updateFrequency: "Hàng quý & theo công văn Cục Quản lý Dược",
    scope: "Tiêu chuẩn chuyên luận thuốc lưu hành tại Việt Nam: Liều dùng người lớn & trẻ em, hiệu chỉnh liều suy gan/thận, đường dùng, tương tác, chống chỉ định phụ nữ mang thai & cho con bú.",
    keyTopics: ["Chuyên luận thuốc", "Liều chuẩn VN", "Chống chỉ định thai kỳ", "Hiệu chỉnh suy thận"],
    attribution: "Bản quyền thuộc Bộ Y Tế Việt Nam. Dữ liệu được số hóa và chuẩn hóa thuật ngữ lâm sàng.",
    status: "verified",
    citationExample: "Dược thư Quốc gia Việt Nam 2022, Chuyên luận 'Metformin hydrochloride', tr. 982-985.",
  },
  {
    id: "drugbank-v5",
    name: "DrugBank Comprehensive Pharmacoinformatics Database",
    shortName: "DrugBank Online v5.1+",
    authority: "OMx Personal Health Analytics / Đại học Alberta (Canada)",
    country: "Quốc tế / Canada",
    version: "DrugBank Database Core v5.1.12 (2026)",
    category: "pharmacopoeia",
    categoryLabel: "Cơ sở dữ liệu Dược học",
    badgeTone: "ok",
    evidenceGrade: "Hạng A (Gold Standard Pharmacoinformatics)",
    updateFrequency: "Đồng bộ API tự động",
    scope: "Hơn 14,000 hoạt chất dược lý, 450,000+ cặp tương tác thuốc bất lợi (DDI), cơ chế tác dụng sinh học (MoA), chuyển hóa qua enzym Cytochrome P450, và chỉ số nguy cơ tim mạch/độc tính.",
    keyTopics: ["Tương tác thuốc DDI", "Cơ chế MoA", "Enzym CYP450", "Dược động học PK/PD"],
    attribution: "Tích hợp theo thỏa thuận giấy phép chuyên ngành y dược DrugBank Clinical Suite.",
    status: "live_sync",
    citationExample: "DrugBank Online Database (v5.1.12), Accession Number DB00331 (Metformin), 2026.",
  },
  {
    id: "moh-vn-guidelines",
    name: "Hướng dẫn Chẩn đoán và Điều trị của Bộ Y Tế Việt Nam",
    shortName: "Hướng dẫn Điều trị Bộ Y Tế",
    authority: "Cục Quản lý Khám, chữa bệnh — Bộ Y Tế",
    country: "Việt Nam (VN)",
    version: "Quyết định Bộ Y Tế (2020 - 2026)",
    category: "guidelines",
    categoryLabel: "Phác đồ Bộ Y Tế",
    badgeTone: "brand",
    evidenceGrade: "Hạng A (Quy chuẩn thực hành lâm sàng quốc gia)",
    updateFrequency: "Ngay khi có Quyết định mới của Bộ Y Tế",
    scope: "Phác đồ điều trị chính thức áp dụng tại tất cả các bệnh viện từ tuyến trung ương đến cơ sở: Tim mạch, Đái tháo đường Type 2, Đột quỵ, COPD, Hen phế quản, Sốt xuất huyết Dengue, Viêm gan B/C.",
    keyTopics: ["Phác đồ quốc gia", "Bệnh không lây nhiễm", "Tim mạch & ĐTĐ", "Nhiễm khuẩn & Kháng sinh"],
    attribution: "Công bố chính thức bởi Cục Quản lý Khám, chữa bệnh — Bộ Y Tế Việt Nam.",
    status: "verified",
    citationExample: "Quyết định số 5481/QĐ-BYT ngày 30/12/2020 về Hướng dẫn chẩn đoán và điều trị Đái tháo đường typ 2.",
  },
  {
    id: "us-fda-dailymed",
    name: "US FDA DailyMed & National Drug Code Directory",
    shortName: "US FDA DailyMed / NDC",
    authority: "U.S. Food and Drug Administration (FDA) & NLM",
    country: "Hoa Kỳ (US)",
    version: "Structured Product Labeling (SPL) DailyMed Live Feed",
    category: "regulatory",
    categoryLabel: "Cơ quan Quản lý Dược",
    badgeTone: "warn",
    evidenceGrade: "Hạng A (Regulatory Authority Standard)",
    updateFrequency: "Cập nhật hàng tuần",
    scope: "Hơn 150,000 nhãn thuốc được FDA cấp phép, cảnh báo hộp đen (Black Box Warnings), thông báo thu hồi thuốc khẩn cấp, tương đương sinh học và dữ liệu cảnh giác dược (Pharmacovigilance).",
    keyTopics: ["Nhãn thuốc FDA", "Black Box Warnings", "Cảnh giác dược", "Thu hồi thuốc"],
    attribution: "National Library of Medicine / U.S. FDA Open Data Initiative.",
    status: "live_sync",
    citationExample: "U.S. FDA DailyMed SPL, NDC 0002-4770-90 (Trulicity - dulaglutide), Revised 03/2026.",
  },
  {
    id: "pubmed-medline",
    name: "PubMed / MEDLINE & Living Evidence Repositories",
    shortName: "PubMed / NLM & Living Evidence",
    authority: "National Center for Biotechnology Information (NCBI / NLM)",
    country: "Quốc tế (US / Global)",
    version: "MEDLINE 2026 & Living Evidence Index",
    category: "literature",
    categoryLabel: "Y văn & Thử nghiệm",
    badgeTone: "ok",
    evidenceGrade: "Hạng A/B+ (Y học dựa trên bằng chứng RCT & Meta-analysis)",
    updateFrequency: "Lập chỉ mục thời gian thực",
    scope: "Hơn 36 triệu trích dẫn y sinh học, thử nghiệm lâm sàng ngẫu nhiên có đối chứng (RCT), phân tích gộp (Meta-analyses), và khuyến cáo từ các hội chuyên khoa hàng đầu (ESC, ADA, KDIGO, GINA).",
    keyTopics: ["Thử nghiệm RCT", "Phân tích gộp", "Hướng dẫn ESC/ADA", "Tổng quan hệ thống"],
    attribution: "National Library of Medicine / National Institutes of Health (NIH).",
    status: "active",
    citationExample: "PubMed PMID: 37622384 — ESC Guidelines for the management of cardiovascular disease in diabetes (2023).",
  },
  {
    id: "who-guidelines-eml",
    name: "WHO Guidelines & Model List of Essential Medicines (EML)",
    shortName: "WHO Essential Medicines & Guidelines",
    authority: "Tổ chức Y tế Thế giới (World Health Organization - WHO)",
    country: "Toàn cầu (WHO)",
    version: "23rd WHO Essential Medicines List (2025/2026)",
    category: "global",
    categoryLabel: "Y tế Toàn cầu",
    badgeTone: "neutral",
    evidenceGrade: "Hạng A (Global Health Benchmark)",
    updateFrequency: "Định kỳ 2 năm & Cập nhật thường xuyên",
    scope: "Danh mục thuốc thiết yếu chuẩn toàn cầu, hướng dẫn quản lý bệnh mạn tính, phân loại kháng sinh AWaRe (Access, Watch, Reserve) và an toàn sử dụng thuốc cộng đồng.",
    keyTopics: ["Thuốc thiết yếu", "Phân loại AWaRe", "Y tế cộng đồng", "An toàn bệnh nhân"],
    attribution: "© World Health Organization. Tài liệu phát hành công khai phục vụ sức khỏe cộng đồng.",
    status: "verified",
    citationExample: "WHO Model List of Essential Medicines - 23rd List, Geneva: World Health Organization, 2025.",
  },
];

const CATEGORY_TABS: Array<{ id: SourceCategory; label: string; count: number }> = [
  { id: "all", label: "Tất cả nguồn", count: MEDICAL_SOURCES.length },
  { id: "pharmacopoeia", label: "Dược thư & Thuốc", count: 2 },
  { id: "guidelines", label: "Phác đồ Bộ Y Tế", count: 1 },
  { id: "regulatory", label: "Cơ quan Quản lý Dược", count: 1 },
  { id: "literature", label: "Y văn & Nghiên cứu", count: 1 },
  { id: "global", label: "Tổ chức Quốc tế", count: 1 },
];

export function SourcesCatalogClient() {
  const [selectedCategory, setSelectedCategory] = useState<SourceCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);

  const filteredSources = useMemo(() => {
    return MEDICAL_SOURCES.filter((source) => {
      const matchesCategory = selectedCategory === "all" || source.category === selectedCategory;
      const query = searchQuery.trim().toLowerCase();
      if (!query) return matchesCategory;

      const matchesSearch =
        source.name.toLowerCase().includes(query) ||
        source.shortName.toLowerCase().includes(query) ||
        source.authority.toLowerCase().includes(query) ||
        source.scope.toLowerCase().includes(query) ||
        source.keyTopics.some((t) => t.toLowerCase().includes(query));

      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  return (
    <div className="space-y-8" data-testid="sources-catalog-client">
      {/* 1. Filter and Search Control Bar */}
      <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Search Input */}
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[var(--text-muted)]">
              <Icon name="search" size="1.1rem" />
            </div>
            <input
              type="search"
              aria-label="Tìm kiếm nguồn y văn, dược thư hoặc hướng dẫn điều trị"
              placeholder="Tìm theo tên nguồn, hoạt chất, cơ quan ban hành hoặc từ khóa..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-500)]"
            />
          </div>

          <span className="text-xs text-[var(--text-muted)] font-semibold shrink-0">
            Hiển thị <strong>{filteredSources.length}</strong> / {MEDICAL_SOURCES.length} nguồn dữ liệu
          </span>
        </div>

        {/* Category Tabs */}
        <div
          role="tablist"
          aria-label="Lọc theo phân loại nguồn y khoa"
          className="flex flex-wrap items-center gap-2 pt-1 border-t border-[color:var(--shell-border)]/50"
        >
          {CATEGORY_TABS.map((tab) => {
            const isSelected = selectedCategory === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isSelected}
                onClick={() => setSelectedCategory(tab.id)}
                className={[
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition active:scale-95",
                  isSelected
                    ? "bg-[var(--brand-600)] text-white shadow-xs"
                    : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] border border-[color:var(--shell-border)]/60",
                ].join(" ")}
              >
                <span>{tab.label}</span>
                <span
                  className={[
                    "rounded-full px-1.5 py-0.2 text-[10px] font-bold",
                    isSelected ? "bg-white/20 text-white" : "bg-[var(--surface-panel)] text-[var(--text-muted)]",
                  ].join(" ")}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Sources Grid */}
      {filteredSources.length === 0 ? (
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-12 text-center space-y-3">
          <Icon name="search" size="2rem" className="mx-auto text-[var(--text-muted)]" />
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Không tìm thấy nguồn y văn phù hợp
          </h3>
          <p className="text-xs text-[var(--text-secondary)] max-w-sm mx-auto">
            Không có nguồn dữ liệu nào khớp với từ khóa &ldquo;{searchQuery}&rdquo;. Vui lòng thử tìm với từ khóa khác hoặc xóa bộ lọc.
          </p>
          <button
            type="button"
            onClick={() => {
              setSelectedCategory("all");
              setSearchQuery("");
            }}
            className="text-xs font-bold text-[var(--text-brand)] hover:underline pt-2"
          >
            Xóa bộ lọc tìm kiếm
          </button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2" data-testid="sources-list-grid">
          {filteredSources.map((source) => {
            const isExpanded = activeSourceId === source.id;
            return (
              <article
                key={source.id}
                className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 space-y-5 shadow-sm hover:border-[color:var(--brand-500)]/60 transition"
              >
                {/* Header & Badges */}
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone={source.badgeTone}>{source.categoryLabel}</Badge>
                    <span className="text-[11px] font-mono font-bold text-[var(--text-muted)]">
                      {source.country}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-base sm:text-lg font-bold tracking-tight text-[var(--text-primary)]">
                      {source.name}
                    </h3>
                    <p className="text-xs text-[var(--text-brand)] font-medium mt-0.5">
                      {source.authority}
                    </p>
                  </div>

                  <p className="text-xs sm:text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    {source.scope}
                  </p>

                  {/* Key Topic Chips */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    {source.keyTopics.map((topic) => (
                      <span
                        key={topic}
                        className="rounded-md border border-[color:var(--shell-border)]/70 bg-[var(--surface-muted)]/70 px-2 py-0.5 text-[11px] text-[var(--text-secondary)]"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Metadata Details Table */}
                <div className="space-y-3 border-t border-[color:var(--shell-border)]/60 pt-4 text-xs">
                  <div className="space-y-2 rounded-xl bg-[var(--surface-muted)]/40 p-3.5 border border-[color:var(--shell-border)]/60">
                    <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/40 pb-1.5">
                      <span className="text-[var(--text-muted)]">Phiên bản / Năm:</span>
                      <span className="font-semibold text-[var(--text-primary)]">{source.version}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/40 pb-1.5">
                      <span className="text-[var(--text-muted)]">Mức độ bằng chứng:</span>
                      <span className="font-semibold text-[var(--status-ok-text)]">{source.evidenceGrade}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/40 pb-1.5">
                      <span className="text-[var(--text-muted)]">Chu kỳ cập nhật:</span>
                      <span className="font-semibold text-[var(--text-primary)]">{source.updateFrequency}</span>
                    </div>
                    <div className="flex items-center justify-between pt-0.5">
                      <span className="text-[var(--text-muted)]">Trạng thái đồng bộ:</span>
                      <span className="inline-flex items-center gap-1 font-bold text-[var(--text-brand)]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[var(--text-brand)]" />
                        <span>Đã kiểm định</span>
                      </span>
                    </div>
                  </div>

                  {/* Expandable Citation Example */}
                  {isExpanded ? (
                    <div className="rounded-xl border border-[color:var(--brand-500)]/30 bg-[var(--surface-brand-soft)]/40 p-3.5 space-y-2 text-xs">
                      <div className="flex items-center gap-1.5 text-[var(--text-brand)] font-bold">
                        <Icon name="clinical-notes" size="0.95rem" />
                        <span>Ví dụ trích dẫn y khoa chuẩn (Citation Example):</span>
                      </div>
                      <p className="font-mono text-[11px] text-[var(--text-primary)] bg-[var(--surface-panel)] p-2.5 rounded-lg border border-[color:var(--shell-border)]">
                        {source.citationExample}
                      </p>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        {source.attribution}
                      </p>
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between pt-1">
                    <button
                      type="button"
                      onClick={() => setActiveSourceId(isExpanded ? null : source.id)}
                      className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-brand)] hover:underline"
                    >
                      <Icon name="chevron-down" size="0.85rem" />
                      <span>{isExpanded ? "Thu gọn chi tiết trích dẫn" : "Xem định dạng trích dẫn & Bản quyền"}</span>
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
