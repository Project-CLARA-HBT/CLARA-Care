"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { isSocialModerationBlock, SocialCommunity } from "@/lib/social";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

const EMERGENCY_PATTERNS = [
  "115",
  "đột quỵ",
  "nhồi máu",
  "khó thở",
  "đau ngực",
  "ngất",
  "hôn mê",
  "cấp cứu",
  "co giật",
  "stroke",
  "chest pain",
  "infarction",
  "emergency",
  "dyspnea",
];

function containsEmergencyTerms(text: string): boolean {
  if (!text) return false;
  const lower = text.toLowerCase();
  return EMERGENCY_PATTERNS.some((pattern) => lower.includes(pattern));
}

export interface ComposeModalProps {
  open: boolean;
  onClose: () => void;
  communities: SocialCommunity[];
  initialCommunityId?: number | null;
  onPostCreated: () => Promise<void> | void;
  createPostFn: (data: {
    communityId: number;
    title: string;
    body: string;
  }) => Promise<unknown>;
}

export function ComposeModal({
  open,
  onClose,
  communities,
  initialCommunityId,
  onPostCreated,
  createPostFn,
}: ComposeModalProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language]
  );

  const [communityId, setCommunityId] = useState<number | null>(
    initialCommunityId ?? communities[0]?.id ?? null
  );
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [activeTab, setActiveTab] = useState<"write" | "preview">("write");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setError(null);
      setTitle("");
      setBody("");
      setActiveTab("write");
      setCommunityId(initialCommunityId ?? communities[0]?.id ?? null);
    }
  }, [open, initialCommunityId, communities]);

  const handleSubmit = async () => {
    if (communityId == null) {
      setError(copy("community.compose.chooseCommunity"));
      return;
    }
    if (!title.trim() || !body.trim()) {
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await createPostFn({
        communityId,
        title: title.trim(),
        body: body.trim(),
      });
      await onPostCreated();
      onClose();
    } catch (err: unknown) {
      const serverDetail = (err as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      if (typeof serverDetail === "string" && serverDetail.trim()) {
        setError(serverDetail);
      } else if (isSocialModerationBlock(err)) {
        setError(copy("community.compose.moderationBlocked"));
      } else {
        setError(copy("community.compose.createError"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={copy("community.compose.title")}
      description={
        isEn
          ? "Your post will be screened by AI to ensure patient safety and no illegal prescribing."
          : "Bài viết sẽ được AI rà soát tự động để đảm bảo an toàn y tế và không chứa đơn thuốc chỉ định."
      }
      size="md"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitting}>
            {copy("community.compose.cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={submitting || !title.trim() || !body.trim()}
            loading={submitting}
            loadingLabel={copy("community.compose.submitting")}
          >
            {copy("community.compose.action")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label={copy("community.compose.communityLabel")}
          value={communityId ?? ""}
          onChange={(e) => setCommunityId(Number(e.target.value))}
        >
          {communities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>

        <div className="space-y-1">
          <Field
            label={copy("community.compose.titleLabel")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder={
              isEn
                ? "Enter a clear title for your experience or inquiry"
                : "Nhập tiêu đề rõ ràng cho chia sẻ hoặc câu hỏi của bạn"
            }
          />
          <div className="text-right text-[11px] text-[var(--text-muted)]">
            {title.length}/200
          </div>
        </div>

        {/* Write / Preview Tab switcher */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-[var(--text-primary)]">
              {copy("community.compose.bodyLabel")}
            </label>
            <div className="inline-flex rounded-lg bg-[var(--surface-muted)] p-0.5 border border-[color:var(--shell-border)] text-xs">
              <button
                type="button"
                onClick={() => setActiveTab("write")}
                className={`px-2.5 py-0.5 rounded font-medium transition ${
                  activeTab === "write"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-xs"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? "Write" : "Soạn thảo"}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("preview")}
                className={`px-2.5 py-0.5 rounded font-medium transition ${
                  activeTab === "preview"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-xs"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? "Preview" : "Xem trước"}
              </button>
            </div>
          </div>

          {activeTab === "write" ? (
            <div className="space-y-1">
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={6}
                maxLength={5000}
                placeholder={
                  isEn
                    ? "Describe your context, questions or insights. Please do not provide medical prescriptions or disclose personal identification details."
                    : "Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm của bạn. Vui lòng không tự ý kê đơn thuốc hoặc tiết lộ thông tin định danh cá nhân."
                }
              />
              <div className="text-right text-[11px] text-[var(--text-muted)]">
                {body.length}/5000
              </div>
            </div>
          ) : (
            <div className="min-h-[140px] rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 text-xs text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
              {body.trim() ? (
                body
              ) : (
                <span className="text-[var(--text-muted)] italic">
                  {isEn ? "Nothing to preview yet." : "Chưa có nội dung để xem trước."}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Safety Guidelines helper */}
        <div className="rounded-xl bg-[var(--surface-muted)] p-3.5 text-xs text-[var(--text-secondary)] space-y-1.5 border border-[color:var(--shell-border)]">
          <p className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
            <span>{isEn ? "Safety & Privacy Guidelines:" : "Quy tắc an toàn & Riêng tư:"}</span>
          </p>
          <ul className="list-disc pl-4 space-y-1 text-[11px]">
            <li>
              {isEn
                ? "Do not post personal identification details (phone, email, full names)."
                : "Không đăng tải thông tin định danh cá nhân (số điện thoại, email, họ tên đầy đủ)."}
            </li>
            <li>
              {isEn
                ? "Do not offer clinical diagnosis or instruct others on medication dosages."
                : "Không chẩn đoán thay bác sĩ hoặc hướng dẫn liều dùng thuốc cho người khác."}
            </li>
            <li>
              {isEn
                ? "All submissions are screened by ML safety guardrails before publication."
                : "Toàn bộ bài viết được rà soát an toàn bằng ML trước khi xuất bản."}
            </li>
          </ul>
        </div>

        {error ? (
          <div className="space-y-2 rounded-lg bg-[var(--status-danger-bg)] p-3 border border-[color:var(--status-danger-border)]">
            <p className="text-xs font-semibold text-[var(--status-danger-text)]">
              {error}
            </p>
            {containsEmergencyTerms(error) ||
            containsEmergencyTerms(title) ||
            containsEmergencyTerms(body) ? (
              <div className="rounded-md bg-white/70 dark:bg-black/30 p-2.5 text-xs text-[var(--status-danger-text)] flex items-center justify-between gap-2 border border-[color:var(--status-danger-border)]">
                <span className="font-bold flex items-center gap-1.5 text-[11px]">
                  <Icon name="emergency" size="0.95rem" />
                  <span>
                    {isEn
                      ? "Emergency detected: Please call 115 immediately."
                      : "Dấu hiệu cấp cứu khẩn cấp: Vui lòng gọi 115 ngay lập tức."}
                  </span>
                </span>
                <a
                  href="tel:115"
                  className="px-2 py-0.5 rounded bg-[var(--status-danger-text)] text-white text-[11px] font-bold hover:opacity-90 transition shrink-0"
                >
                  {isEn ? "Call 115" : "Gọi 115"}
                </a>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

export default ComposeModal;
