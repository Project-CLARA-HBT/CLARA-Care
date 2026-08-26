"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type ClinicalSummaryScope = "day" | "week" | "episode" | "all";

export interface ClinicalSummaryItem {
  id: string;
  label: string;
  value: string;
  date?: string;
  status?: string;
  citation?: string;
  truthState?: string;
}

export interface ClinicalSummarySection {
  id: string;
  title: string;
  items: ClinicalSummaryItem[];
}

export interface ClinicalSummaryPreviewProps {
  patientName?: string;
  generatedAt?: string;
  scope?: ClinicalSummaryScope;
  onScopeChange?: (scope: ClinicalSummaryScope) => void;
  episodes?: Array<{ id: string; title: string }>;
  selectedEpisodeId?: string;
  onEpisodeChange?: (id: string) => void;
  overviewText?: string;
  sections?: ClinicalSummarySection[];
  onPrint?: () => void;
  onExport?: () => void;
  className?: string;
}

const DEFAULT_SECTIONS: ClinicalSummarySection[] = [
  {
    id: "journeys",
    title: "1. Tình trạng sức khỏe & Hành trình đang theo dõi",
    items: [
      {
        id: "j-1",
        label: "Hành trình chính",
        value: "Kiểm soát tăng huyết áp nguyên phát (Mục tiêu: < 130/80 mmHg)",
        date: "2026-08-01",
        status: "Đang duy trì",
        citation: "rev-001",
      },
    ],
  },
  {
    id: "vitals",
    title: "2. Chỉ số sinh tồn & Nhật ký đo lường (7 ngày gần nhất)",
    items: [
      {
        id: "v-1",
        label: "Huyết áp trung bình",
        value: "126/81 mmHg (Tâm thu: 122–129 mmHg, Tâm trương: 78–84 mmHg)",
        date: "2026-08-10",
        citation: "rev-005",
      },
      {
        id: "v-2",
        label: "Nhịp tim khi nghỉ",
        value: "74 bpm (Dao động: 68–78 bpm, nhịp đều)",
        date: "2026-08-10",
        citation: "rev-006",
      },
      {
        id: "v-3",
        label: "Tuân thủ đo lường",
        value: "Đo đều đặn 14/14 lần sáng và tối (100% mục tiêu)",
        date: "2026-08-10",
      },
    ],
  },
  {
    id: "medications",
    title: "3. Thuốc & Dược phẩm đang sử dụng",
    items: [
      {
        id: "m-1",
        label: "Amlodipine (Amlor 5mg)",
        value: "Uống 1 viên vào 07:00 sáng mỗi ngày sau ăn. Dung nạp tốt, không phù chân.",
        date: "2026-08-03",
        status: "Đang dùng",
        citation: "rev-003",
      },
    ],
  },
  {
    id: "labs",
    title: "4. Kết quả cận lâm sàng & Xét nghiệm mới nhất",
    items: [
      {
        id: "l-1",
        label: "Sinh hóa máu (Medlatec)",
        value: "Cholesterol toàn phần: 4.8 mmol/L, HbA1c: 5.6%, Triglyceride: 1.6 mmol/L.",
        date: "2026-08-05",
        status: "Bình thường",
        citation: "rev-004",
      },
    ],
  },
  {
    id: "observations",
    title: "5. Triệu chứng bất thường & Ghi chú tự theo dõi",
    items: [
      {
        id: "o-1",
        label: "Cơn chóng mặt nhẹ",
        value: "Ghi nhận 1 lần vào buổi chiều ngày 07/08 sau khi đứng lên nhanh, kéo dài 2-3 phút rồi tự hết.",
        date: "2026-08-07",
        truthState: "user_reported",
        citation: "rev-007",
      },
    ],
  },
];

