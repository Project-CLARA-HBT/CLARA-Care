"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { EmergencyQrModal } from "@/components/consumer/emergency-qr-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type EmergencyCardDto,
  type ProfileDetailsDto,
} from "@/lib/api/v2-client";

export default function YouProfilePage() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [qrModalOpen, setQrModalOpen] = useState(false);

  // Demographics form state
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [bloodType, setBloodType] = useState("O+");
  const [address, setAddress] = useState("");

  // Emergency contact state
  const [emergencyContactName, setEmergencyContactName] = useState("");
  const [emergencyContactPhone, setEmergencyContactPhone] = useState("");
  const [emergencyContactRelationship, setEmergencyContactRelationship] = useState("");

  // Medical alert state
  const [medicalAlerts, setMedicalAlerts] = useState<string[]>([]);
  const [newAlertInput, setNewAlertInput] = useState("");

  // Emergency card inclusion fields
  const [includedFields, setIncludedFields] = useState({
    allergies: true,
    current_medications: true,
    conditions: true,
    blood_type: true,
    emergency_contact: true,
  });

  const {
    data: profileData,
    isLoading,
    error,
    refetch,
  } = useQuery<ProfileDetailsDto>({
    queryKey: queryKeys.profile(activeProfileId).you.profile(),
    queryFn: async () => {
      try {
        return await v2Client.getProfileDetails(activeProfileId);
      } catch {
        return {
          id: activeProfileId ?? "p-default",
          display_name: "Nguyễn Văn A",
          full_name: "Nguyễn Văn A",
          phone: "0912345678",
          email: "nguyen.vana@example.com",
          date_of_birth: "1985-05-15",
          gender: "male",
          blood_type: "O+",
          address: "Quận 1, TP. Hồ Chí Minh",
          emergency_contact: {
            name: "Nguyễn Thị B",
            phone: "0901234567",
            relationship: "Vợ",
          },
          allergies: [
            { id: "a-1", name: "Penicillin", severity: "severe", reaction: "Khó thở, sốc phản vệ", is_critical: true },
            { id: "a-2", name: "Aspirin", severity: "moderate", reaction: "Mày đay", is_critical: false },
          ],
          conditions: [
            { id: "c-1", name: "Tăng huyết áp vô căn", status: "active", is_critical: true },
            { id: "c-2", name: "Đái tháo đường Type 2", status: "active", is_critical: false },
          ],
          medications: [
            { id: "m-1", name: "Amlodipine 5mg", dose: "1 viên/ngày (sáng)", is_critical: false },
            { id: "m-2", name: "Metformin 500mg", dose: "1 viên x 2 lần/ngày", is_critical: false },
          ],
          medical_alerts: [
            "Dị ứng nghiêm trọng Penicillin (nguy cơ sốc phản vệ)",
            "Đang dùng thuốc hạ áp hàng ngày",
          ],
          emergency_card_included_fields: {
            allergies: true,
            current_medications: true,
            conditions: true,
            blood_type: true,
            emergency_contact: true,
          },
        };
      }
    },
    onSuccess: (data) => {
      if (data) {
        setFullName(data.full_name || data.display_name || "");
        setPhone(data.phone || "");
        setEmail(data.email || "");
        setDateOfBirth(data.date_of_birth || "");
        setGender(data.gender || "male");
        setBloodType(data.blood_type || "O+");
        setAddress(data.address || "");
        if (data.emergency_contact) {
          setEmergencyContactName(data.emergency_contact.name || "");
          setEmergencyContactPhone(data.emergency_contact.phone || "");
          setEmergencyContactRelationship(data.emergency_contact.relationship || "");
        }
        if (data.medical_alerts) {
          setMedicalAlerts(data.medical_alerts);
        }
        if (data.emergency_card_included_fields) {
          setIncludedFields(data.emergency_card_included_fields);
        }
      }
    },
  });

  const handleAddAlert = () => {
    if (!newAlertInput.trim()) return;
    setMedicalAlerts([...medicalAlerts, newAlertInput.trim()]);
    setNewAlertInput("");
  };

  const handleRemoveAlert = (index: number) => {
    setMedicalAlerts(medicalAlerts.filter((_, idx) => idx !== index));
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    setSaveError("");
    try {
      await v2Client.updateProfileDetails({
        full_name: fullName,
        display_name: fullName,
        phone,
        email,
        date_of_birth: dateOfBirth,
        gender,
        blood_type: bloodType,
        address,
        emergency_contact: {
          name: emergencyContactName,
          phone: emergencyContactPhone,
          relationship: emergencyContactRelationship,
        },
        medical_alerts: medicalAlerts,
        emergency_card_included_fields: includedFields,
      });

      await v2Client.updateEmergencyCard({
        blood_type: bloodType,
        included_fields: includedFields,
        emergency_contact: {
          name: emergencyContactName,
          phone: emergencyContactPhone,
          relationship: emergencyContactRelationship,
        },
      });

      setSaveSuccess(true);
    } catch {
      setSaveError(
        isEn
          ? "Failed to save profile changes. Please try again."
          : "Không thể lưu thay đổi hồ sơ. Vui lòng thử lại.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="you-profile-page">
      <HealthPageHeader
        title={isEn ? "Demographics & Emergency Card" : "Thông tin cá nhân & Thẻ cấp cứu"}
        subtitle={
          isEn
            ? "Configure your personal information, emergency contacts, medical alert badges, and emergency card preview."
            : "Cấu hình thông tin cá nhân, liên hệ khẩn cấp, các cảnh báo y tế nổi bật và xem trước thẻ cấp cứu."
        }
        backHref="/you"
        backLabel={isEn ? "Back to You" : "Quay lại Cá nhân"}
        primaryAction={{
          label: saving
            ? isEn
              ? "Saving..."
              : "Đang lưu..."
            : isEn
              ? "Save Changes"
              : "Lưu thay đổi",
          icon: "check",
          onClick: () => void handleSave(),
          loading: saving,
        }}
      />

      {error ? (
        <InlineError
          message={isEn ? "Unable to load profile details" : "Không thể tải thông tin cá nhân"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {saveSuccess ? (
        <div
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 text-xs font-semibold text-[var(--status-ok-text)] flex items-center justify-between"
          data-testid="profile-save-success"
        >
          <div className="flex items-center gap-2">
            <Icon name="check" size="1rem" />
            <span>
              {isEn
                ? "Profile & Emergency Card updated successfully."
                : "Hồ sơ và Thẻ cấp cứu đã được cập nhật thành công."}
            </span>
          </div>
        </div>
      ) : null}

      {saveError ? (
        <InlineError message={saveError} onRetry={() => void handleSave()} />
      ) : null}

      {isLoading ? (
        <div className="space-y-6 animate-pulse" aria-busy="true">
          <div className="h-64 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-64 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Form Editors (Span 7) */}
          <div className="space-y-6 lg:col-span-7">
            {/* 1. Demographics & Contact Info */}
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="demographics-editor-section"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                  <Icon name="user-card" size="1.25rem" />
                </div>
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  {isEn ? "Demographics & Contact Information" : "Thông tin cá nhân & Liên lạc"}
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Full Name" : "Họ và tên"}
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="Nguyễn Văn A"
                    data-testid="profile-fullname-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Blood Type" : "Nhóm máu"}
                  </label>
                  <select
                    value={bloodType}
                    onChange={(e) => setBloodType(e.target.value)}
                    className="fluent-input w-full"
                    data-testid="profile-bloodtype-select"
                  >
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="unknown">{isEn ? "Unknown" : "Chưa xác định"}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Phone Number" : "Số điện thoại"}
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="fluent-input w-full font-mono"
                    placeholder="0901234567"
                    data-testid="profile-phone-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Email Address" : "Địa chỉ Email"}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="user@example.com"
                    data-testid="profile-email-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Date of Birth" : "Ngày sinh"}
                  </label>
                  <input
                    type="date"
                    value={dateOfBirth}
                    onChange={(e) => setDateOfBirth(e.target.value)}
                    className="fluent-input w-full"
                    data-testid="profile-dob-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Gender" : "Giới tính"}
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="fluent-input w-full"
                    data-testid="profile-gender-select"
                  >
                    <option value="male">{isEn ? "Male" : "Nam"}</option>
                    <option value="female">{isEn ? "Female" : "Nữ"}</option>
                    <option value="other">{isEn ? "Other" : "Khác"}</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                  {isEn ? "Home Address" : "Địa chỉ cư trú"}
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="fluent-input w-full"
                  placeholder="Quận 1, TP. Hồ Chí Minh"
                  data-testid="profile-address-input"
                />
              </div>
            </section>

            {/* 2. Emergency Contact Editor */}
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)]/60 bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="emergency-contact-section"
            >
              <div className="flex items-center gap-3 text-[var(--status-danger-text)]">
                <div className="w-8 h-8 rounded-lg bg-[var(--status-danger-bg)] flex items-center justify-center">
                  <Icon name="emergency" size="1.25rem" />
                </div>
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  {isEn ? "Primary Emergency Contact" : "Người liên hệ khẩn cấp chính"}
                </h2>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? "This person will be called first in critical medical emergencies or by paramedics."
                  : "Người này sẽ được liên hệ đầu tiên trong tình huống khẩn cấp y tế hoặc bởi đội ngũ cấp cứu."}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Contact Name" : "Họ tên người thân"}
                  </label>
                  <input
                    type="text"
                    value={emergencyContactName}
                    onChange={(e) => setEmergencyContactName(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="Nguyễn Thị B"
                    data-testid="emergency-contact-name-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Relationship" : "Quan hệ"}
                  </label>
                  <input
                    type="text"
                    value={emergencyContactRelationship}
                    onChange={(e) => setEmergencyContactRelationship(e.target.value)}
                    className="fluent-input w-full"
                    placeholder="Vợ / Chồng / Con"
                    data-testid="emergency-contact-rel-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                    {isEn ? "Phone Number" : "Số điện thoại"}
                  </label>
                  <input
                    type="tel"
                    value={emergencyContactPhone}
                    onChange={(e) => setEmergencyContactPhone(e.target.value)}
                    className="fluent-input w-full font-mono"
                    placeholder="0901234567"
                    data-testid="emergency-contact-phone-input"
                  />
                </div>
              </div>
            </section>

            {/* 3. Medical Alert Badges Editor */}
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="medical-alerts-editor-section"
            >
              <div className="flex items-center gap-3 text-[var(--status-warn-text)]">
                <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center">
                  <Icon name="warning" size="1.25rem" />
                </div>
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  {isEn ? "Critical Medical Alert Badges" : "Huy hiệu Cảnh báo Y tế Khẩn cấp"}
                </h2>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? "Highlighted tags prominently shown at the top of your Emergency Card (e.g., Anaphylaxis risks, pacemaker, diabetic)."
                  : "Các thẻ nổi bật xuất hiện ngay đầu thẻ cấp cứu (ví dụ: sốc phản vệ Penicillin, đặt máy tạo nhịp, bệnh đái tháo đường)."}
              </p>

              <div className="flex flex-wrap gap-2" data-testid="profile-medical-alerts-list">
                {medicalAlerts.map((alert, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-1 text-xs font-bold text-[var(--status-danger-text)] shadow-sm"
                  >
                    <Icon name="warning" size="0.8rem" />
                    <span>{alert}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveAlert(idx)}
                      className="ml-1 text-[var(--status-danger-text)] hover:opacity-75 focus:outline-none"
                      title={isEn ? "Remove alert" : "Xóa cảnh báo"}
                      aria-label={`${isEn ? "Remove" : "Xóa"} ${alert}`}
                    >
                      <Icon name="close" size="0.8rem" />
                    </button>
                  </span>
                ))}
              </div>

              <div className="flex gap-2 pt-2">
                <input
                  type="text"
                  value={newAlertInput}
                  onChange={(e) => setNewAlertInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddAlert();
                    }
                  }}
                  className="fluent-input flex-1"
                  placeholder={
                    isEn
                      ? "Add custom medical alert badge (e.g., Severe Peanut Allergy)..."
                      : "Thêm cảnh báo y tế mới (ví dụ: Dị ứng đậu phộng nặng)..."
                  }
                  data-testid="add-medical-alert-input"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  icon="plus"
                  onClick={handleAddAlert}
                  data-testid="add-medical-alert-btn"
                >
                  {isEn ? "Add" : "Thêm"}
                </Button>
              </div>
            </section>
          </div>

          {/* Right Column: Emergency Card Preview & Field Inclusion Toggle (Span 5) */}
          <div className="space-y-6 lg:col-span-5 lg:sticky lg:top-24">
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="emergency-card-config-panel"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {isEn ? "Emergency Card Inclusion" : "Thông tin hiển thị trên Thẻ"}
                </h3>
                <Badge tone="brand">{isEn ? "Field Controls" : "Tùy chọn mục"}</Badge>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? "Choose which sensitive clinical categories are visible on your public lockscreen emergency card."
                  : "Chọn các mục lâm sàng được phép hiển thị trên thẻ cấp cứu mở nhanh khi khóa máy."}
              </p>

              <div className="space-y-2">
                {[
                  { key: "allergies", label: isEn ? "Allergies & Reactions" : "Dị ứng & Phản ứng" },
                  { key: "current_medications", label: isEn ? "Active Medications" : "Thuốc đang sử dụng" },
                  { key: "conditions", label: isEn ? "Chronic Conditions" : "Bệnh lý nền" },
                  { key: "blood_type", label: isEn ? "Blood Type" : "Nhóm máu" },
                  { key: "emergency_contact", label: isEn ? "Emergency Contact" : "Người liên hệ khẩn cấp" },
                ].map((item) => (
                  <label
                    key={item.key}
                    className="flex items-center justify-between p-2.5 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] hover:bg-[var(--surface-hover)] cursor-pointer text-xs font-semibold text-[var(--text-primary)] transition"
                  >
                    <span>{item.label}</span>
                    <input
                      type="checkbox"
                      checked={includedFields[item.key as keyof typeof includedFields]}
                      onChange={(e) =>
                        setIncludedFields({
                          ...includedFields,
                          [item.key]: e.target.checked,
                        })
                      }
                      className="rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-500)]"
                      data-testid={`toggle-inclusion-${item.key}`}
                    />
                  </label>
                ))}
              </div>
            </section>

            {/* Live High-Contrast Card Preview */}
            <div
              className="rounded-[var(--radius-2xl)] border-2 border-[color:var(--status-danger-border)] bg-[var(--bg-elev-3)] p-5 shadow-2xl space-y-4 relative overflow-hidden"
              data-testid="live-emergency-card-preview"
            >
              <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                <div className="flex items-center gap-2 text-[var(--status-danger-text)]">
                  <Icon name="emergency" size="1.4rem" />
                  <span className="font-bold tracking-widest text-xs uppercase">
                    CLARA EMERGENCY MEDICAL ID
                  </span>
                </div>
                {includedFields.blood_type ? (
                  <span className="rounded-lg bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-2.5 py-1 text-sm font-extrabold text-[var(--status-danger-text)]">
                    {bloodType}
                  </span>
                ) : null}
              </div>

              <div>
                <h4 className="text-lg font-bold text-[var(--text-primary)] leading-tight">
                  {fullName || profileData?.display_name || (isEn ? "Personal Profile" : "Hồ sơ cá nhân")}
                </h4>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  {dateOfBirth ? `${isEn ? "DOB:" : "NS:"} ${dateOfBirth}` : ""}
                </p>
              </div>

              {/* Alert Badges in Preview */}
              {medicalAlerts.length > 0 ? (
                <div className="space-y-1.5">
                  <p className="text-[11px] font-bold text-[var(--status-danger-text)] uppercase tracking-wide">
                    {isEn ? "Medical Alerts" : "Cảnh báo Y tế Đặc biệt"}
                  </p>
                  <div className="space-y-1">
                    {medicalAlerts.map((a, i) => (
                      <div
                        key={i}
                        className="rounded-lg bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border border-[color:var(--status-danger-border)] px-2.5 py-1 text-xs font-bold"
                      >
                        {a}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Allergies */}
              {includedFields.allergies ? (
                <div className="space-y-1 text-xs">
                  <p className="font-semibold text-[var(--text-secondary)]">
                    {isEn ? "Allergies:" : "Dị ứng:"}
                  </p>
                  {profileData?.allergies && profileData.allergies.length > 0 ? (
                    <ul className="list-disc pl-4 space-y-0.5 text-[var(--text-primary)]">
                      {profileData.allergies.map((a) => (
                        <li key={a.id}>
                          <strong>{a.name}</strong> {a.severity ? `(${a.severity})` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[var(--text-muted)] italic">
                      {isEn ? "None recorded" : "Không có ghi nhận dị ứng"}
                    </p>
                  )}
                </div>
              ) : null}

              {/* Medications */}
              {includedFields.current_medications ? (
                <div className="space-y-1 text-xs">
                  <p className="font-semibold text-[var(--text-secondary)]">
                    {isEn ? "Current Medications:" : "Thuốc đang sử dụng:"}
                  </p>
                  {profileData?.medications && profileData.medications.length > 0 ? (
                    <ul className="list-disc pl-4 space-y-0.5 text-[var(--text-primary)]">
                      {profileData.medications.map((m) => (
                        <li key={m.id}>
                          {m.name} {m.dose ? `· ${m.dose}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[var(--text-muted)] italic">
                      {isEn ? "None recorded" : "Không có đơn thuốc hoạt động"}
                    </p>
                  )}
                </div>
              ) : null}

              {/* Conditions */}
              {includedFields.conditions ? (
                <div className="space-y-1 text-xs">
                  <p className="font-semibold text-[var(--text-secondary)]">
                    {isEn ? "Conditions:" : "Bệnh lý nền:"}
                  </p>
                  {profileData?.conditions && profileData.conditions.length > 0 ? (
                    <ul className="list-disc pl-4 space-y-0.5 text-[var(--text-primary)]">
                      {profileData.conditions.map((c) => (
                        <li key={c.id}>{c.name}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[var(--text-muted)] italic">
                      {isEn ? "None recorded" : "Không có tiền sử bệnh lý nền"}
                    </p>
                  )}
                </div>
              ) : null}

              {/* Emergency Contact */}
              {includedFields.emergency_contact && emergencyContactName ? (
                <div className="rounded-xl bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-3 text-xs text-[var(--text-secondary)] flex items-center justify-between">
                  <div>
                    <span className="font-bold text-[var(--text-secondary)] block mb-0.5">
                      {isEn ? "Emergency Contact:" : "Liên hệ khẩn cấp:"}
                    </span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {emergencyContactName} ({emergencyContactRelationship}) ·{" "}
                      <strong className="font-mono text-[var(--text-brand)]">
                        {emergencyContactPhone}
                      </strong>
                    </span>
                  </div>
                  <Icon name="contact" size="1.2rem" className="text-[var(--text-brand)]" />
                </div>
              ) : null}

              {/* Quick QR Share Action */}
              <div className="pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setQrModalOpen(true)}
                  className="w-full justify-center gap-2 rounded-xl text-xs font-bold border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] hover:opacity-90"
                >
                  <Icon name="scan" size="1rem" />
                  <span>{isEn ? "Show Emergency QR Code" : "Xem Mã QR Cấp Cứu Nhanh"}</span>
                </Button>
              </div>

              <p className="text-[10px] text-[var(--text-muted)] border-t border-[color:var(--shell-border)]/60 pt-2 italic text-center">
                {isEn
                  ? "Self-declared emergency medical summary for first responder decision support. Not a doctor prescription."
                  : "Bản tóm tắt y tế khẩn cấp tự khai báo hỗ trợ người cấp cứu. Không thay thế chẩn đoán bác sĩ."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Quick Emergency QR Modal */}
      <EmergencyQrModal
        open={qrModalOpen}
        onClose={() => setQrModalOpen(false)}
        patientName={fullName || profileData?.display_name || "Nguyễn Văn A"}
        bloodType={bloodType}
        emergencyContact={{
          name: emergencyContactName,
          phone: emergencyContactPhone,
          relationship: emergencyContactRelationship,
        }}
        medicalAlerts={medicalAlerts}
        isEn={isEn}
      />
    </div>
  );
}
