"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { EmptyState, InlineError, SurfaceCard } from "@/components/ui/surface";
import MedicalConsentGate from "@/components/medicines/medical-consent-gate";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import { trackCareguardViewed } from "@/lib/analytics/events";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { createMedicationCourse } from "@/lib/medication-courses";
import {
  deleteCabinetItem,
  getCabinet,
  updateCabinetItem,
  type CabinetItem,
  type NormalizationStatus,
} from "@/lib/selfmed";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { DrugAutocompleteSearch } from "@/components/medicines/drug-autocomplete-search";

type FilterTab = "all" | "valid" | "expiring" | "expired" | "missingDose";

function sourceLabel(language: "vi" | "en", source: string): string {
  if (source === "ocr") return t(language, "medicines.cabinet.source.ocr");
  if (source === "manual") return t(language, "medicines.cabinet.source.manual");
  if (source === "barcode") return t(language, "medicines.cabinet.source.barcode");
  if (source === "imported") return t(language, "medicines.cabinet.source.imported");
  return source;
}

function sourceTone(source: string): BadgeTone {
  if (source === "ocr") return "brand";
  if (source === "manual") return "neutral";
  if (source === "barcode") return "brand";
  if (source === "imported") return "brand";
  return "neutral";
}

function normalizationLabel(language: "vi" | "en", source: string | null | undefined): string {
  if (source === "db" || source === "matched") return t(language, "medicines.cabinet.normalization.matched");
  if (source === "candidate") return t(language, "medicines.cabinet.normalization.candidate");
  if (source === "needs_review") return t(language, "medicines.cabinet.normalization.review");
  if (source === "fallback") return t(language, "medicines.cabinet.normalization.manual");
  return t(language, "medicines.cabinet.normalization.unknown");
}

function normalizationTone(source: string | null | undefined): BadgeTone {
  if (source === "db" || source === "matched") return "ok";
  if (source === "candidate") return "warn";
  if (source === "needs_review") return "danger";
  if (source === "fallback") return "danger";
  return "neutral";
}

function formatDate(language: "vi" | "en", value: string | null): string {
  if (!value) return t(language, "medicines.cabinet.notAvailable");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t(language, "medicines.cabinet.notAvailable");
  return formatLocaleDate(language, date);
}

