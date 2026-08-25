"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "@/components/ui/icon";
import Badge from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  searchVietnameseDrugs,
  type VietnameseDrug,
} from "@/lib/vietnamese-drugs";
import { addCabinetItem } from "@/lib/selfmed";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

export type DrugAutocompleteSearchProps = {
  onSelectDrug?: (drug: VietnameseDrug) => void;
  onAddedToCabinet?: (drug: VietnameseDrug) => void;
  placeholder?: string;
  autoFocus?: boolean;
  className?: string;
  showPopularChips?: boolean;
  showCabinetAddButton?: boolean;
};

const POPULAR_DRUG_PRESETS = [
  "Panadol Extra",
  "Glucophage XR",
  "Coversyl",
  "Augmentin",
  "Lipitor",
  "Nexium Mups",
  "Plavix",
  "Concor",
  "Voltaren",
  "Aspirin Protect",
];

export function DrugAutocompleteSearch({
  onSelectDrug,
  onAddedToCabinet,
  placeholder,
  autoFocus = false,
  className = "",
  showPopularChips = true,
  showCabinetAddButton = true,
}: DrugAutocompleteSearchProps) {
  const language = useUILanguage();
  const isEn = language === "en";

  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<VietnameseDrug[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [addedMessage, setAddedMessage] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Search when query changes
  useEffect(() => {
    if (!query.trim()) {
      setResults(searchVietnameseDrugs("", 6));
      setSelectedIndex(-1);
      return;
    }
    const matched = searchVietnameseDrugs(query, 8);
    setResults(matched);
    setSelectedIndex(-1);
  }, [query]);

  // Click outside listener
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = useCallback(
    (drug: VietnameseDrug) => {
      onSelectDrug?.(drug);
      setIsOpen(false);
      setQuery("");
    },
    [onSelectDrug],
  );

  const handleQuickAddToCabinet = async (drug: VietnameseDrug, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setAddingId(drug.id);
    setAddedMessage(null);
    setAddError(null);
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
      const msg = isEn
        ? `Added "${drug.tradeName}" to medicine cabinet.`
        : `Đã thêm "${drug.tradeName}" vào Tủ thuốc gia đình.`;
      setAddedMessage(msg);
      onAddedToCabinet?.(drug);
      setTimeout(() => setAddedMessage(null), 4000);
    } catch (cause) {
      setAddError(
        safeUserFacingError(
          cause,
          isEn ? "Failed to add to cabinet." : "Không thể thêm vào tủ thuốc lúc này.",
        ),
      );
      setTimeout(() => setAddError(null), 4000);
    } finally {
      setAddingId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        setIsOpen(true);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        handleSelect(results[selectedIndex]);
      } else if (results.length > 0) {
        handleSelect(results[0]);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const handleChipClick = (presetName: string) => {
    const matched = searchVietnameseDrugs(presetName, 1);
    if (matched.length > 0) {
      handleSelect(matched[0]);
    } else {
      setQuery(presetName);
      setIsOpen(true);
    }
  };

  return (
    <div ref={containerRef} className={`relative w-full space-y-2.5 ${className}`}>
      {/* Toast Notification */}
      {addedMessage && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3.5 py-2 text-xs font-semibold text-[var(--status-ok-text)] transition-all animate-fadeIn"
        >
          <Icon name="check" size={16} aria-hidden="true" />
          <span>{addedMessage}</span>
        </div>
      )}

      {addError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3.5 py-2 text-xs font-semibold text-[var(--status-danger-text)] transition-all animate-fadeIn"
        >
          <Icon name="warning" size={16} aria-hidden="true" />
          <span>{addError}</span>
        </div>
      )}

      {/* Instant Search Bar */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[var(--text-muted)]">
          <Icon name="search" size={18} aria-hidden="true" />
        </div>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          autoFocus={autoFocus}
          placeholder={
            placeholder ||
            (isEn
              ? "Search Vietnamese drug trade names (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...)"
              : "Tìm tên biệt dược (Panadol, Glucophage, Coversyl, Augmentin, Lipitor...)")
          }
          className="w-full rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-3 pl-10 pr-10 text-sm font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] shadow-sm transition-all focus:border-[var(--brand-500)] focus:bg-[var(--surface-panel)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]/20"
          aria-label={isEn ? "Search medications" : "Tìm kiếm thuốc"}
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls="drug-autocomplete-listbox"
          role="combobox"
        />

        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              inputRef.current?.focus();
            }}
            className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            aria-label={isEn ? "Clear search" : "Xóa tìm kiếm"}
          >
            <Icon name="close" size={16} aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown Popup */}
      {isOpen && (
        <div
          id="drug-autocomplete-listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-1.5 shadow-xl backdrop-blur-md transition-all animate-fadeIn"
          role="listbox"
        >
          <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
            {query.trim()
              ? isEn
                ? `Results for "${query}" (${results.length})`
                : `Gợi ý thuốc biệt dược (${results.length})`
              : isEn
                ? "Popular Vietnamese Medications"
                : "Thuốc biệt dược phổ biến tại Việt Nam"}
          </div>

          {results.length === 0 ? (
            <div className="p-4 text-center text-xs text-[var(--text-secondary)]">
              {isEn
                ? "No matching medications found. You can still type custom names."
                : "Không tìm thấy thuốc khớp từ khóa. Bạn vẫn có thể nhập tên để kiểm tra."}
            </div>
          ) : (
            results.map((drug, index) => {
              const isSelected = selectedIndex === index;
              return (
                <div
                  key={drug.id}
                  onClick={() => handleSelect(drug)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`group flex cursor-pointer items-center justify-between gap-3 rounded-xl p-2.5 transition-colors ${
                    isSelected
                      ? "bg-[var(--surface-brand-soft)] text-[var(--text-primary)]"
                      : "hover:bg-[var(--surface-muted)] text-[var(--text-primary)]"
                  }`}
                  role="option"
                  aria-selected={isSelected}
                >
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <span
                      className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:bg-[var(--surface-panel)]"
                      aria-hidden="true"
                    >
                      <Icon name="medication" size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-bold text-sm text-[var(--text-primary)]">
                          {drug.tradeName}
                        </span>
                        <Badge tone="brand" className="text-[10px] py-0 px-1.5">
                          {drug.dosageForm}
                        </Badge>
                      </div>
                      <p className="truncate text-xs text-[var(--text-secondary)] mt-0.5">
                        <span className="font-semibold text-[var(--text-primary)]">Hoạt chất:</span>{" "}
                        {drug.activeIngredients}
                      </p>
                      <p className="truncate text-[11px] text-[var(--text-muted)] mt-0.5">
                        {drug.category} · {drug.manufacturer || "Dược phẩm"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {showCabinetAddButton && (
                      <Button
                        size="sm"
                        variant="secondary"
                        icon="medication"
                        loading={addingId === drug.id}
                        onClick={(e) => void handleQuickAddToCabinet(drug, e)}
                        title={
                          isEn
                            ? `Quick add ${drug.tradeName} to cabinet`
                            : `Thêm nhanh ${drug.tradeName} vào Tủ thuốc`
                        }
                        className="text-xs h-7 px-2"
                      >
                        {isEn ? "+ Cabinet" : "+ Tủ thuốc"}
                      </Button>
                    )}
                    <span className="text-xs font-semibold text-[var(--text-brand)] group-hover:underline">
                      {isEn ? "Select →" : "Chọn →"}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Popular Vietnamese Drug Trade Name Preset Chips */}
      {showPopularChips && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] mr-1 flex items-center gap-1">
            <Icon name="medication" size={13} aria-hidden="true" />
            {isEn ? "Popular in VN:" : "Thuốc phổ biến:"}
          </span>
          {POPULAR_DRUG_PRESETS.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => handleChipClick(name)}
              className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--brand-500)] hover:bg-[var(--surface-brand-soft)] hover:text-[var(--text-brand)] focus-ring"
            >
              <span>+ {name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default DrugAutocompleteSearch;
