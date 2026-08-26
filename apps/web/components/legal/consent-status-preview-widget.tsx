"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  isGranularConsentEnabled,
  listConsents,
  type ConsentPurpose,
} from "@/lib/compliance";
import { LEGAL_POLICY_VERSION } from "@/lib/legal";

export interface PurposePreviewItem {
  id: string;
  purposeKey: string;
  title: string;
  shortLabel: string;
  type: "mandatory" | "optional" | "anonymized" | "cross_border";
  typeLabel: string;
  statutoryBasis: string;
  icon: IconName;
  description: string;
  locked?: boolean;
  consequenceWhenGranted: string;
  consequenceWhenRevoked: string;
}

export const PREVIEW_PURPOSES: PurposePreviewItem[] = [
  {
    id: "core-health-assistance",
    purposeKey: "medical_ai_reasoning",
    title: "1. Trợ lý thông tin y tế & Kiểm tra an toàn tương tác thuốc (Core Assistance & DDI)",
    shortLabel: "Trợ lý lâm sàng & DDI",
    type: "mandatory",
    typeLabel: "Bắt buộc cốt lõi",
    statutoryBasis: "Điều 15 Luật Khám bệnh 2023 · FIDES Safety Gate",
    icon: "clinical-notes",
    locked: true,
    description:
      "Phân tích tri thức y khoa đối chiếu Living Evidence, Dược thư Quốc gia và kiểm tra tương tác thuốc FIDES. Chuỗi suy luận Zero-CoT bị tiêu hủy ngay sau phiên.",
    consequenceWhenGranted:
      "Kích hoạt tra cứu an toàn thuốc, phát hiện tương tác thuốc bất lợi (DDI) và chuẩn bị nội dung trước khám.",
    consequenceWhenRevoked:
      "Đây là căn cứ bắt buộc để sử dụng dịch vụ CLARA. Không thể tắt riêng lẻ khi tài khoản đang hoạt động.",
  },
  {
    id: "lifemap-timeline",
    purposeKey: "personalization",
    title: "2. Dòng thời gian sinh hiệu & Tổng hợp bối cảnh LifeMap (Longitudinal Synthesis)",
    shortLabel: "LifeMap & Sinh hiệu",
    type: "optional",
    typeLabel: "Tùy chọn · Gated",
    statutoryBasis: "Điều 9 & 13 Nghị định 13/2023/NĐ-CP (Dữ liệu sức khỏe)",
    icon: "progress",
    locked: false,
    description:
      "Tổng hợp dữ liệu hồ sơ sức khỏe cá nhân (PHR), theo dõi chuỗi chỉ số sinh hiệu theo thời gian thực và xây dựng biểu đồ LifeMap hỗ trợ bác sĩ nắm bắt diễn tiến.",
    consequenceWhenGranted:
      "Mở khóa biểu đồ xu hướng huyết áp/đường huyết, cảnh báo diễn tiến bất thường và tổng hợp bệnh sử dài hạn.",
    consequenceWhenRevoked:
      "Hệ thống dừng tổng hợp diễn tiến sinh hiệu; dữ liệu cũ được lưu trữ ở chế độ tĩnh không phân tích bối cảnh.",
  },
  {
    id: "biomedical-research",
    purposeKey: "research",
    title: "3. Nghiên cứu y sinh học & Đối chiếu y văn sống (Biomedical Research - Zero-PII)",
    shortLabel: "Nghiên cứu ẩn danh",
    type: "anonymized",
    typeLabel: "Ẩn danh 100%",
    statutoryBasis: "Điều 21 Nghị định 13/2023/NĐ-CP (Nghiên cứu khoa học)",
    icon: "scan",
    locked: false,
    description:
      "Đóng góp dữ liệu hỏi đáp lâm sàng đã loại bỏ 100% thông tin định danh (Zero-PII) phục vụ đánh giá độ chính xác của AI và cập nhật Living Evidence tại Việt Nam.",
    consequenceWhenGranted:
      "Dữ liệu khử định danh góp phần nâng cao chất lượng phác đồ y văn sống phục vụ cộng đồng y tế Việt Nam.",
    consequenceWhenRevoked:
      "Tuyệt đối không thu thập hoặc trích xuất bất kỳ dữ liệu nào từ tài khoản của bạn cho mục đích nghiên cứu.",
  },
  {
    id: "cross-border-inference",
    purposeKey: "cross_border_processing",
    title: "4. Suy luận mô hình xuyên biên giới không lưu vết (YEScale DeepSeek with TIA)",
    shortLabel: "Suy luận DeepSeek (TIA)",
    type: "cross_border",
    typeLabel: "TIA · Zero Data Retention",
    statutoryBasis: "Điều 25 Nghị định 13/2023/NĐ-CP (Đánh giá TIA)",
    icon: "settings",
    locked: false,
    description:
      "Xử lý suy luận y khoa nâng cao qua điểm cuối YEScale DeepSeek đã thực hiện Đánh giá tác động TIA, cam kết Zero Data Retention (ZDR) và mã hóa kênh truyền TLS 1.3.",
    consequenceWhenGranted:
      "Sử dụng đầy đủ năng lực suy luận chuyên sâu từ mô hình ngôn ngữ lớn DeepSeek với độ chính xác lâm sàng cao.",
    consequenceWhenRevoked:
      "Tạm dừng gửi truy vấn tới điểm cuối suy luận nâng cao; hệ thống chuyển sang chế độ tra cứu từ điển cục bộ.",
  },
  {
    id: "family-clinician-sharing",
    purposeKey: "sharing",
    title: "5. Chia sẻ hồ sơ PHR có ranh giới cho người thân & Bác sĩ (Bounded PHR Sharing)",
    shortLabel: "Chia sẻ PHR an toàn",
    type: "optional",
    typeLabel: "Tùy chọn · Bounded",
    statutoryBasis: "Điều 17 Nghị định 13/2023/NĐ-CP (Ủy quyền tiếp cận)",
    icon: "share",
    locked: false,
    description:
      "Cấp quyền xem hồ sơ PHR và nhắc uống thuốc cho người thân hoặc bác sĩ điều trị qua liên kết mã hóa có thời hạn và mã xác thực PIN bảo mật.",
    consequenceWhenGranted:
      "Người chăm sóc hoặc bác sĩ được ủy quyền có thể theo dõi diễn tiến dùng thuốc và sinh hiệu để phối hợp điều trị.",
    consequenceWhenRevoked:
      "Toàn bộ liên kết chia sẻ và quyền truy cập bị thu hồi ngay lập tức; dữ liệu trở về chế độ riêng tư 100%.",
  },
];

