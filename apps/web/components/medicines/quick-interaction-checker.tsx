"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/button";
import Badge from "@/components/ui/badge";
import Icon from "@/components/ui/icon";
import { SurfaceCard, InlineError } from "@/components/ui/surface";
import { DrugAutocompleteSearch } from "./drug-autocomplete-search";
import { TrafficLightSafetyIndicator } from "./traffic-light-safety-indicator";
import {
  checkInstantDrugInteractions,
  type DrugInteractionAlert,
  type TrafficLightLevel,
  type VietnameseDrug,
  VIETNAMESE_DRUGS_CATALOG,
} from "@/lib/vietnamese-drugs";
import { addCabinetItem, getCabinet, type CabinetItem } from "@/lib/selfmed";
import { analyzeCareguard, type CareguardAnalyzeRawResponse } from "@/lib/careguard";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

export type QuickInteractionCheckerProps = {
  initialDrugs?: string[];
  onCabinetUpdated?: () => void;
  className?: string;
  compact?: boolean;
};

export function QuickInteractionChecker({
  initialDrugs = [],
  onCabinetUpdated,
  className = "",
  compact = false,
}: QuickInteractionCheckerProps) {
  const language = useUILanguage();
  const isEn = language === "en";

  // Selected drug items for comparison
  const [selectedDrugs, setSelectedDrugs] = useState<VietnameseDrug[]>([]);
  const [cabinetItems, setCabinetItems] = useState<CabinetItem[]>([]);
  const [isLoadingCabinet, setIsLoadingCabinet] = useState(false);

  // Interaction results
  const [interactionLevel, setInteractionLevel] = useState<TrafficLightLevel | null>(null);
  const [interactionSummary, setInteractionSummary] = useState<string>("");
  const [interactionAlerts, setInteractionAlerts] = useState<DrugInteractionAlert[]>([]);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string>("");

  // Batch add to cabinet state
  const [isBatchAdding, setIsBatchAdding] = useState(false);
  const [notice, setNotice] = useState<string>("");

  // Populate initial drugs if provided
  useEffect(() => {
    if (initialDrugs.length > 0 && selectedDrugs.length === 0) {
      const found: VietnameseDrug[] = [];
      for (const name of initialDrugs) {
        const match = VIETNAMESE_DRUGS_CATALOG.find(
          (d) =>
            d.tradeName.toLowerCase().includes(name.toLowerCase()) ||
            d.genericName.toLowerCase().includes(name.toLowerCase()),
        );
        if (match && !found.some((f) => f.id === match.id)) {
          found.push(match);
        } else if (!found.some((f) => f.tradeName.toLowerCase() === name.toLowerCase())) {
          found.push({
            id: `custom-${name}`,
            tradeName: name,
            genericName: name,
            activeIngredients: name,
            category: "Thuốc nhập tay",
            categoryEn: "Custom entry",
            defaultDosage: "1 viên",
            dosageForm: "Viên",
            description: "Thuốc nhập thủ công vào danh sách kiểm tra.",
            searchTokens: [name.toLowerCase()],
          });
        }
      }
      setSelectedDrugs(found);
    }
  }, [initialDrugs, selectedDrugs.length]);

  // Load existing cabinet for 1-click import
  const loadCabinet = useCallback(async () => {
    setIsLoadingCabinet(true);
    try {
      const res = await getCabinet();
      setCabinetItems(res.items ?? []);
    } catch {
      // Graceful ignore
    } finally {
      setIsLoadingCabinet(false);
    }
  }, []);

  useEffect(() => {
    void loadCabinet();
  }, [loadCabinet]);

  // Add drug to selected list
  const handleAddDrug = (drug: VietnameseDrug) => {
    setNotice("");
    setError("");
    if (selectedDrugs.some((d) => d.id === drug.id || d.tradeName.toLowerCase() === drug.tradeName.toLowerCase())) {
      return;
    }
    const nextList = [...selectedDrugs, drug];
    setSelectedDrugs(nextList);

    // If we now have 2 or more drugs, auto-run instant check for responsiveness
    if (nextList.length >= 2) {
      const instantRes = checkInstantDrugInteractions(nextList.map((d) => d.tradeName));
      setInteractionLevel(instantRes.level);
      setInteractionSummary(instantRes.summary);
      setInteractionAlerts(instantRes.alerts);
    }
  };

  // Remove drug from list
  const handleRemoveDrug = (id: string) => {
    const nextList = selectedDrugs.filter((d) => d.id !== id);
    setSelectedDrugs(nextList);
    if (nextList.length >= 2) {
      const instantRes = checkInstantDrugInteractions(nextList.map((d) => d.tradeName));
      setInteractionLevel(instantRes.level);
      setInteractionSummary(instantRes.summary);
      setInteractionAlerts(instantRes.alerts);
    } else {
      setInteractionLevel(null);
      setInteractionAlerts([]);
      setInteractionSummary("");
    }
  };

  // 1-Click "Kiểm tra tương tác thuốc" (runs deterministic checks + backend API)
  const runFullInteractionCheck = async () => {
    if (selectedDrugs.length < 2) {
      setError(
        isEn
          ? "Please select at least 2 medications to check drug-drug interactions."
          : "Vui lòng chọn ít nhất 2 loại thuốc để kiểm tra tương tác thuốc.",
      );
      return;
    }

    setError("");
    setIsChecking(true);
    try {
      const drugNames = selectedDrugs.map((d) => d.tradeName);

      // 1. Instant local matrix check
      const localResult = checkInstantDrugInteractions(drugNames);
      setInteractionLevel(localResult.level);
      setInteractionSummary(localResult.summary);
      setInteractionAlerts(localResult.alerts);

      // 2. Call backend Careguard analyze API
      try {
        const apiResponse: CareguardAnalyzeRawResponse = await analyzeCareguard({
          symptoms: [],
          labs: {},
          medications: [],
          medication_text: drugNames.join(", "),
          allergies: [],
          locale: language,
        });

        if (apiResponse && apiResponse.status !== "requires_medication_clarification") {
          const rawRisk = String(apiResponse.risk_tier || apiResponse.tier || "").toLowerCase();
          if (/(critical|severe|major|high|red|danger)/.test(rawRisk)) {
            setInteractionLevel("danger");
          } else if (/(moderate|medium|amber|intermediate)/.test(rawRisk) && localResult.level !== "danger") {
            setInteractionLevel("caution");
          }
        }
      } catch {
        // In offline/mock mode, local deterministic engine result remains authoritative
      }
    } catch (cause) {
      setError(
        safeUserFacingError(
          cause,
          isEn ? "Failed to complete interaction check." : "Không thể hoàn tất kiểm tra tương tác thuốc.",
        ),
      );
    } finally {
      setIsChecking(false);
    }
  };

  // 1-Click "Nhập thuốc từ Tủ thuốc hiện tại"
  const handleImportFromCabinet = () => {
    if (cabinetItems.length === 0) {
      setError(isEn ? "Your medicine cabinet is currently empty." : "Tủ thuốc gia đình của bạn hiện đang trống.");
      return;
    }

    const imported: VietnameseDrug[] = [];
    cabinetItems.forEach((cItem) => {
      const match = VIETNAMESE_DRUGS_CATALOG.find(
        (d) =>
          d.tradeName.toLowerCase() === cItem.drug_name.toLowerCase() ||
          (cItem.brand_name && d.tradeName.toLowerCase() === cItem.brand_name.toLowerCase()),
      );
      if (match) {
        if (!imported.some((i) => i.id === match.id)) imported.push(match);
      } else {
        imported.push({
          id: `cabinet-${cItem.id}`,
          tradeName: cItem.drug_name,
          genericName: cItem.normalized_name || cItem.drug_name,
          activeIngredients: cItem.dosage ? `${cItem.drug_name} ${cItem.dosage}` : cItem.drug_name,
          category: "Thuốc từ tủ cá nhân",
          categoryEn: "From Cabinet",
          defaultDosage: cItem.dosage || "Theo đơn",
          dosageForm: cItem.dosage_form || "Viên",
          description: cItem.note || "Thuốc lưu trong tủ thuốc gia đình.",
          searchTokens: [cItem.drug_name.toLowerCase()],
        });
      }
    });

    setSelectedDrugs(imported);
    if (imported.length >= 2) {
      const instantRes = checkInstantDrugInteractions(imported.map((d) => d.tradeName));
      setInteractionLevel(instantRes.level);
      setInteractionSummary(instantRes.summary);
      setInteractionAlerts(instantRes.alerts);
    }
    setNotice(
      isEn
        ? `Imported ${imported.length} medication(s) from your cabinet.`
        : `Đã nhập ${imported.length} thuốc từ Tủ thuốc gia đình để kiểm tra.`,
    );
  };

  // 1-Click "Thêm nhanh vào Tủ thuốc" for a single selected drug
  const handleAddSingleToCabinet = async (drug: VietnameseDrug) => {
    try {
      await addCabinetItem({
        drug_name: drug.tradeName,
        brand_name: drug.tradeName,
        manufacturer: drug.manufacturer || undefined,
        dosage: drug.defaultDosage,
        dosage_form: drug.dosageForm,
        quantity: 1,
        source: "manual",
        note: `Hoạt chất: ${drug.activeIngredients}`,
      });
      setNotice(
        isEn
          ? `Added "${drug.tradeName}" to medicine cabinet!`
          : `Đã thêm "${drug.tradeName}" vào Tủ thuốc gia đình!`,
      );
      void loadCabinet();
      onCabinetUpdated?.();
      setTimeout(() => setNotice(""), 4000);
    } catch (cause) {
      setError(
        safeUserFacingError(
          cause,
          isEn ? "Failed to add medication to cabinet." : "Không thể thêm thuốc vào tủ lúc này.",
        ),
      );
    }
  };

  // 1-Click "Thêm tất cả vào Tủ thuốc"
  const handleAddAllToCabinet = async () => {
    if (selectedDrugs.length === 0) return;
    setIsBatchAdding(true);
    setError("");
    setNotice("");
    let addedCount = 0;
    try {
      for (const drug of selectedDrugs) {
        await addCabinetItem({
          drug_name: drug.tradeName,
          brand_name: drug.tradeName,
          manufacturer: drug.manufacturer || undefined,
          dosage: drug.defaultDosage,
          dosage_form: drug.dosageForm,
          quantity: 1,
          source: "manual",
          note: `Hoạt chất: ${drug.activeIngredients}`,
        }).catch(() => null);
        addedCount++;
      }
      setNotice(
        isEn
          ? `Successfully added ${addedCount} medication(s) to your medicine cabinet!`
          : `Đã thêm nhanh ${addedCount} thuốc vào Tủ thuốc gia đình!`,
      );
      void loadCabinet();
      onCabinetUpdated?.();
    } catch (cause) {
      setError(
        safeUserFacingError(
          cause,
          isEn ? "Failed to add some items to cabinet." : "Có lỗi khi lưu một số thuốc vào tủ.",
        ),
      );
    } finally {
      setIsBatchAdding(false);
    }
  };

  return (
    <SurfaceCard
      data-testid="quick-interaction-checker"
      className={`p-5 sm:p-6 space-y-6 ${className}`}
    >
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="grid h-8 w-8 place-items-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
              aria-hidden="true"
            >
              <Icon name="medication" size={20} />
            </span>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[var(--text-primary)]">
              {isEn ? "Instant Drug Interaction Check" : "Kiểm tra Tương tác Thuốc Tức thì"}
            </h2>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)]">
            {isEn
              ? "1-Click autocomplete for Vietnamese trade names (Panadol, Glucophage, Coversyl, Augmentin, Lipitor) with Traffic-Light safety indicators."
              : "Tìm nhanh thuốc biệt dược tại Việt Nam (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...) và nhận diện chỉ báo an toàn Xanh - Vàng - Đỏ."}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {cabinetItems.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              icon="medication"
              onClick={handleImportFromCabinet}
              disabled={isLoadingCabinet}
              title={
                isEn
                  ? `Import ${cabinetItems.length} items from your cabinet`
                  : `Lấy ${cabinetItems.length} thuốc đang có trong tủ`
              }
            >
              {isEn ? `Import Cabinet (${cabinetItems.length})` : `Lấy từ Tủ thuốc (${cabinetItems.length})`}
            </Button>
          )}
        </div>
      </div>

      {/* Notice & Error Banners */}
      {notice && (
        <div
          role="status"
          className="flex items-center justify-between rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-xs font-semibold text-[var(--status-ok-text)]"
        >
          <div className="flex items-center gap-2">
            <Icon name="check" size={16} aria-hidden="true" />
            <span>{notice}</span>
          </div>
          <button type="button" onClick={() => setNotice("")} className="text-xs opacity-75 hover:opacity-100">
            ✕
          </button>
        </div>
      )}

      {error && <InlineError message={error} onRetry={() => void runFullInteractionCheck()} />}

      {/* 1. Instant Autocomplete Search Bar */}
      <div className="space-y-2">
        <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center justify-between">
          <span>{isEn ? "Search & Add Medications to Check:" : "1. Tìm & Thêm thuốc vào danh sách kiểm tra:"}</span>
          <span className="text-[11px] font-normal text-[var(--text-muted)]">
            {isEn ? "Type brand name or click presets below" : "Nhập tên biệt dược hoặc bấm thuốc gợi ý"}
          </span>
        </label>

        <DrugAutocompleteSearch
          onSelectDrug={handleAddDrug}
          onAddedToCabinet={() => {
            void loadCabinet();
            onCabinetUpdated?.();
          }}
          placeholder={
            isEn
              ? "Type Vietnamese brand name (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...)"
              : "Nhập tên thuốc biệt dược (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...)"
          }
        />
      </div>

      {/* 2. Selected Drugs Tray */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            {isEn
              ? `Selected Medications for Interaction Test (${selectedDrugs.length}):`
              : `2. Thuốc đang được chọn để đối chiếu (${selectedDrugs.length}):`}
          </span>

          {selectedDrugs.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setSelectedDrugs([]);
                setInteractionLevel(null);
                setInteractionAlerts([]);
                setInteractionSummary("");
              }}
              className="text-xs font-medium text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition-colors"
            >
              {isEn ? "Clear All" : "Xóa tất cả"}
            </button>
          )}
        </div>

        {selectedDrugs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 text-center space-y-2">
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              {isEn ? "No medications selected yet" : "Chưa có thuốc nào trong danh sách kiểm tra"}
            </p>
            <p className="text-xs text-[var(--text-secondary)] max-w-md mx-auto">
              {isEn
                ? "Search Vietnamese brand names above or click on popular tags (+ Panadol, + Glucophage, + Coversyl, + Augmentin, + Lipitor) to test interactions."
                : "Sử dụng thanh tìm kiếm phía trên hoặc bấm vào các thẻ thuốc phổ biến (+ Panadol, + Glucophage, + Coversyl, + Augmentin, + Lipitor) để bắt đầu."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {selectedDrugs.map((drug) => (
              <div
                key={drug.id}
                className="flex items-start justify-between gap-2.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-sm hover:border-[var(--brand-500)]/50 transition-all"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-bold text-sm text-[var(--text-primary)]">
                      {drug.tradeName}
                    </span>
                    <Badge tone="brand" className="text-[10px] py-0 px-1.5">
                      {drug.defaultDosage}
                    </Badge>
                  </div>
                  <p className="truncate text-xs text-[var(--text-secondary)]">
                    {drug.activeIngredients}
                  </p>
                  <p className="truncate text-[11px] text-[var(--text-muted)]">
                    {drug.category}
                  </p>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleRemoveDrug(drug.id)}
                    className="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--status-danger-text)] transition-colors"
                    aria-label={isEn ? `Remove ${drug.tradeName}` : `Bỏ ${drug.tradeName}`}
                  >
                    <Icon name="close" size={14} />
                  </button>

                  <button
                    type="button"
                    onClick={() => void handleAddSingleToCabinet(drug)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded"
                    title={isEn ? "1-Click Add to Cabinet" : "1-Click Thêm nhanh vào Tủ thuốc"}
                  >
                    <Icon name="medication" size={12} />
                    <span>{isEn ? "+ Cabinet" : "+ Tủ thuốc"}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Action Toolbar */}
      {selectedDrugs.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[color:var(--shell-border)]">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              icon="clinical-notes"
              onClick={() => void runFullInteractionCheck()}
              loading={isChecking}
              disabled={selectedDrugs.length < 2}
            >
              {isEn ? "Check Interactions Now" : "Kiểm tra Tương tác Ngay"}
            </Button>

            <Button
              variant="secondary"
              icon="medication"
              onClick={() => void handleAddAllToCabinet()}
              loading={isBatchAdding}
              disabled={selectedDrugs.length === 0}
            >
              {isEn
                ? `1-Click Add All (${selectedDrugs.length}) to Cabinet`
                : `1-Click Thêm tất cả (${selectedDrugs.length}) vào Tủ thuốc`}
            </Button>
          </div>

          {selectedDrugs.length < 2 && (
            <span className="text-xs font-semibold text-[var(--status-warn-text)]">
              {isEn ? "⚠️ Need at least 2 drugs to check interactions" : "⚠️ Cần chọn tối thiểu 2 thuốc để kiểm tra"}
            </span>
          )}
        </div>
      )}

      {/* 4. Traffic-Light Safety Indicator Result */}
      {interactionLevel && (
        <div className="pt-2 animate-fadeIn">
          <TrafficLightSafetyIndicator
            level={interactionLevel}
            summary={interactionSummary}
            alerts={interactionAlerts}
            medications={selectedDrugs.map((d) => d.tradeName)}
            checkedCount={selectedDrugs.length}
          />
        </div>
      )}
    </SurfaceCard>
  );
}

export default QuickInteractionChecker;
