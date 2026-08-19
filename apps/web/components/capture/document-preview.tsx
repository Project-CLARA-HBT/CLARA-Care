"use client";

import { useEffect, useMemo, useState } from "react";
import type { CaptureCandidateV2 } from "@/lib/api/v2-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatCandidateFieldName, getCategoryMeta } from "./types";

export interface DocumentPreviewProps {
  file?: File | null;
  fileUrl?: string | null;
  fileName?: string | null;
  mediaType?: string | null;
  candidates?: CaptureCandidateV2[];
  selectedCandidateId?: string | null;
  onSelectCandidate?: (candidateId: string) => void;
  locale?: "vi" | "en";
  className?: string;
}

export function DocumentPreview({
  file,
  fileUrl,
  fileName,
  mediaType,
  candidates = [],
  selectedCandidateId = null,
  onSelectCandidate,
  locale = "vi",
  className = "",
}: DocumentPreviewProps) {
  const isEn = locale === "en";

  const [previewUrl, setPreviewUrl] = useState<string | null>(fileUrl ?? null);
  const [zoom, setZoom] = useState<number>(100);
  const [rotation, setRotation] = useState<number>(0);
  const [hoveredCandidateId, setHoveredCandidateId] = useState<string | null>(null);

  // Generate object URL for preview if File is passed
  useEffect(() => {
    if (fileUrl) {
      setPreviewUrl(fileUrl);
      return;
    }
    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => {
        URL.revokeObjectURL(url);
      };
    }
    setPreviewUrl(null);
  }, [file, fileUrl]);

  const resolvedName = fileName ?? file?.name ?? (isEn ? "Document" : "Tài liệu");
  const resolvedMediaType = mediaType ?? file?.type ?? "";
  const isPdf =
    resolvedMediaType.includes("pdf") ||
    resolvedName.toLowerCase().endsWith(".pdf");
  const isImage =
    resolvedMediaType.startsWith("image/") ||
    /\.(jpg|jpeg|png|webp|heic|heif)$/i.test(resolvedName);

  const handleZoomIn = () => setZoom((z) => Math.min(250, z + 25));
  const handleZoomOut = () => setZoom((z) => Math.max(50, z - 25));
  const handleRotate = () => setRotation((r) => (r + 90) % 360);
  const handleReset = () => {
    setZoom(100);
    setRotation(0);
  };

  // Extract candidate highlights that have bounding boxes
  const highlights = useMemo(() => {
    return candidates
      .filter((c) => c.bounding_box && typeof c.bounding_box === "object")
      .map((c) => ({
        candidateId: c.id,
        category: c.category,
        fieldName: c.field_name,
        box: c.bounding_box!,
        isSelected: c.id === selectedCandidateId,
        isHovered: c.id === hoveredCandidateId,
      }));
  }, [candidates, selectedCandidateId, hoveredCandidateId]);

  return (
    <div
      className={`document-preview flex flex-col rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden shadow-sm ${className}`}
      data-testid="document-preview"
    >
      {/* Header bar with controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 px-4 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <Icon
            name={isPdf ? "clinical-notes" : "scan"}
            size="1.1rem"
            className="text-[var(--text-brand)] shrink-0"
          />
          <span
            className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] truncate max-w-[200px] sm:max-w-xs"
            title={resolvedName}
          >
            {resolvedName}
          </span>
          {highlights.length > 0 ? (
            <Badge tone="brand" className="text-[10px] py-0.5 px-2">
              {highlights.length} {isEn ? "regions" : "vùng khớp"}
            </Badge>
          ) : null}
        </div>

        {/* Zoom & View Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={zoom <= 50}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] disabled:opacity-40 transition-colors"
            title={isEn ? "Zoom out" : "Thu nhỏ"}
            aria-label={isEn ? "Zoom out" : "Thu nhỏ"}
            data-testid="doc-zoom-out"
          >
            <Icon name="zoom-out" size="0.95rem" />
          </button>
          <span className="min-w-[40px] text-center text-xs font-mono text-[var(--text-muted)]">
            {zoom}%
          </span>
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={zoom >= 250}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] disabled:opacity-40 transition-colors"
            title={isEn ? "Zoom in" : "Phóng to"}
            aria-label={isEn ? "Zoom in" : "Phóng to"}
            data-testid="doc-zoom-in"
          >
            <Icon name="zoom-in" size="0.95rem" />
          </button>

          <div className="h-4 w-px bg-[var(--shell-border)] mx-1" />

          <button
            type="button"
            onClick={handleRotate}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] transition-colors"
            title={isEn ? "Rotate 90 degrees" : "Xoay 90 độ"}
            aria-label={isEn ? "Rotate 90 degrees" : "Xoay 90 độ"}
            data-testid="doc-rotate"
          >
            <Icon name="refresh" size="0.95rem" />
          </button>

          <button
            type="button"
            onClick={handleReset}
            className="inline-flex h-7 px-2 items-center justify-center rounded-[var(--radius-md)] text-[11px] text-[var(--text-secondary)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)] transition-colors"
            title={isEn ? "Reset view" : "Đặt lại"}
            data-testid="doc-reset"
          >
            {isEn ? "Reset" : "Đặt lại"}
          </button>
        </div>
      </div>

      {/* Main Preview Canvas Area */}
      <div
        className="relative flex-1 min-h-[300px] max-h-[500px] sm:max-h-[600px] overflow-auto bg-[var(--surface-muted)]/40 p-4 flex items-center justify-center"
        tabIndex={0}
        role="region"
        aria-label={isEn ? "Document preview container" : "Khung xem trước tài liệu"}
      >
        {previewUrl && isImage ? (
          <div
            className="relative transition-transform duration-150 inline-block shadow-md rounded-[var(--radius-md)] bg-white overflow-hidden"
            style={{
              transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
              transformOrigin: "center center",
            }}
            data-testid="document-image-container"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt={resolvedName}
              className="max-w-full h-auto object-contain block select-none pointer-events-none"
              data-testid="document-image-preview"
            />

            {/* Bounding Box Highlights Overlay */}
            {highlights.map((hl) => {
              const { box, isSelected, isHovered, candidateId, fieldName } = hl;
              return (
                <div
                  key={candidateId}
                  onClick={() => onSelectCandidate?.(candidateId)}
                  onMouseEnter={() => setHoveredCandidateId(candidateId)}
                  onMouseLeave={() => setHoveredCandidateId(null)}
                  style={{
                    left: `${box.x}%`,
                    top: `${box.y}%`,
                    width: `${box.width}%`,
                    height: `${box.height}%`,
                  }}
                  className={`absolute cursor-pointer transition-all duration-150 border-2 rounded-sm ${
                    isSelected
                      ? "border-[color:var(--brand-600)] bg-[var(--brand-500)]/25 ring-2 ring-[color:var(--brand-500)]/50 z-20"
                      : isHovered
                      ? "border-[color:var(--brand-400)] bg-[var(--brand-500)]/15 z-10"
                      : "border-[color:var(--brand-500)]/60 bg-[var(--brand-500)]/5 z-0 hover:bg-[var(--brand-500)]/15"
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${formatCandidateFieldName(fieldName, locale)} - ${
                    isSelected ? (isEn ? "Selected" : "Đang chọn") : ""
                  }`}
                  data-testid={`bounding-box-${candidateId}`}
                >
                  {(isSelected || isHovered) && (
                    <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-[var(--brand-600)] px-1.5 py-0.5 text-[10px] font-bold text-white shadow-sm pointer-events-none z-30">
                      {formatCandidateFieldName(fieldName, locale)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ) : previewUrl && isPdf ? (
          <div
            className="flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-[var(--surface-panel)] rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] shadow-sm max-w-md w-full"
            data-testid="document-pdf-preview"
          >
            <div className="grid h-16 w-16 place-items-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)] mb-3">
              <Icon name="clinical-notes" size="2rem" />
            </div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] break-all mb-1">
              {resolvedName}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mb-4">
              {isEn
                ? "PDF Document loaded and OCR processed"
                : "Tài liệu PDF đã được tải và xử lý nhận diện dữ liệu"}
            </p>
            <div className="flex items-center gap-2">
              <Badge tone="ok" icon="check">
                {isEn ? "OCR Extracted" : "Đã trích xuất"}
              </Badge>
              <Badge tone="neutral">
                {candidates.length} {isEn ? "items found" : "mục tìm thấy"}
              </Badge>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-6 text-center text-[var(--text-muted)]">
            <Icon name="scan" size="2rem" className="mb-2 opacity-50" />
            <p className="text-xs">
              {isEn ? "No document preview available" : "Chưa có tài liệu xem trước"}
            </p>
          </div>
        )}
      </div>

      {/* Selected candidate banner if active */}
      {selectedCandidateId ? (
        <div className="border-t border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-4 py-2 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--text-brand)]" />
            <span className="text-[var(--text-primary)] font-medium">
              {isEn ? "Selected extracted field highlighted in document" : "Vùng trích xuất đang chọn được làm nổi bật"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => onSelectCandidate?.("")}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-[11px] underline"
          >
            {isEn ? "Clear highlight" : "Bỏ chọn"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default DocumentPreview;