export function ClinicalSummaryPreview({
  patientName = "Nguyễn Văn A",
  generatedAt = "2026-08-10T08:00:00Z",
  scope = "week",
  onScopeChange,
  episodes = [],
  selectedEpisodeId,
  onEpisodeChange,
  overviewText = "Bệnh nhân tuân thủ điều trị tăng huyết áp tốt. Huyết áp 7 ngày qua duy trì trong ngưỡng mục tiêu an toàn (< 130/80 mmHg). Không ghi nhận biến cố tim mạch hay tác dụng phụ nghiêm trọng của thuốc.",
  sections = DEFAULT_SECTIONS,
  onPrint,
  onExport,
  className = "",
}: ClinicalSummaryPreviewProps) {
  const language = useUILanguage();
  const [internalScope, setInternalScope] = useState<ClinicalSummaryScope>(scope);
  const [copied, setCopied] = useState(false);

  const activeScope = onScopeChange ? scope : internalScope;

  const handleScopeSelect = (newScope: ClinicalSummaryScope) => {
    setInternalScope(newScope);
    onScopeChange?.(newScope);
  };

  const handlePrint = () => {
    if (onPrint) {
      onPrint();
    } else if (typeof window !== "undefined") {
      window.print();
    }
  };

  const handleCopy = async () => {
    if (onExport) {
      onExport();
      return;
    }

    const textToCopy = `=== BẢN TÓM TẮT LÂM SÀNG LIFEMAP ===\nBệnh nhân: ${patientName}\nThời điểm: ${formatLocaleDate(language, generatedAt)}\n\nTổng quan:\n${overviewText}\n\n` +
      sections
        .map(
          (sec) =>
            `${sec.title}:\n` +
            sec.items.map((it) => `- ${it.label}: ${it.value}`).join("\n"),
        )
        .join("\n\n");

    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(textToCopy);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // ignore
    }
  };

  return (
    <div className={`space-y-6 ${className}`} data-testid="clinical-summary-preview">
      {/* Controls & Actions Bar */}
      <SurfaceCard className="p-4 rounded-xl border border-[var(--shell-border)] print:hidden">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="clinical-notes" />
            </span>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Bản tóm tắt y khoa
              </span>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                Tóm tắt chuẩn bị gặp Bác sĩ / Khám bệnh
              </h2>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Scope selection */}
            <div className="inline-flex rounded-lg border border-[var(--shell-border)] p-1 bg-[var(--surface-muted)] text-xs">
              {(["day", "week", "episode", "all"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleScopeSelect(s)}
                  className={`px-3 py-1 rounded-md font-medium transition-all ${
                    activeScope === s
                      ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {s === "day"
                    ? "Hôm nay"
                    : s === "week"
                      ? "7 ngày"
                      : s === "episode"
                        ? "Hành trình"
                        : "Tất cả"}
                </button>
              ))}
            </div>

            {activeScope === "episode" && episodes.length > 0 && (
              <select
                aria-label="Chọn hành trình tóm tắt"
                value={selectedEpisodeId ?? episodes[0]?.id ?? ""}
                onChange={(e) => onEpisodeChange?.(e.target.value)}
                className="rounded-lg border border-[var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-primary)]"
              >
                {episodes.map((ep) => (
                  <option key={ep.id} value={ep.id}>
                    {ep.title}
                  </option>
                ))}
              </select>
            )}

            <Button
              size="sm"
              variant="secondary"
              icon="content_copy"
              onClick={() => void handleCopy()}
            >
              {copied ? "Đã sao chép" : "Sao chép"}
            </Button>

            <Button
              size="sm"
              variant="primary"
              icon="print"
              onClick={handlePrint}
            >
              In / Xuất PDF
            </Button>
          </div>
        </div>
      </SurfaceCard>

      {/* Printable Clinical Sheet Surface */}
      <SurfaceCard className="p-8 rounded-2xl border border-[var(--shell-border)] bg-white text-black shadow-sm space-y-6 print:border-none print:shadow-none print:p-0">
        {/* Document Header */}
        <div className="border-b-2 border-gray-900 pb-4">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-gray-500">
                CLARA Health Engine · Hồ sơ tự quản lý LifeMap
              </span>
              <h1 className="text-xl font-bold text-gray-900 mt-1">
                BẢN TÓM TẮT DIỄN BIẾN SỨC KHỎE
              </h1>
            </div>
            <div className="text-right text-xs text-gray-600 font-mono">
              <p>Ngày lập: {formatLocaleDate(language, generatedAt, { dateStyle: "long" })}</p>
              <p>Mã hồ sơ: LM-2026-9921</p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-3 border-t border-gray-200 text-xs">
            <div>
              <span className="text-gray-500 block">Bệnh nhân:</span>
              <span className="font-bold text-gray-900">{patientName}</span>
            </div>
            <div>
              <span className="text-gray-500 block">Phạm vi tóm tắt:</span>
              <span className="font-semibold text-gray-900">
                {activeScope === "day"
                  ? "Trong ngày"
                  : activeScope === "week"
                    ? "7 ngày qua"
                    : activeScope === "episode"
                      ? "Theo hành trình"
                      : "Toàn bộ"}
              </span>
            </div>
            <div>
              <span className="text-gray-500 block">Nguồn chứng cứ:</span>
              <span className="font-semibold text-gray-900">Bitemporal EMR + IoT</span>
            </div>
            <div>
              <span className="text-gray-500 block">Trạng thái:</span>
              <span className="font-semibold text-green-700">Đã đối chiếu</span>
            </div>
          </div>
        </div>

        {/* Clinical Overview Box */}
        {overviewText && (
          <div className="rounded-xl bg-blue-50 border border-blue-200 p-4 text-sm leading-relaxed text-blue-950">
            <h3 className="font-bold text-xs uppercase tracking-wider text-blue-800 mb-1 flex items-center gap-1.5">
              <Icon name="clinical-notes" size={14} />
              Đánh giá tổng quan
            </h3>
            <p>{overviewText}</p>
          </div>
        )}

        {/* Structured Sections */}
        <div className="space-y-6">
          {sections.map((section) => (
            <div key={section.id} className="space-y-2">
              <h3 className="text-sm font-bold text-gray-900 border-b border-gray-300 pb-1">
                {section.title}
              </h3>

              <div className="divide-y divide-gray-100">
                {section.items.map((item) => (
                  <div key={item.id} className="py-2 flex flex-col sm:flex-row sm:items-start justify-between gap-2 text-xs">
                    <div className="sm:w-1/3 font-semibold text-gray-700">
                      {item.label}
                      {item.date && (
                        <span className="block text-[11px] font-normal text-gray-500">
                          {formatLocaleDate(language, item.date, { dateStyle: "short" })}
                        </span>
                      )}
                    </div>

                    <div className="sm:w-2/3 text-gray-900">
                      <p className="leading-relaxed">{item.value}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {item.status && (
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-700">
                            {item.status}
                          </span>
                        )}
                        {item.truthState && (
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                            {item.truthState === "user_reported" ? "Người bệnh tự ghi" : item.truthState}
                          </span>
                        )}
                        {item.citation && (
                          <span className="text-[10px] font-mono text-gray-400">
                            ref: #{item.citation}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Disclaimer Footer */}
        <div className="pt-4 border-t border-gray-300 text-[11px] text-gray-500 leading-normal">
          <p className="font-semibold text-gray-700">
            * Lưu ý an toàn y khoa:
          </p>
          <p>
            Bản tóm tắt này được tổng hợp tự động từ nhật ký theo dõi của bệnh nhân và hồ sơ kết nối, nhằm hỗ trợ chuẩn bị thông tin cho buổi khám. Tài liệu không phải là chẩn đoán y khoa, không thay thế ý kiến chuyên môn của bác sĩ.
          </p>
        </div>
      </SurfaceCard>
    </div>
  );
}

export default ClinicalSummaryPreview;
