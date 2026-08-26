"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/field";
import { isSocialModerationBlock, SocialCommunity } from "@/lib/social";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setError(null);
      setTitle("");
      setBody("");
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
    } catch (err) {
      if (isSocialModerationBlock(err)) {
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

        <div className="space-y-1">
          <Textarea
            label={copy("community.compose.bodyLabel")}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
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
          <p className="text-xs font-semibold text-[var(--status-danger-text)] rounded-lg bg-[var(--status-danger-bg)] p-3 border border-[color:var(--status-danger-border)]">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

export default ComposeModal;
