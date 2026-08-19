"use client";

import {
  useState,
  useRef,
  useEffect,
  type FormEvent,
  type KeyboardEvent,
  type ChangeEvent,
} from "react";
import { Icon } from "@/components/ui/icon";
import type { ConsumerAskAttachmentDto } from "@/lib/api/v2-client";

export interface AttachedFileItem {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  previewUrl?: string;
}

export interface AskComposerProps {
  onSend: (text: string, attachments?: AttachedFileItem[]) => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  onCancel?: () => void;
  initialText?: string;
  placeholder?: string;
  locale?: "vi" | "en";
  className?: string;
  autoFocus?: boolean;
}

export function AskComposer({
  onSend,
  isSubmitting = false,
  disabled = false,
  onCancel,
  initialText = "",
  placeholder,
  locale = "vi",
  className = "",
  autoFocus = false,
}: AskComposerProps) {
  const [text, setText] = useState(initialText);
  const [attachments, setAttachments] = useState<AttachedFileItem[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  const isEn = locale === "en";
  const defaultPlaceholder =
    placeholder ??
    (isEn
      ? "Ask CLARA about symptoms, medications, lab results..."
      : "Hỏi CLARA về triệu chứng, thuốc, kết quả xét nghiệm...");

  // Synchronize initialText if changed from outside (e.g. from suggestions or url)
  useEffect(() => {
    if (initialText) {
      setText((prev) => (prev ? prev : initialText));
    }
  }, [initialText]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const newHeight = Math.min(textarea.scrollHeight, 180);
    textarea.style.height = `${Math.max(newHeight, 44)}px`;
  }, [text]);

  // Clean up object URLs on unmount
  useEffect(() => {
    return () => {
      attachments.forEach((att) => {
        if (att.previewUrl) URL.revokeObjectURL(att.previewUrl);
      });
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
  }, [attachments]);

  const handleSend = (e?: FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = text.trim();
    if ((!trimmed && attachments.length === 0) || isSubmitting || disabled) {
      return;
    }

    onSend(trimmed, attachments);
    // Note: Do not clear text immediately until confirmed or let parent handle,
    // but in consumer chat we clear composer state on successful submit.
    // The draft is preserved if user cancels or error occurs because the active exchange preserves it.
    setText("");
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newItems: AttachedFileItem[] = Array.from(files).map((file) => {
      const isImg = file.type.startsWith("image/");
      return {
        id: `att_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        previewUrl: isImg ? URL.createObjectURL(file) : undefined,
      };
    });

    setAttachments((prev) => [...prev, ...newItems]);
    // Reset input value so same file can be selected again if needed
    e.target.value = "";
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => {
      const target = prev.find((a) => a.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((a) => a.id !== id);
    });
  };

  const toggleVoiceRecording = () => {
    if (disabled || isSubmitting) return;

    if (isRecording) {
      setIsRecording(false);
      setVoiceNotice(null);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      return;
    }

    // Try Web Speech API if supported
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.lang = isEn ? "en-US" : "vi-VN";
        recognition.interimResults = true;
        recognition.continuous = false;

        recognition.onstart = () => {
          setIsRecording(true);
          setVoiceNotice(isEn ? "Listening... Speak your question" : "Đang lắng nghe... Hãy nói câu hỏi của bạn");
        };

        recognition.onresult = (event: any) => {
          let transcript = "";
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            transcript += event.results[i][0].transcript;
          }
          if (transcript) {
            setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
          }
        };

        recognition.onerror = () => {
          setIsRecording(false);
          setVoiceNotice(isEn ? "Voice recognition ended" : "Đã dừng nhận diện giọng nói");
          setTimeout(() => setVoiceNotice(null), 3000);
        };

        recognition.onend = () => {
          setIsRecording(false);
          setVoiceNotice(null);
        };

        recognitionRef.current = recognition;
        recognition.start();
      } catch {
        setIsRecording(true);
        setVoiceNotice(isEn ? "Listening..." : "Đang lắng nghe...");
      }
    } else {
      // Affordance fallback state
      setIsRecording(true);
      setVoiceNotice(isEn ? "Recording voice input..." : "Đang ghi nhận giọng nói...");
      setTimeout(() => {
        setIsRecording(false);
        setVoiceNotice(null);
      }, 4000);
    }
  };

  const canSend = (text.trim().length > 0 || attachments.length > 0) && !disabled;

  return (
    <form
      onSubmit={handleSend}
      className={`relative flex flex-col rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm transition-all duration-150 focus-within:border-[color:var(--brand-500)] focus-within:shadow-[0_0_0_2px_rgba(164,201,255,0.2)] ${className}`}
      data-testid="ask-composer"
    >
      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.png,.jpg,.jpeg,.webp,.heic,.txt"
        onChange={handleFileChange}
        className="hidden"
        data-testid="ask-composer-file-input"
        aria-hidden="true"
      />

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileChange}
        className="hidden"
        data-testid="ask-composer-camera-input"
        aria-hidden="true"
      />

      {/* Voice recording alert banner if active */}
      {isRecording || voiceNotice ? (
        <div className="flex items-center justify-between gap-2 border-b border-[color:var(--brand-500)]/20 bg-[var(--surface-brand-soft)] px-4 py-2 text-xs font-medium text-[var(--text-brand)]">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
            </span>
            <span>{voiceNotice || (isEn ? "Recording voice..." : "Đang ghi âm...")}</span>
          </div>
          {isRecording ? (
            <button
              type="button"
              onClick={toggleVoiceRecording}
              className="font-semibold text-red-500 hover:underline"
            >
              {isEn ? "Stop" : "Dừng"}
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Attachment Previews */}
      {attachments.length > 0 ? (
        <div
          className="flex flex-wrap gap-2 border-b border-[color:var(--shell-border)]/60 p-3"
          data-testid="ask-composer-attachments"
        >
          {attachments.map((att) => (
            <div
              key={att.id}
              className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs text-[var(--text-primary)]"
              data-testid={`attachment-chip-${att.id}`}
            >
              {att.previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={att.previewUrl}
                  alt={att.name}
                  className="h-5 w-5 rounded object-cover"
                />
              ) : (
                <Icon name="folder" size={14} className="text-[var(--text-muted)]" />
              )}
              <span className="max-w-[150px] truncate font-medium">{att.name}</span>
              <button
                type="button"
                onClick={() => handleRemoveAttachment(att.id)}
                disabled={isSubmitting}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] focus-ring rounded"
                aria-label={`Xóa đính kèm ${att.name}`}
              >
                <Icon name="close" size={13} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {/* Textarea Input */}
      <div className="px-4 pt-3 pb-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={defaultPlaceholder}
          disabled={disabled || isSubmitting}
          autoFocus={autoFocus}
          rows={1}
          className="clara-scrollbar w-full resize-none border-0 bg-transparent p-0 text-sm leading-relaxed text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-0 sm:text-base"
          aria-label={defaultPlaceholder}
          data-testid="ask-composer-textarea"
        />
      </div>

      {/* Bottom Bar: Action Affordances + Send / Stop Button */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-t border-[color:var(--shell-border)]/40 bg-[var(--surface-panel)] rounded-b-[var(--radius-2xl)]">
        {/* Left Side: Camera, File, Voice affordances */}
        <div className="flex items-center gap-1">
          {/* Camera Button */}
          <button
            type="button"
            onClick={() => cameraInputRef.current?.click()}
            disabled={disabled || isSubmitting}
            title={isEn ? "Take photo or scan" : "Chụp ảnh nhãn thuốc / kết quả"}
            aria-label={isEn ? "Take photo or scan" : "Chụp ảnh nhãn thuốc hoặc kết quả"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] disabled:opacity-40 focus-ring"
            data-testid="ask-composer-camera-button"
          >
            <Icon name="scan" size={19} aria-hidden="true" />
          </button>

          {/* File Attachment Button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isSubmitting}
            title={isEn ? "Attach health document" : "Đính kèm tệp hồ sơ"}
            aria-label={isEn ? "Attach health document" : "Đính kèm tệp hồ sơ"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] disabled:opacity-40 focus-ring"
            data-testid="ask-composer-file-button"
          >
            <Icon name="folder" size={19} aria-hidden="true" />
          </button>

          {/* Voice Input Button */}
          <button
            type="button"
            onClick={toggleVoiceRecording}
            disabled={disabled || isSubmitting}
            title={isEn ? "Voice question" : "Hỏi bằng giọng nói"}
            aria-label={isEn ? "Voice question" : "Hỏi bằng giọng nói"}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] transition-colors disabled:opacity-40 focus-ring ${
              isRecording
                ? "bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            }`}
            data-testid="ask-composer-voice-button"
          >
            <Icon name="notifications" size={19} aria-hidden="true" />
          </button>
        </div>

        {/* Right Side: Send button or Stop button when isSubmitting */}
        <div className="flex items-center gap-2">
          {isSubmitting ? (
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3.5 text-xs font-semibold text-[var(--status-danger-text)] transition-colors hover:brightness-95 focus-ring"
              data-testid="ask-composer-stop-button"
              aria-label="Dừng câu trả lời"
            >
              <Icon name="stop" size={14} aria-hidden="true" />
              <span>Dừng</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-[var(--radius-lg)] bg-[var(--brand-600)] px-4 text-xs font-semibold text-[var(--button-primary-text)] shadow-xs transition-colors hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-45 focus-ring"
              data-testid="ask-composer-send-button"
              aria-label="Gửi câu hỏi"
            >
              <span>{isEn ? "Ask" : "Gửi"}</span>
              <Icon name="send" size={14} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}

export default AskComposer;