export default function MedicineCabinetInventoryPage() {
  const language = useUILanguage();
  const isEn = language === "en";
  const { setMode } = useShellMode();

  useEffect(() => {
    setMode("explore");
  }, [setMode]);

  const [cabinetLabel, setCabinetLabel] = useState("");
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [convertingId, setConvertingId] = useState<number | null>(null);

  // Search and filter
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterTab>("all");

  // Edit item modal
  const [editingItem, setEditingItem] = useState<CabinetItem | null>(null);
  const [editDrugName, setEditDrugName] = useState("");
  const [editBrandName, setEditBrandName] = useState("");
  const [editManufacturer, setEditManufacturer] = useState("");
  const [editDosage, setEditDosage] = useState("");
  const [editQuantity, setEditQuantity] = useState(1);
  const [editExpiresOn, setEditExpiresOn] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");

  const refreshCabinet = useCallback(async () => {
    setError("");
    setIsLoading(true);
    try {
      const response = await getCabinet();
      setCabinetLabel(response.label || "");
      setItems(response.items ?? []);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.cabinet.loadError")));
    } finally {
      setIsLoading(false);
    }
  }, [language]);

  useEffect(() => {
    trackCareguardViewed({ surface: "selfmed" });
    void refreshCabinet();
  }, [refreshCabinet]);

  const stats = useMemo(() => {
    const fromOcr = items.filter((item) => item.source === "ocr").length;
    const manual = items.filter((item) => item.source === "manual").length;

    const now = Date.now();
    const in30Days = now + 30 * 24 * 60 * 60 * 1000;

    let expiringSoon = 0;
    let expired = 0;
    let valid = 0;
    let missingDosage = 0;

    items.forEach((item) => {
      if (!String(item.dosage ?? "").trim()) {
        missingDosage += 1;
      }
      if (!item.expires_on) {
        valid += 1;
        return;
      }
      const expiresAt = Date.parse(item.expires_on);
      if (!Number.isFinite(expiresAt)) {
        valid += 1;
        return;
      }
      if (expiresAt < now) {
        expired += 1;
      } else if (expiresAt <= in30Days) {
        expiringSoon += 1;
      } else {
        valid += 1;
      }
    });

    return {
      total: items.length,
      fromOcr,
      manual,
      expiringSoon,
      expired,
      valid,
      missingDosage,
    };
  }, [items]);

  const filteredItems = useMemo(() => {
    const now = Date.now();
    const in30Days = now + 30 * 24 * 60 * 60 * 1000;
    const q = searchQuery.trim().toLowerCase();

    return items.filter((item) => {
      // Search filter
      if (q) {
        const matchesName = item.drug_name.toLowerCase().includes(q);
        const matchesBrand = (item.brand_name || "").toLowerCase().includes(q);
        const matchesMfg = (item.manufacturer || "").toLowerCase().includes(q);
        if (!matchesName && !matchesBrand && !matchesMfg) return false;
      }

      // Status filter
      if (activeFilter === "valid") {
        if (!item.expires_on) return true;
        const exp = Date.parse(item.expires_on);
        return Number.isFinite(exp) && exp > in30Days;
      }
      if (activeFilter === "expiring") {
        if (!item.expires_on) return false;
        const exp = Date.parse(item.expires_on);
        return Number.isFinite(exp) && exp >= now && exp <= in30Days;
      }
      if (activeFilter === "expired") {
        if (!item.expires_on) return false;
        const exp = Date.parse(item.expires_on);
        return Number.isFinite(exp) && exp < now;
      }
      if (activeFilter === "missingDose") {
        return !String(item.dosage ?? "").trim();
      }

      return true;
    });
  }, [items, searchQuery, activeFilter]);

  const onDelete = async (itemId: number) => {
    setNotice("");
    setError("");
    try {
      await deleteCabinetItem(itemId);
      setNotice(t(language, "medicines.cabinet.deleted"));
      await refreshCabinet();
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.cabinet.deleteError")));
    }
  };

  const onConvertToActiveTaking = async (item: CabinetItem) => {
    setNotice("");
    setError("");
    setConvertingId(item.id);
    try {
      await createMedicationCourse({
        medication_name: item.drug_name,
        dose_text: item.dosage || undefined,
        form_text: item.dosage_form || undefined,
        route_text: isEn ? "oral" : "uống",
        schedule_text: isEn ? "1 dose daily" : "Uống hàng ngày",
      });
      setNotice(
        isEn
          ? `Promoted "${item.drug_name}" to active taking medication.`
          : `Đã chuyển "${item.drug_name}" thành thuốc đang dùng trong hồ sơ.`,
      );
    } catch (cause) {
      setError(
        safeUserFacingError(
          cause,
          isEn ? "Failed to convert item to active course." : "Không thể chuyển thuốc vào đơn đang dùng.",
        ),
      );
    } finally {
      setConvertingId(null);
    }
  };

  const openEditModal = (item: CabinetItem) => {
    setEditingItem(item);
    setEditDrugName(item.drug_name);
    setEditBrandName(item.brand_name || "");
    setEditManufacturer(item.manufacturer || "");
    setEditDosage(item.dosage || "");
    setEditQuantity(item.quantity || 1);
    setEditExpiresOn(item.expires_on ? item.expires_on.split("T")[0] : "");
    setEditError("");
  };

  const saveItemEdit = async () => {
    if (!editingItem || !editDrugName.trim()) return;
    setSavingEdit(true);
    setEditError("");
    try {
      await updateCabinetItem(editingItem.id, {
        drug_name: editDrugName.trim(),
        brand_name: editBrandName.trim() || undefined,
        manufacturer: editManufacturer.trim() || undefined,
        dosage: editDosage.trim() || undefined,
        quantity: editQuantity,
        expires_on: editExpiresOn.trim() || undefined,
      });
      setEditingItem(null);
      setNotice(isEn ? "Cabinet item updated." : "Đã cập nhật thông tin thuốc trong tủ.");
      await refreshCabinet();
    } catch (cause) {
      setEditError(safeUserFacingError(cause, isEn ? "Unable to update item." : "Không thể cập nhật thông tin thuốc."));
    } finally {
      setSavingEdit(false);
    }
  };

  const quickAdjustQuantity = async (item: CabinetItem, delta: number) => {
    const nextQty = Math.max(0, (item.quantity || 0) + delta);
    try {
      await updateCabinetItem(item.id, { quantity: nextQty });
      setItems((prev) =>
        prev.map((it) => (it.id === item.id ? { ...it, quantity: nextQty } : it)),
      );
    } catch {
      // Refresh on failure
      void refreshCabinet();
    }
  };

  const canCheckInteractions = stats.total >= 2;

  return (
    <MedicalConsentGate>
      <div className="mx-auto max-w-5xl space-y-8 pb-20 pt-4" data-testid="medicine-cabinet-inventory">
        {/* Navigation Breadcrumb */}
        <nav aria-label="Breadcrumb" className="flex items-center justify-between">
          <Link
            href="/medicines"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-brand)] transition-colors focus-ring"
          >
            <Icon name="arrow-left" size={16} aria-hidden="true" />
            <span>{isEn ? "Back to Medicines Hub" : "Quay lại Trung tâm Thuốc"}</span>
          </Link>
          <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
            {isEn ? "Archetype: Medicine Cabinet Inventory" : "Tủ thuốc Gia đình & Tồn kho"}
          </span>
        </nav>

        {/* Top Header Card */}
        <SurfaceCard className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Icon name="medication" size={24} className="text-[var(--text-brand)]" aria-hidden="true" />
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
                  {cabinetLabel || (isEn ? "Home Medicine Cabinet" : "Tủ thuốc gia đình")}
                </h1>
              </div>
              <p className="max-w-2xl text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                {isEn
                  ? "Manage household backup medication inventory, track expiration dates, receive safe disposal guidance, and promote stock items to active treatment regimens."
                  : "Quản lý danh mục tồn kho thuốc dự phòng tại nhà, theo dõi hạn sử dụng, hướng dẫn tiêu hủy an toàn và chuyển đổi nhanh sang đơn thuốc đang dùng."}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button as="link" href="/medicines/cabinet/add" icon="plus">
                {t(language, "medicines.cabinet.add")}
              </Button>
              {canCheckInteractions ? (
                <Button as="link" href="/medicines?tab=safety" variant="secondary" icon="clinical-notes">
                  {t(language, "medicines.cabinet.checkInteractions")}
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  disabled
                  icon="clinical-notes"
                  title={t(language, "medicines.cabinet.needsTwo")}
                >
                  {t(language, "medicines.cabinet.checkInteractions")}
                </Button>
              )}
              <Button variant="ghost" icon="refresh" onClick={() => void refreshCabinet()}>
                {t(language, "medicines.cabinet.refresh")}
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs uppercase tracking-wider text-[var(--text-muted)] border-t border-[color:var(--shell-border)] pt-3">
            <span className="inline-flex items-center gap-1">
              <Icon name="check" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.verifiedSource")}
            </span>
            <span className="inline-flex items-center gap-1">
              <Icon name="folder" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.accountData")}
            </span>
            <span className="inline-flex items-center gap-1">
              <Icon name="progress" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.updateAnytime")}
            </span>
          </div>
        </SurfaceCard>

        {/* 1-Click Vietnamese Trade Name Quick Add to Cabinet */}
        <SurfaceCard className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              {isEn ? "1-Click Quick Add to Cabinet (Vietnamese Trade Names):" : "Thêm nhanh thuốc vào Tủ thuốc (Tìm theo tên biệt dược):"}
            </h2>
            <span className="text-[11px] text-[var(--text-muted)]">
              Panadol, Glucophage, Coversyl, Augmentin, Lipitor...
            </span>
          </div>
          <DrugAutocompleteSearch
            onAddedToCabinet={() => void refreshCabinet()}
            placeholder={
              isEn
                ? "Search Vietnamese brand names to 1-click add to cabinet..."
                : "Tìm kiếm thuốc biệt dược để thêm nhanh 1-chạm vào tủ thuốc..."
            }
          />
        </SurfaceCard>

        {notice ? (
          <div className="flex items-center justify-between rounded-xl border border-[color:var(--brand-border)] bg-[var(--surface-brand-soft)] p-4 text-xs font-medium text-[var(--text-brand)]">
            <div className="flex items-center gap-2">
              <Icon name="check" size={16} aria-hidden="true" />
              <span>{notice}</span>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/medicines?tab=list" className="underline font-bold">
                {isEn ? "View Active List" : "Xem đơn thuốc đang dùng →"}
              </Link>
              <button type="button" onClick={() => setNotice("")} className="text-xs text-[var(--text-secondary)]">
                {isEn ? "Dismiss" : "Đóng"}
              </button>
            </div>
          </div>
        ) : null}

        {error ? <InlineError message={error} onRetry={() => void refreshCabinet()} /> : null}

        {/* Readiness & KPI Statistics Grid */}
        <section aria-labelledby="inventory-stats-heading" className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <SurfaceCard className="p-4 border border-[color:var(--shell-border)]">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              {isEn ? "Total Items" : "Tổng số thuốc"}
            </p>
            <p className="text-2xl font-extrabold text-[var(--text-primary)] mt-1">
              {formatLocaleNumber(language, stats.total)}
            </p>
            <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">
              {stats.fromOcr} OCR · {stats.manual} {isEn ? "manual" : "thủ công"}
            </p>
          </SurfaceCard>

          <SurfaceCard className="p-4 border border-[color:var(--shell-border)]">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              {isEn ? "Good Condition" : "Còn hạn sử dụng"}
            </p>
            <p className="text-2xl font-extrabold text-[var(--status-ok-text)] mt-1">
              {formatLocaleNumber(language, stats.valid)}
            </p>
            <Badge tone="ok" className="mt-1">{isEn ? "Ready" : "An toàn"}</Badge>
          </SurfaceCard>

          <SurfaceCard className="p-4 border border-[color:var(--shell-border)]">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              {isEn ? "Expiring Soon" : "Sắp hết hạn (≤30 ngày)"}
            </p>
            <p className="text-2xl font-extrabold text-[var(--status-warn-text)] mt-1">
              {formatLocaleNumber(language, stats.expiringSoon)}
            </p>
            <Badge tone={stats.expiringSoon > 0 ? "warn" : "neutral"} className="mt-1">
              {stats.expiringSoon > 0 ? (isEn ? "Action Needed" : "Cần lưu ý") : (isEn ? "None" : "Không có")}
            </Badge>
          </SurfaceCard>

          <SurfaceCard className="p-4 border border-[color:var(--shell-border)]">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
              {isEn ? "Expired" : "Đã quá hạn"}
            </p>
            <p className="text-2xl font-extrabold text-[var(--status-danger-text)] mt-1">
              {formatLocaleNumber(language, stats.expired)}
            </p>
            <Badge tone={stats.expired > 0 ? "danger" : "neutral"} className="mt-1">
              {stats.expired > 0 ? (isEn ? "Dispose Safely" : "Cần tiêu hủy") : (isEn ? "Clean" : "Tốt")}
            </Badge>
          </SurfaceCard>
        </section>

        {/* Filter & Search Bar */}
        <section aria-labelledby="inventory-controls" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:max-w-xs">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={isEn ? "Search cabinet medications..." : "Tìm thuốc theo tên, biệt dược..."}
                className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus-ring"
              />
              {searchQuery ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-2.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  ✕
                </button>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-1.5 w-full sm:w-auto">
              {[
                { id: "all" as const, label: isEn ? `All (${stats.total})` : `Tất cả (${stats.total})` },
                { id: "valid" as const, label: isEn ? `Valid (${stats.valid})` : `Còn hạn (${stats.valid})` },
                { id: "expiring" as const, label: isEn ? `Expiring (${stats.expiringSoon})` : `Sắp hết (${stats.expiringSoon})` },
                { id: "expired" as const, label: isEn ? `Expired (${stats.expired})` : `Quá hạn (${stats.expired})` },
                { id: "missingDose" as const, label: isEn ? `Missing Dose (${stats.missingDosage})` : `Thiếu liều (${stats.missingDosage})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveFilter(tab.id)}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                    activeFilter === tab.id
                      ? "bg-[var(--brand-500)] text-white shadow-sm"
                      : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Cabinet Stock Inventory List */}
        <section aria-labelledby="stock-list-heading" className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h2 id="stock-list-heading" className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
              {isEn ? "Cabinet Stock Inventory" : "Danh mục Tồn kho Thuốc gia đình"}
            </h2>
            <span className="text-xs text-[var(--text-muted)]">
              {isEn
                ? `Showing ${filteredItems.length} of ${stats.total} items`
                : `Hiển thị ${filteredItems.length} trên ${stats.total} thuốc`}
            </span>
          </div>

          {isLoading ? (
            <p className="text-sm text-[var(--text-secondary)]">{t(language, "medicines.cabinet.loading")}</p>
          ) : null}

          {!isLoading && filteredItems.length === 0 ? (
            <EmptyState
              icon="inventory_2"
              title={
                searchQuery || activeFilter !== "all"
                  ? (isEn ? "No Matching Medications" : "Không có thuốc phù hợp bộ lọc")
                  : t(language, "medicines.cabinet.emptyTitle")
              }
              description={
                searchQuery || activeFilter !== "all"
                  ? (isEn ? "Try clearing your search query or switching filters." : "Thử đổi từ khóa tìm kiếm hoặc chọn bộ lọc khác.")
                  : t(language, "medicines.cabinet.emptyDescription")
              }
            >
              {searchQuery || activeFilter !== "all" ? (
                <Button variant="secondary" size="sm" onClick={() => { setSearchQuery(""); setActiveFilter("all"); }}>
                  {isEn ? "Clear Filters" : "Xóa bộ lọc"}
                </Button>
              ) : (
                <Button as="link" href="/medicines/cabinet/add">
                  {t(language, "medicines.cabinet.add")}
                </Button>
              )}
            </EmptyState>
          ) : null}

          <div className="space-y-4">
            {filteredItems.map((item) => {
              const expiresAt = item.expires_on ? Date.parse(item.expires_on) : NaN;
              const now = Date.now();
              const isExpired = Number.isFinite(expiresAt) && expiresAt < now;
              const isExpiringSoon =
                Number.isFinite(expiresAt) && expiresAt >= now && expiresAt <= now + 30 * 24 * 60 * 60 * 1000;

              return (
                <SurfaceCard key={item.id} className="group overflow-hidden border border-[color:var(--shell-border)]">
                  <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:gap-6">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)]">
                      <Icon name="medication" size={28} className="text-[var(--text-brand)]" aria-hidden="true" />
                    </div>

                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate text-base sm:text-lg font-bold text-[var(--text-primary)]">
                          {item.drug_name}
                        </h3>
                        <Badge tone={sourceTone(item.source)}>{sourceLabel(language, item.source)}</Badge>
                        {(item.normalization_status ?? item.normalization_source) ? (
                          <Badge tone={normalizationTone(item.normalization_status ?? item.normalization_source)}>
                            {normalizationLabel(language, item.normalization_status ?? item.normalization_source)}
                          </Badge>
                        ) : null}

                        {isExpired ? (
                          <Badge tone="danger">{isEn ? "Expired" : "Đã hết hạn"}</Badge>
                        ) : isExpiringSoon ? (
                          <Badge tone="warn">{isEn ? "Expiring Soon" : "Sắp hết hạn"}</Badge>
                        ) : null}
                      </div>

                      <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
                        {t(language, "medicines.cabinet.doseValue", {
                          dose: item.dosage || t(language, "medicines.cabinet.notAvailable"),
                          quantity: formatLocaleNumber(language, item.quantity),
                        })}
                        {item.dosage_form ? ` · ${item.dosage_form}` : ""}
                      </p>

                      <p className="text-xs text-[var(--text-muted)]">
                        {t(language, "medicines.cabinet.brandValue", {
                          brand: item.brand_name || t(language, "medicines.cabinet.notAvailable"),
                          manufacturer: item.manufacturer || t(language, "medicines.cabinet.notAvailable"),
                        })}
                      </p>

                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[var(--text-muted)] pt-1">
                        <span className={`inline-flex items-center gap-1 font-medium ${isExpired ? "text-[var(--status-danger-text)]" : isExpiringSoon ? "text-[var(--status-warn-text)]" : ""}`}>
                          <Icon name="calendar" size={14} aria-hidden="true" />
                          {t(language, "medicines.cabinet.expiryValue", { date: formatDate(language, item.expires_on) })}
                        </span>
                        {item.ocr_confidence !== null ? (
                          <span className="inline-flex items-center gap-1 font-semibold text-[var(--status-ok-text)]">
                            <Icon name="check" size={14} aria-hidden="true" /> OCR {Math.round(item.ocr_confidence * 100)}%
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {/* Action & Quantity Box */}
                    <div className="flex flex-col items-end gap-3 shrink-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                          {t(language, "medicines.cabinet.quantity")}:
                        </span>
                        <div className="flex items-center gap-1 rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5">
                          <button
                            type="button"
                            onClick={() => void quickAdjustQuantity(item, -1)}
                            className="h-6 w-6 rounded text-xs font-bold hover:bg-[var(--bg-canvas)] focus-ring"
                            aria-label={isEn ? "Decrease quantity" : "Giảm số lượng"}
                          >
                            -
                          </button>
                          <span className="px-2 text-xs font-bold text-[var(--text-primary)]">
                            {formatLocaleNumber(language, item.quantity)}
                          </span>
                          <button
                            type="button"
                            onClick={() => void quickAdjustQuantity(item, 1)}
                            className="h-6 w-6 rounded text-xs font-bold hover:bg-[var(--bg-canvas)] focus-ring"
                            aria-label={isEn ? "Increase quantity" : "Tăng số lượng"}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Prominent Action: "Chuyển thành thuốc đang dùng" */}
                      <div className="flex flex-wrap gap-2 justify-end">
                        <Button
                          size="sm"
                          icon="medication"
                          loading={convertingId === item.id}
                          onClick={() => void onConvertToActiveTaking(item)}
                          title={isEn ? "Promote to active taking medication course" : "Tạo đợt dùng thuốc đang theo dõi trong hồ sơ"}
                        >
                          {isEn ? "Convert to Active Taking" : "Chuyển thành thuốc đang dùng"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon="edit"
                          onClick={() => openEditModal(item)}
                        >
                          {isEn ? "Edit" : "Sửa"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          icon="delete"
                          onClick={() => void onDelete(item.id)}
                        >
                          {t(language, "medicines.cabinet.delete")}
                        </Button>
                      </div>
                    </div>
                  </div>
                </SurfaceCard>
              );
            })}
          </div>
        </section>

        {/* Safe Medication Disposal Guidance Section */}
        <section aria-labelledby="disposal-guidance-heading" className="space-y-4 pt-4">
          <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Icon name="warning" size={22} className="text-[var(--status-warn-text)]" aria-hidden="true" />
              <h2 id="disposal-guidance-heading" className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                {isEn ? "Safe Medication Disposal Guidance" : "Hướng dẫn tiêu hủy thuốc an toàn & Đúng cách"}
              </h2>
            </div>

            <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
              {isEn
                ? "Proper disposal of expired or unwanted medications prevents accidental poisoning, antibiotic resistance, and environmental pollution of water supplies."
                : "Tiêu hủy thuốc hết hạn hoặc không còn sử dụng đúng quy trình giúp ngăn ngừa ngộ độc ngoài ý muốn, tránh tình trạng kháng thuốc và bảo vệ nguồn nước sinh hoạt không bị ô nhiễm dược phẩm."}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-4 space-y-1.5">
                <div className="flex items-center gap-2 text-[var(--status-danger-text)] font-bold text-xs">
                  <Icon name="close" size={16} aria-hidden="true" />
                  <span>{isEn ? "DO NOT Flush Down Toilet or Sink" : "KHÔNG xả thuốc xuống bồn cầu / cống"}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-5">
                  {isEn
                    ? "Never pour liquid medicines or flush pills into the sewer system as wastewater treatment plants cannot filter active pharmaceutical ingredients."
                    : "Tuyệt đối không đổ thuốc viên hay siro vào hệ thống thoát nước vì các trạm xử lý nước thải sinh hoạt không thể lọc bỏ hoàn toàn các hoạt chất dược lý."}
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-4 space-y-1.5">
                <div className="flex items-center gap-2 text-[var(--status-ok-text)] font-bold text-xs">
                  <Icon name="check" size={16} aria-hidden="true" />
                  <span>{isEn ? "Safe Household Waste Disposal" : "Xử lý rác thải an toàn tại nhà"}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-5">
                  {isEn
                    ? "Mix uncrushed pills with unpalatable substances (coffee grounds, cat litter, soil), seal in a plastic bag, and place in household trash."
                    : "Lấy thuốc ra khỏi vỉ, trộn đều với bã cà phê, mùn cưa hoặc đất cát, cho vào túi nilon buộc kín trước khi bỏ vào thùng rác gia đình thông thường."}
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-4 space-y-1.5">
                <div className="flex items-center gap-2 text-[var(--text-brand)] font-bold text-xs">
                  <Icon name="check" size={16} aria-hidden="true" />
                  <span>{isEn ? "Remove Personal Privacy Labels" : "Bảo vệ thông tin cá nhân"}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-5">
                  {isEn
                    ? "Scratch off or black out patient names and prescription numbers on packaging bottles before recycling or disposal."
                    : "Bóc hoặc gạch bỏ nhãn dán có tên người bệnh, số đơn thuốc trên lọ và vỏ hộp trước khi vứt bỏ bao bì để bảo mật quyền riêng tư y tế."}
                </p>
              </div>

              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-4 space-y-1.5">
                <div className="flex items-center gap-2 text-[var(--text-brand)] font-bold text-xs">
                  <Icon name="clinical-notes" size={16} aria-hidden="true" />
                  <span>{isEn ? "Pharmacy Take-Back Drop-offs" : "Điểm thu hồi thuốc y tế"}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-5">
                  {isEn
                    ? "Preferred: Bring unused or hazardous medications to designated hospital drop-off boxes or authorized pharmacy take-back programs."
                    : "Ưu tiên: Mang thuốc hết hạn đến các bệnh viện, trạm y tế hoặc nhà thuốc có điểm tiếp nhận chất thải y tế để được xử lý theo quy trình chuẩn."}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Edit Item Modal */}
        <Modal
          open={Boolean(editingItem)}
          onClose={() => setEditingItem(null)}
          title={isEn ? "Edit Cabinet Medication" : "Chỉnh sửa thuốc trong tủ"}
        >
          <div className="space-y-4 p-2">
            {editError ? <InlineError message={editError} /> : null}

            <Field
              id="cabinet-edit-name"
              label={isEn ? "Drug Name *" : "Tên thuốc *"}
              value={editDrugName}
              onChange={(e) => setEditDrugName(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-3">
              <Field
                id="cabinet-edit-brand"
                label={isEn ? "Brand Name" : "Tên thương mại"}
                value={editBrandName}
                onChange={(e) => setEditBrandName(e.target.value)}
              />
              <Field
                id="cabinet-edit-mfg"
                label={isEn ? "Manufacturer" : "Hãng sản xuất"}
                value={editManufacturer}
                onChange={(e) => setEditManufacturer(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field
                id="cabinet-edit-dose"
                label={isEn ? "Dosage" : "Liều dùng"}
                value={editDosage}
                onChange={(e) => setEditDosage(e.target.value)}
              />
              <Field
                id="cabinet-edit-qty"
                label={isEn ? "Quantity" : "Số lượng"}
                type="number"
                value={String(editQuantity)}
                onChange={(e) => setEditQuantity(Number(e.target.value) || 0)}
              />
            </div>
            <Field
              id="cabinet-edit-exp"
              label={isEn ? "Expiration Date (YYYY-MM-DD)" : "Hạn sử dụng (YYYY-MM-DD)"}
              type="date"
              value={editExpiresOn}
              onChange={(e) => setEditExpiresOn(e.target.value)}
            />

            <div className="flex justify-end gap-2 pt-4 border-t border-[color:var(--shell-border)]">
              <Button variant="ghost" onClick={() => setEditingItem(null)}>
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button loading={savingEdit} onClick={() => void saveItemEdit()}>
                {isEn ? "Save" : "Lưu thay đổi"}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </MedicalConsentGate>
  );
}
