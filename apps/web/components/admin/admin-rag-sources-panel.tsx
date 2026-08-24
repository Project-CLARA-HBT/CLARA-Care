"use client";

import { useMemo, useState } from "react";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { StatusChip } from "@/components/ui/status-chip";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import { DEFAULT_SOURCE_CATEGORIES } from "@/components/admin/admin-config-meta";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import type { ControlTowerRagSource } from "@/lib/system";
import { useUILanguage } from "@/lib/use-ui-language";
import { t } from "@/lib/i18n/catalog";

export interface AdminRagSourcesPanelProps {
  className?: string;
  onSelectSource?: (source: ControlTowerRagSource) => void;
}

export default function AdminRagSourcesPanel({
  className = "",
  onSelectSource,
}: AdminRagSourcesPanelProps) {
  const language = useUILanguage();
  const isVi = language === "vi";

  const {
    config,
    error,
    message,
    isDirty,
    isLoading,
    isSaving,
    reload,
    save,
    setSourceCategory,
    setSourceEnabled,
    setSourcePriority,
    setSourceWeight,
  } = useControlTowerConfig();

  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [selectedSource, setSelectedSource] = useState<ControlTowerRagSource | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const categoryOptions = useMemo(() => {
    const fromConfig = (config?.rag_sources ?? []).map((source) => source.category);
    return Array.from(new Set([...DEFAULT_SOURCE_CATEGORIES, ...fromConfig])).sort();
  }, [config]);

  const sources = useMemo(() => config?.rag_sources ?? [], [config?.rag_sources]);
  const totalSources = sources.length;
  const enabledSources = sources.filter((s) => s.enabled).length;

  const filteredSources = useMemo(() => {
    return sources.filter((source) => {
      if (categoryFilter !== "all" && source.category !== categoryFilter) {
        return false;
      }
      if (statusFilter === "enabled" && !source.enabled) {
        return false;
      }
      if (statusFilter === "disabled" && source.enabled) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchesName = source.name.toLowerCase().includes(q);
        const matchesId = source.id.toLowerCase().includes(q);
        const matchesCat = source.category.toLowerCase().includes(q);
        if (!matchesName && !matchesId && !matchesCat) return false;
      }
      return true;
    });
  }, [sources, categoryFilter, statusFilter, searchQuery]);

  const handleInspect = (source: ControlTowerRagSource) => {
    setSelectedSource(source);
    setInspectorOpen(true);
    onSelectSource?.(source);
  };

  const getCategoryBadgeTone = (cat: string): BadgeTone => {
    switch (cat.toLowerCase()) {
      case "guideline":
      case "pharmacopeia":
        return "brand";
      case "drug-safety":
      case "policy":
        return "warn";
      case "research":
      case "literature":
        return "brand";
      default:
        return "neutral";
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Panel Header & Global Controls */}
      <section className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {isVi ? "Cấu hình nguồn truy xuất RAG" : "RAG Data Source Controls"}
              </h3>
              <Badge tone="brand" className="font-mono text-[10px]">
                {enabledSources}/{totalSources} {isVi ? "hoạt động" : "active"}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {isVi
                ? "Điều chỉnh trạng thái bật/tắt, mức độ ưu tiên (priority), trọng số (weight), và danh mục cho từng nguồn RAG."
                : "Manage enabled state, priority ranking, synthesis weight, and category mapping across RAG knowledge connectors."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void reload()}
              disabled={isLoading || isSaving}
              className="border-[color:var(--shell-border)] text-xs"
            >
              <Icon name="refresh" size={13} className="mr-1.5" />
              {isVi ? "Tải lại" : "Reload"}
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!isDirty || isSaving || isLoading || !config}
              onClick={() => void save()}
              className="text-xs font-semibold"
            >
              {isSaving ? (
                <>
                  <span className="mr-1.5 inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  {isVi ? "Đang lưu…" : "Saving…"}
                </>
              ) : (
                <>
                  <Icon name="check" size={13} className="mr-1.5" />
                  {isVi ? "Lưu cấu hình" : "Save Sources"}
                </>
              )}
            </Button>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="mt-3 flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]"
          >
            <Icon name="warning" size={14} className="shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        {message ? (
          <div
            role="status"
            className="mt-3 flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-xs text-[var(--status-ok-text)]"
          >
            <Icon name="check" size={14} className="shrink-0" />
            <span>{message}</span>
          </div>
        ) : null}
      </section>

      {/* Sticky Filter & Search Toolbar */}
      <div className="sticky top-0 z-10 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 p-3 backdrop-blur shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-1 flex-wrap items-center gap-2.5 min-w-[280px]">
            {/* Search Input */}
            <div className="relative min-w-[200px] flex-1 max-w-sm">
              <Icon
                name="search"
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={isVi ? "Tìm theo tên nguồn, mã ID…" : "Search by source name, ID…"}
                aria-label={isVi ? "Tìm kiếm nguồn RAG" : "Search RAG sources"}
                className="min-h-[34px] w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[color:var(--brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--brand-primary)]"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  aria-label={isVi ? "Xóa tìm kiếm" : "Clear search"}
                >
                  <Icon name="close" size={12} />
                </button>
              )}
            </div>

            {/* Category Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="rag-panel-category-filter" className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                {isVi ? "Danh mục:" : "Category:"}
              </label>
              <select
                id="rag-panel-category-filter"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                aria-label={isVi ? "Lọc theo danh mục" : "Filter by category"}
                className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-medium text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
              >
                <option value="all">{isVi ? "Tất cả danh mục" : "All Categories"}</option>
                {categoryOptions.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5">
              <label htmlFor="rag-panel-status-filter" className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                {isVi ? "Trạng thái:" : "Status:"}
              </label>
              <select
                id="rag-panel-status-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as "all" | "enabled" | "disabled")}
                aria-label={isVi ? "Lọc theo trạng thái" : "Filter by status"}
                className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-medium text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
              >
                <option value="all">{isVi ? "Tất cả" : "All"}</option>
                <option value="enabled">{isVi ? "Đang bật" : "Enabled"}</option>
                <option value="disabled">{isVi ? "Đã tắt" : "Disabled"}</option>
              </select>
            </div>
          </div>

          <div className="text-[11px] font-mono text-[var(--text-muted)]">
            {isVi
              ? `Hiển thị ${filteredSources.length}/${totalSources} nguồn`
              : `Showing ${filteredSources.length}/${totalSources} sources`}
          </div>
        </div>
      </div>

      {/* Dense Source Registry Table */}
      <section className="overflow-x-auto rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-[var(--text-muted)]">
            <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            {isVi ? "Đang tải cấu hình nguồn RAG…" : "Loading RAG sources…"}
          </div>
        ) : (
          <table
            className="w-full text-left text-xs"
            aria-label={isVi ? "Bảng cấu hình nguồn RAG" : "RAG sources configuration table"}
          >
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                <th className="px-3.5 py-2.5">{isVi ? "Nguồn RAG" : "Source Name"}</th>
                <th className="px-3 py-2.5">{isVi ? "Danh mục" : "Category"}</th>
                <th className="px-3 py-2.5 text-center">{isVi ? "Mức ưu tiên" : "Priority"}</th>
                <th className="px-3 py-2.5">{isVi ? "Trọng số (Weight)" : "Weight"}</th>
                <th className="px-3 py-2.5 text-center">{isVi ? "Trạng thái" : "Status"}</th>
                <th className="px-3 py-2.5 text-right">{isVi ? "Thao tác" : "Actions"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)]">
              {filteredSources.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-xs text-[var(--text-muted)]">
                    {isVi ? "Không tìm thấy nguồn RAG nào phù hợp." : "No matching RAG sources found."}
                  </td>
                </tr>
              ) : (
                filteredSources.map((source) => {
                  const isSelected = selectedSource?.id === source.id;
                  return (
                    <tr
                      key={source.id}
                      onClick={() => handleInspect(source)}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleInspect(source);
                        }
                      }}
                      className={`group cursor-pointer transition-colors focus:outline-none ${
                        isSelected
                          ? "bg-[var(--surface-brand-soft)]/60"
                          : "hover:bg-[var(--surface-muted)]/70"
                      }`}
                    >
                      {/* Name & ID */}
                      <td className="px-3.5 py-2.5">
                        <div className="flex items-center gap-2">
                          <div>
                            <p className="font-semibold text-[var(--text-primary)] group-hover:text-[var(--text-brand)]">
                              {source.name}
                            </p>
                            <p className="font-mono text-[10px] text-[var(--text-muted)]">
                              {source.id}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Category */}
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={source.category}
                          onChange={(e) => setSourceCategory(source.id, e.target.value)}
                          aria-label={`Category for ${source.name}`}
                          className="min-h-[28px] rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-xs font-medium text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
                        >
                          {categoryOptions.map((cat) => (
                            <option key={cat} value={cat}>
                              {cat}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* Priority */}
                      <td className="px-3 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                        <div className="inline-flex items-center gap-1.5">
                          <input
                            type="number"
                            min={1}
                            max={100}
                            value={source.priority}
                            onChange={(e) => setSourcePriority(source.id, Number(e.target.value))}
                            aria-label={`Priority for ${source.name}`}
                            className="h-7 w-14 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 text-center font-mono text-xs font-bold text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
                          />
                        </div>
                      </td>

                      {/* Weight */}
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-2 min-w-[140px]">
                          <input
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            value={source.weight}
                            onChange={(e) => setSourceWeight(source.id, Number(e.target.value))}
                            aria-label={`Weight for ${source.name}`}
                            className="h-7 w-14 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 text-center font-mono text-xs font-bold text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
                          />
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]">
                            <div
                              className="h-full rounded-full bg-[var(--brand-primary)]"
                              style={{ width: `${Math.round(Math.min(1, Math.max(0, source.weight)) * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-3 py-2.5 text-center">
                        <StatusChip
                          tone={source.enabled ? "success" : "unknown"}
                          label={source.enabled ? (isVi ? "Hoạt động" : "Enabled") : (isVi ? "Đã tắt" : "Disabled")}
                          size="sm"
                        />
                      </td>

                      {/* Actions */}
                      <td className="px-3 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => setSourceEnabled(source.id, !source.enabled)}
                            className={`min-h-[26px] rounded-[var(--radius-sm)] border px-2 text-[11px] font-semibold transition ${
                              source.enabled
                                ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] hover:opacity-80"
                                : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)] hover:opacity-80"
                            }`}
                          >
                            {source.enabled ? (isVi ? "Tắt" : "Disable") : (isVi ? "Bật" : "Enable")}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleInspect(source)}
                            className="min-h-[26px] rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-[11px] font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          >
                            {isVi ? "Chi tiết" : "Inspect"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </section>

      {/* Selected Source Inspector Drawer */}
      <Inspector
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        title={selectedSource ? selectedSource.name : (isVi ? "Chi tiết nguồn RAG" : "RAG Source Inspector")}
        subtitle={
          selectedSource
            ? `ID: ${selectedSource.id} · ${isVi ? "Danh mục" : "Category"}: ${selectedSource.category}`
            : undefined
        }
        badges={
          selectedSource ? (
            <div className="flex items-center gap-2">
              <Badge tone={getCategoryBadgeTone(selectedSource.category)} className="font-mono text-[10px]">
                {selectedSource.category}
              </Badge>
              <StatusChip
                tone={selectedSource.enabled ? "success" : "unknown"}
                label={selectedSource.enabled ? (isVi ? "Hoạt động" : "Enabled") : (isVi ? "Đã tắt" : "Disabled")}
                size="sm"
              />
            </div>
          ) : undefined
        }
        size="md"
        footer={
          <div className="flex items-center justify-between gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setInspectorOpen(false)}
            >
              {isVi ? "Đóng" : "Close"}
            </Button>
            {selectedSource && (
              <div className="flex items-center gap-2">
                <Button
                  variant={selectedSource.enabled ? "danger" : "secondary"}
                  size="sm"
                  onClick={() => {
                    setSourceEnabled(selectedSource.id, !selectedSource.enabled);
                    setSelectedSource((prev) =>
                      prev ? { ...prev, enabled: !prev.enabled } : prev
                    );
                  }}
                >
                  {selectedSource.enabled ? (isVi ? "Tắt nguồn" : "Disable") : (isVi ? "Bật nguồn" : "Enable")}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={!isDirty || isSaving}
                  onClick={() => void save()}
                >
                  {isSaving ? (isVi ? "Đang lưu…" : "Saving…") : (isVi ? "Lưu thay đổi" : "Save Changes")}
                </Button>
              </div>
            )}
          </div>
        }
      >
        {selectedSource && (
          <div className="space-y-4">
            <InspectorSection
              title={isVi ? "Thông tin nguồn tri thức" : "Source Metadata"}
              description={isVi ? "Định danh và cấu hình cơ bản của nguồn trong pipeline retrieval." : "Pipeline identifiers and category taxonomy."}
            >
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <InspectorField
                  label={isVi ? "Mã nguồn (ID)" : "Source ID"}
                  value={selectedSource.id}
                  copyable
                />
                <InspectorField
                  label={isVi ? "Tên hiển thị" : "Display Name"}
                  value={selectedSource.name}
                />
                <InspectorField
                  label={isVi ? "Danh mục hiện tại" : "Current Category"}
                  value={selectedSource.category}
                />
                <InspectorField
                  label={isVi ? "Trạng thái kết nối" : "Connector Status"}
                  value={selectedSource.enabled ? (isVi ? "Bật (Active)" : "Enabled") : (isVi ? "Tắt (Disabled)" : "Disabled")}
                />
              </div>
            </InspectorSection>

            <InspectorSection
              title={isVi ? "Mức ưu tiên & Trọng số truy xuất" : "Priority & Synthesis Weight"}
              description={isVi ? "Mức ưu tiên thấp hơn sẽ được xếp trước trong pipeline. Trọng số ảnh hưởng đến điểm số reranking." : "Lower priority number indicates higher retrieval precedence."}
            >
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    {isVi ? "Mức ưu tiên (Priority 1-100):" : "Priority Rank (1-100):"}
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={selectedSource.priority}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setSourcePriority(selectedSource.id, val);
                      setSelectedSource((prev) => (prev ? { ...prev, priority: val } : prev));
                    }}
                    className="mt-1 min-h-[34px] w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-primary)] focus:outline-none"
                  />
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                    {isVi
                      ? "Ưu tiên 1 là cao nhất (ưu tiên truy xuất đầu tiên)."
                      : "Priority 1 is evaluated first in hybrid retrieval."}
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      {isVi ? "Trọng số tổng hợp (Weight 0.0 - 1.0):" : "Synthesis Weight (0.0 - 1.0):"}
                    </label>
                    <span className="font-mono text-xs font-bold text-[var(--text-brand)]">
                      {selectedSource.weight.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={selectedSource.weight}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setSourceWeight(selectedSource.id, val);
                      setSelectedSource((prev) => (prev ? { ...prev, weight: val } : prev));
                    }}
                    className="mt-1 w-full accent-[color:var(--brand-primary)]"
                    aria-label={`Weight slider for ${selectedSource.name}`}
                  />
                </div>
              </div>
            </InspectorSection>
          </div>
        )}
      </Inspector>
    </div>
  );
}