export function ConsentStatusPreviewWidget() {
  const [activeStates, setActiveStates] = useState<Record<string, boolean>>({
    medical_ai_reasoning: true,
    personalization: true,
    research: true,
    cross_border_processing: true,
    sharing: false,
  });
  const [selectedPillarId, setSelectedPillarId] = useState<string>("core-health-assistance");
  const [auditHash, setAuditHash] = useState<string>("SHA256:7B8F12A9");
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);

  // Sync with live compliance state if available
  useEffect(() => {
    let mounted = true;
    if (!isGranularConsentEnabled()) return;

    async function loadLiveConsent() {
      try {
        const res = await listConsents();
        if (mounted && res.enabled && res.consents) {
          const map: Record<string, boolean> = { medical_ai_reasoning: true };
          for (const c of res.consents) {
            map[c.purpose] = c.granted;
          }
          setActiveStates((prev) => ({ ...prev, ...map }));
          setIsLiveConnected(true);
        }
      } catch {
        // Fallback to local simulation mode gracefully
      }
    }

    void loadLiveConsent();
    return () => {
      mounted = false;
    };
  }, []);

  const handleToggle = useCallback((purposeKey: string, locked?: boolean) => {
    if (locked) return;
    setActiveStates((prev) => {
      const nextVal = !prev[purposeKey];
      const nextMap = { ...prev, [purposeKey]: nextVal };
      // Regenerate simulated audit hash on modification
      const randomSuffix = Math.random().toString(16).substring(2, 10).toUpperCase();
      setAuditHash(`SHA256:${randomSuffix}`);
      return nextMap;
    });
  }, []);

  const handleReset = useCallback(() => {
    setActiveStates({
      medical_ai_reasoning: true,
      personalization: true,
      research: true,
      cross_border_processing: true,
      sharing: false,
    });
    setAuditHash("SHA256:7B8F12A9");
  }, []);

  const activeCount = useMemo(() => {
    return PREVIEW_PURPOSES.filter((p) =>
      p.locked ? true : Boolean(activeStates[p.purposeKey]),
    ).length;
  }, [activeStates]);

  const selectedPillar = useMemo(() => {
    return (
      PREVIEW_PURPOSES.find((p) => p.id === selectedPillarId) ??
      PREVIEW_PURPOSES[0]
    );
  }, [selectedPillarId]);

  const isSelectedActive = selectedPillar.locked
    ? true
    : Boolean(activeStates[selectedPillar.purposeKey]);

  return (
    <div
      data-testid="interactive-consent-preview-widget"
      className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-500)]/40 bg-[var(--surface-panel)] p-5 sm:p-7 shadow-md space-y-6 relative overflow-hidden"
    >
      {/* Background ambient glow */}
      <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-[var(--brand-500)]/10 blur-3xl" />

      {/* 1. Widget Header */}
      <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[color:var(--shell-border)]/70 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge tone="brand" icon="clinical-notes">
              Bảng điều khiển tương tác
            </Badge>
            {isLiveConnected ? (
              <Badge tone="ok" icon="check">
                Đồng bộ tài khoản thực
              </Badge>
            ) : (
              <Badge tone="neutral">Mô phỏng chính sách</Badge>
            )}
          </div>
          <h3 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
            Xem trước trạng thái đồng thuận theo mục đích (Purpose-Gated Posture)
          </h3>
          <p className="text-xs text-[var(--text-secondary)]">
            Trực tiếp thử nghiệm và kiểm tra cơ chế phân quyền độc lập của 5 trụ cột đồng thuận y tế.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-center">
            <span className="text-[10px] uppercase font-bold text-[var(--text-muted)] block">
              Trạng thái kích hoạt
            </span>
            <span className="text-sm font-extrabold text-[var(--text-brand)]">
              {activeCount} / 5 Trụ cột
            </span>
          </div>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
            title="Khôi phục trạng thái xem trước mặc định"
          >
            <Icon name="refresh" size="0.9rem" className="mr-1" />
            <span>Đặt lại</span>
          </button>
        </div>
      </div>

      {/* 2. Five Purpose Pillars Interactive Rows */}
      <div className="relative z-10 space-y-3">
        <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
          Danh mục 5 trụ cột đồng thuận y tế (Click vào dòng để xem chi tiết tác động):
        </p>

        <div className="grid gap-3">
          {PREVIEW_PURPOSES.map((item) => {
            const isGranted = item.locked ? true : Boolean(activeStates[item.purposeKey]);
            const isSelected = selectedPillarId === item.id;

            return (
              <div
                key={item.id}
                onClick={() => setSelectedPillarId(item.id)}
                className={[
                  "cursor-pointer rounded-xl border p-4 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3",
                  isSelected
                    ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)]/40 ring-1 ring-[var(--brand-500)]/30"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border)]/90 hover:bg-[var(--surface-muted)]/50",
                ].join(" ")}
                data-testid={`preview-pillar-row-${item.purposeKey}`}
              >
                {/* Left meta */}
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <div
                    className={[
                      "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border mt-0.5",
                      isGranted
                        ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/40 text-[var(--status-ok-text)]"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-muted)]",
                    ].join(" ")}
                  >
                    <Icon name={item.icon} size="1rem" />
                  </div>

                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                        {item.title}
                      </span>
                      <Badge
                        tone={
                          item.locked
                            ? "ok"
                            : isGranted
                              ? "ok"
                              : "neutral"
                        }
                      >
                        {item.locked
                          ? "Bắt buộc · Đang bật"
                          : isGranted
                            ? "Đang kích hoạt"
                            : "Đã tạm dừng"}
                      </Badge>
                      <span className="text-[11px] font-mono text-[var(--text-muted)] hidden md:inline">
                        {item.statutoryBasis}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] line-clamp-1">
                      {item.description}
                    </p>
                  </div>
                </div>

                {/* Right Toggle Control */}
                <div
                  className="flex items-center gap-3 shrink-0 self-end sm:self-center pt-2 sm:pt-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="text-xs font-semibold text-[var(--text-muted)] hidden sm:inline">
                    {item.locked ? "Cố định" : isGranted ? "Bật" : "Tắt"}
                  </span>

                  {item.locked ? (
                    <div className="inline-flex h-6 w-11 items-center rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/80 px-1 text-[var(--status-ok-text)]">
                      <Icon name="check" size="0.8rem" className="mx-auto" />
                    </div>
                  ) : (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={isGranted}
                      aria-label={`Bật tắt ${item.shortLabel}`}
                      onClick={() => handleToggle(item.purposeKey, item.locked)}
                      data-testid={`preview-toggle-${item.purposeKey}`}
                      className={[
                        "inline-flex h-6 w-11 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]",
                        isGranted
                          ? "border-[color:var(--brand-600)] bg-[var(--brand-600)]"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
                      ].join(" ")}
                    >
                      <span
                        aria-hidden="true"
                        className={[
                          "ml-0.5 h-5 w-5 rounded-full bg-[var(--text-primary)] transition-transform motion-reduce:transition-none shadow-sm",
                          isGranted ? "translate-x-5" : "translate-x-0",
                        ].join(" ")}
                      />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Consequence Analysis Card for the Selected Pillar */}
      <div className="relative z-10 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 sm:p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-2.5">
          <div className="flex items-center gap-2">
            <Icon name="clinical-notes" size="1.05rem" className="text-[var(--text-brand)]" />
            <h4 className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
              Phân tích tác động: {selectedPillar.title}
            </h4>
          </div>
          <Badge tone={isSelectedActive ? "ok" : "warn"}>
            {isSelectedActive ? "Trạng thái: Cho phép xử lý" : "Trạng thái: Đã thu hồi / Bị chặn"}
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {/* When Granted */}
          <div
            className={[
              "rounded-lg border p-3 space-y-1.5 transition-all",
              isSelectedActive
                ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]/30 text-[var(--text-primary)] font-medium"
                : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]/60 text-[var(--text-muted)]",
            ].join(" ")}
          >
            <div className="flex items-center gap-1.5 font-bold text-[var(--status-ok-text)]">
              <Icon name="check" size="0.9rem" />
              <span>Khi được đồng thuận (Active):</span>
            </div>
            <p className="leading-relaxed">{selectedPillar.consequenceWhenGranted}</p>
          </div>

          {/* When Revoked */}
          <div
            className={[
              "rounded-lg border p-3 space-y-1.5 transition-all",
              !isSelectedActive
                ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/30 text-[var(--text-primary)] font-medium"
                : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]/60 text-[var(--text-muted)]",
            ].join(" ")}
          >
            <div className="flex items-center gap-1.5 font-bold text-amber-500">
              <Icon name="warning" size="0.9rem" />
              <span>Khi thu hồi / Không đồng thuận (Revoked):</span>
            </div>
            <p className="leading-relaxed">{selectedPillar.consequenceWhenRevoked}</p>
          </div>
        </div>
      </div>

      {/* 4. Widget Footer & 1-Click Navigation to Account Ledger */}
      <div className="relative z-10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 text-xs">
        <div className="flex flex-wrap items-center gap-2 text-[var(--text-muted)] font-mono text-[11px]">
          <span>Mã băm kiểm toán:</span>
          <code className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-bold text-[var(--text-brand)]">
            {auditHash}
          </code>
          <span>· Phiên bản chính sách: {LEGAL_POLICY_VERSION}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Link
            href="/account/consent"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-4 py-2 text-xs font-bold text-[var(--text-on-brand)] shadow-sm transition hover:bg-[var(--brand-500)]"
          >
            <span>Mở Sổ cái đồng thuận cá nhân</span>
            <Icon name="arrow-right" size="0.9rem" />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default ConsentStatusPreviewWidget;
