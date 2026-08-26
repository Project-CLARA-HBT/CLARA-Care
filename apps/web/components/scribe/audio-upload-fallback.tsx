"use client";

import React, { useRef, useState } from "react";
import { SurfaceCard } from "@/components/ui/surface";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";

export interface AudioUploadFallbackProps {
  isVi?: boolean;
  onUploadFile: (file: File) => void | Promise<void>;
  disabled?: boolean;
  isTranscribing?: boolean;
  className?: string;
}

export function AudioUploadFallback({
  isVi = true,
  onUploadFile,
  disabled = false,
  isTranscribing = false,
  className = "",
}: AudioUploadFallbackProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = (file: File | null | undefined) => {
    if (!file) return;
    if (disabled || isTranscribing) return;
    void onUploadFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled || isTranscribing) return;
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  return (
    <SurfaceCard
      className={`p-6 border-dashed border-2 transition-colors ${
        isDragOver
          ? "border-[var(--brand-500)] bg-[var(--surface-brand-soft)]"
          : "border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
      } ${className}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
    >
      <div className="text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] flex items-center justify-center mx-auto border border-[color:var(--shell-border)]">
          <Icon name="upload" size="1.5rem" />
        </div>

        <div className="space-y-1">
          <h4 className="font-bold text-sm text-[var(--text-primary)]">
            {isVi ? "Tải lên tệp ghi âm sẵn có" : "Upload Pre-recorded Audio"}
          </h4>
          <p className="text-xs text-[var(--text-secondary)] max-w-sm mx-auto">
            {isVi
              ? "Kéo thả hoặc chọn tệp âm thanh (.webm, .wav, .mp3, .m4a, .ogg) dung lượng tối đa 50MB."
              : "Drag & drop or select audio file (.webm, .wav, .mp3, .m4a, .ogg) up to 50MB."}
          </p>
        </div>

        <div className="flex items-center justify-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,.webm,.mp3,.wav,.m4a,.ogg"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              handleFile(f);
            }}
            disabled={disabled || isTranscribing}
            data-testid="scribe-audio-upload"
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isTranscribing}
          >
            <Icon name="folder" size="1rem" />
            <span>{isTranscribing ? (isVi ? "Đang xử lý..." : "Processing...") : (isVi ? "Chọn tệp âm thanh" : "Select Audio File")}</span>
          </Button>
        </div>
      </div>
    </SurfaceCard>
  );
}

export default AudioUploadFallback;
