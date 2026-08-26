"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { getMyProfile, updateMyProfile, SocialProfile } from "@/lib/social";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface ProfileDrawerProps {
  open: boolean;
  onClose: () => void;
  onProfileUpdated?: (profile: SocialProfile) => void;
}

export function ProfileDrawer({
  open,
  onClose,
  onProfileUpdated,
}: ProfileDrawerProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState<SocialProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setError(null);
    setSuccess(false);
    setLoading(true);

    getMyProfile()
      .then((data) => {
        if (!active) return;
        setProfile(data);
        setDisplayName(data.display_name || "");
        setBio(data.bio || "");
      })
      .catch(() => {
        if (!active) return;
        setError(isEn ? "Failed to load profile." : "Không thể tải thông tin hồ sơ.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, isEn]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await updateMyProfile({
        display_name: displayName.trim(),
        bio: bio.trim(),
      });
      setProfile(updated);
      setSuccess(true);
      onProfileUpdated?.(updated);
      setTimeout(() => {
        onClose();
      }, 700);
    } catch {
      setError(
        isEn
          ? "Failed to update profile. Please try again."
          : "Không thể cập nhật hồ sơ. Vui lòng thử lại."
      );
    } finally {
      setSaving(false);
    }
  };

  const isClinician = profile?.role_badge === "clinician";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEn ? "My Community Profile" : "Hồ sơ Cộng đồng của tôi"}
      description={
        isEn
          ? "Manage your public handle, display name and community bio. Your private medical records remain completely isolated (Zero-PII)."
          : "Quản lý tên hiển thị và giới thiệu bản thân trong cộng đồng. Hồ sơ y tế cá nhân của bạn được cách ly an toàn (Zero-PII)."
      }
      size="md"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            {copy("community.compose.cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            disabled={saving || loading}
            loading={saving}
          >
            {isEn ? "Save Profile" : "Lưu hồ sơ"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {loading ? (
          <div className="py-8 text-center text-xs text-[var(--text-secondary)] space-y-2">
            <Icon
              name="progress"
              size="1.25rem"
              className="mx-auto text-[var(--text-brand)] animate-spin"
            />
            <p>{isEn ? "Loading profile..." : "Đang tải thông tin hồ sơ..."}</p>
          </div>
        ) : (
          <>
            {/* Header Avatar & Handle */}
            <div className="flex items-center gap-3.5 p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)]">
              <div className="w-12 h-12 rounded-full bg-[var(--brand-600)] text-[var(--button-primary-text)] font-bold text-base flex items-center justify-center shrink-0 shadow-xs">
                {(displayName || profile?.handle || "U").slice(0, 2).toUpperCase()}
              </div>
              <div className="space-y-1 flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-bold text-sm text-[var(--text-primary)] truncate">
                    @{profile?.handle || "user"}
                  </p>
                  {isClinician ? (
                    <Badge tone="brand" icon="check" className="text-[10px] py-0.5 font-bold">
                      {isEn ? "Verified Clinician" : "Bác sĩ / Chuyên gia"}
                    </Badge>
                  ) : (
                    <Badge tone="neutral" className="text-[10px] py-0.5">
                      {isEn ? "Community Member" : "Thành viên Cộng đồng"}
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  {isEn
                    ? "Zero-PII Isolation active. PHR data is never linked."
                    : "Đang kích hoạt cách ly Zero-PII. Không liên kết hồ sơ bệnh án."}
                </p>
              </div>
            </div>

            {/* Display Name Input */}
            <div className="space-y-1">
              <Field
                label={isEn ? "Display Name" : "Tên hiển thị"}
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={80}
                placeholder={isEn ? "Your public community name" : "Tên hiển thị của bạn trong cộng đồng"}
              />
              <div className="text-right text-[11px] text-[var(--text-muted)]">
                {displayName.length}/80
              </div>
            </div>

            {/* Bio Input */}
            <div className="space-y-1">
              <Textarea
                label={isEn ? "Community Bio" : "Giới thiệu ngắn"}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                maxLength={280}
                placeholder={
                  isEn
                    ? "Share your general interests, wellness goals, or background (do not share personal contact info or sensitive health IDs)."
                    : "Chia sẻ ngắn về mối quan tâm sức khỏe hoặc kinh nghiệm (không chia sẻ thông tin liên lạc hay dữ liệu định danh)."
                }
              />
              <div className="text-right text-[11px] text-[var(--text-muted)]">
                {bio.length}/280
              </div>
            </div>

            {/* Safety & Isolation Notice */}
            <div className="rounded-lg bg-[var(--surface-muted)]/60 p-3 text-xs text-[var(--text-secondary)] border border-[color:var(--shell-border)] flex items-start gap-2">
              <Icon name="check" size="1rem" className="text-[var(--text-brand)] shrink-0 mt-0.5" />
              <p className="text-[11px] leading-relaxed">
                {isEn
                  ? "Your community profile is strictly isolated from your electronic medical records, clinical notes, and private consultations."
                  : "Hồ sơ cộng đồng của bạn được cách ly hoàn toàn khỏi hồ sơ bệnh án điện tử, sổ tay lâm sàng và các cuộc tư vấn riêng tư."}
              </p>
            </div>

            {success ? (
              <p className="text-xs font-semibold text-[var(--status-ok-text)] rounded-lg bg-[var(--status-ok-bg)] p-2.5 border border-[color:var(--status-ok-border)] flex items-center gap-1.5">
                <Icon name="check" size="0.9rem" />
                <span>{isEn ? "Profile updated successfully!" : "Đã cập nhật hồ sơ thành công!"}</span>
              </p>
            ) : null}

            {error ? (
              <p className="text-xs font-semibold text-[var(--status-danger-text)] rounded-lg bg-[var(--status-danger-bg)] p-2.5 border border-[color:var(--status-danger-border)]">
                {error}
              </p>
            ) : null}
          </>
        )}
      </div>
    </Modal>
  );
}

export default ProfileDrawer;
