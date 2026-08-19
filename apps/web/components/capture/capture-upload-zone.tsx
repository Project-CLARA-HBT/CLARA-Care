"use client";

import {
  useCallback,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export interface CaptureUploadZoneProps {
  onFileSelect: (file: File) => void;
  onCancel?: () => void;
  uploadProgress?: number | null;
  isUploading?: boolean;
  isProcessing?: boolean;
  statusMessage?: string | null;
  acceptedMimeTypes?: string[];
  maxSizeMb?: number;
  captureMode?: "file" | "camera" | "all";
  disabled?: boolean;
  locale?: "vi" | "en";
  className?: string;
  children?: ReactNode;
}

const DEFAULT_ACCEPTED_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

const DEFAULT_MAX_SIZE_MB = 25;

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function CaptureUploadZone({
  onFileSelect,
  onCancel,
  uploadProgress = null,
  isUploading = false,
  isProcessing = false,
  statusMessage = null,
  acceptedMimeTypes = DEFAULT_ACCEPTED_MIME_TYPES,
  maxSizeMb = DEFAULT_MAX_SIZE_MB,
  captureMode = "all",
  disabled = false,
  locale = "vi",
  className = "",
  children,
}: CaptureUploadZoneProps) {
  const isEn = locale === "en";
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const maxSizeBytes = maxSizeMb * 1024 * 1024;

  const validateAndSelect = useCallback(
    (file: File) => {
      setValidationError(null);

      // Check file size
      if (file.size > maxSizeBytes) {
        const errorMsg = isEn
          ? `File size (${formatBytes(file.size)}) exceeds the maximum allowed limit of ${maxSizeMb}MB.`
          : `Kích thước tệp (${formatBytes(file.size)}) vượt quá dung lượng tối đa cho phép (${maxSizeMb}MB).`;
        setValidationError(errorMsg);
        return false;
      }

      // Check MIME type or extension
      const fileNameLower = file.name.toLowerCase();
      const isMimeMatch = acceptedMimeTypes.some((type) => {
        if (type.endsWith("/*")) {
          const prefix = type.replace("/*", "");
          return file.type.startsWith(prefix);
        }
        return file.type === type;
      });

      const isExtMatch =
        fileNameLower.endsWith(".jpg") ||
        fileNameLower.endsWith(".jpeg") ||
        fileNameLower.endsWith(".png") ||
        fileNameLower.endsWith(".webp") ||
        fileNameLower.endsWith(".heic") ||
        fileNameLower.endsWith(".pdf") ||
        fileNameLower.endsWith(".docx");

      if (file.type && !isMimeMatch && !isExtMatch) {
        const errorMsg = isEn
          ? "Unsupported file format. Please upload JPG, PNG, WEBP, PDF, or DOCX."
          : "Định dạng tệp không được hỗ trợ. Vui lòng tải lên ảnh JPG, PNG, WEBP, PDF hoặc DOCX.";
        setValidationError(errorMsg);
        return false;
      }

      onFileSelect(file);
      return true;
    },
    [acceptedMimeTypes, isEn, maxSizeBytes, maxSizeMb, onFileSelect],
  );

  const handleDragOver = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (disabled || isUploading || isProcessing) return;
      setIsDragOver(true);
    },
    [disabled, isProcessing, isUploading],
  );

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (disabled || isUploading || isProcessing) return;

      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        validateAndSelect(files[0]);
      }
    },
    [disabled, isProcessing, isUploading, validateAndSelect],
  );

  const handleInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        validateAndSelect(files[0]);
      }
      // Reset input value to allow selecting the same file again
      e.target.value = "";
    },
    [validateAndSelect],
  );

  const isBusy = isUploading || isProcessing;

  return (
    <div className={`capture-upload-zone space-y-3 ${className}`} data-testid="capture-upload-zone">
      {/* Hidden file pickers */}
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptedMimeTypes.join(",")}
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled || isBusy}
        aria-label={isEn ? "Select file" : "Chọn tệp"}
        data-testid="capture-file-input"
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleInputChange}
        className="hidden"
        disabled={disabled || isBusy}
        aria-label={isEn ? "Capture photo with camera" : "Chụp ảnh bằng camera"}
        data-testid="capture-camera-input"
      />

      {/* Main Drag-and-Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center rounded-[var(--radius-xl)] border-2 border-dashed p-6 sm:p-8 text-center transition-all duration-200 ${
          isDragOver
            ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] scale-[1.005]"
            : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border-strong)]"
        } ${isBusy ? "opacity-90 pointer-events-none" : ""}`}
        role="region"
        aria-label={isEn ? "Upload and drop area" : "Khu vực tải và kéo thả tệp"}
      >
        {isBusy ? (
          <div className="w-full max-w-sm space-y-4 py-3" data-testid="capture-busy-state">
            <div className="flex items-center justify-center gap-3">
              <Icon
                name="progress"
                size="1.75rem"
                className="animate-spin text-[var(--text-brand)]"
              />
              <span className="font-semibold text-[var(--text-primary)] text-sm sm:text-base">
                {statusMessage ??
                  (isUploading
                    ? isEn
                      ? "Uploading document..."
                      : "Đang tải lên tài liệu..."
                    : isEn
                    ? "Extracting health data..."
                    : "Đang trích xuất thông tin y tế...")}
              </span>
            </div>

            {/* Progress Bar */}
            {uploadProgress !== null ? (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-[var(--text-muted)] font-medium">
                  <span>{isEn ? "Progress" : "Tiến độ"}</span>
                  <span data-testid="upload-progress-value">{Math.round(uploadProgress)}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-muted)]">
                  <div
                    className="h-full bg-[var(--brand-600)] transition-all duration-200"
                    style={{ width: `${Math.min(100, Math.max(0, uploadProgress))}%` }}
                    role="progressbar"
                    aria-valuenow={Math.round(uploadProgress)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
              </div>
            ) : (
              <div className="h-1.5 w-full overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-muted)]">
                <div className="h-full w-1/3 animate-pulse bg-[var(--brand-600)] rounded-[var(--radius-pill)]" />
              </div>
            )}

            {/* Cancellation Button */}
            {onCancel ? (
              <div className="pt-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onCancel}
                  icon="close"
                  className="pointer-events-auto text-xs text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)]"
                  data-testid="capture-cancel-button"
                >
                  {isEn ? "Cancel upload" : "Hủy tải lên"}
                </Button>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="grid h-14 w-14 place-items-center rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-sm">
              <Icon
                name={captureMode === "camera" ? "camera" : "upload"}
                size="1.75rem"
              />
            </div>

            <div className="space-y-1">
              <p className="text-sm sm:text-base font-semibold text-[var(--text-primary)]">
                {isDragOver
                  ? isEn
                    ? "Drop file here to start capture"
                    : "Thả tệp vào đây để bắt đầu nhận diện"
                  : isEn
                  ? "Drag and drop your file here"
                  : "Kéo thả tài liệu y tế vào đây"}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? `Supported formats: Images (JPG, PNG), PDF, DOCX (Max ${maxSizeMb}MB)`
                  : `Hỗ trợ ảnh chụp (JPG, PNG), tài liệu PDF, DOCX (Tối đa ${maxSizeMb}MB)`}
              </p>
            </div>

            {/* Action Buttons */}
            <div className="mt-2 flex flex-wrap items-center justify-center gap-2.5">
              {captureMode !== "camera" ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled}
                  icon="upload"
                  data-testid="capture-browse-btn"
                >
                  {isEn ? "Choose file" : "Chọn tệp từ máy"}
                </Button>
              ) : null}

              {captureMode !== "file" ? (
                <Button
                  variant={captureMode === "camera" ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => cameraInputRef.current?.click()}
                  disabled={disabled}
                  icon="camera"
                  data-testid="capture-camera-btn"
                >
                  {isEn ? "Take photo" : "Chụp ảnh"}
                </Button>
              ) : null}
            </div>
          </div>
        )}

        {children}
      </div>

      {/* Validation Error Message */}
      {validationError ? (
        <div
          className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3 text-xs text-[var(--status-danger-text)] animate-fadeIn"
          role="alert"
          data-testid="capture-validation-error"
        >
          <Icon name="warning" size="1.1rem" className="shrink-0" />
          <span className="flex-1 font-medium">{validationError}</span>
          <button
            type="button"
            onClick={() => setValidationError(null)}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label={isEn ? "Dismiss error" : "Đóng thông báo"}
          >
            <Icon name="close" size="0.9rem" />
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default CaptureUploadZone;
