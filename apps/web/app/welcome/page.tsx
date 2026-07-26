"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, Select } from "@/components/ui/field";
import { InlineError, SurfaceCard } from "@/components/ui/surface";
import { getRole } from "@/lib/auth-store";
import { getRoleHomePath } from "@/lib/navigation.config";
import {
  getPhrOnboarding,
  updatePhrOnboarding,
  type PhrOnboarding,
} from "@/lib/phr-onboarding";

type Step = 0 | 1 | 2;

const GENDERS = [
  ["", "Không muốn nói"],
  ["female", "Nữ"],
  ["male", "Nam"],
  ["other", "Khác"],
] as const;

const BLOOD_TYPES = ["", "A", "B", "AB", "O"] as const;

function Stepper({ step }: { step: Step }) {
  const items = ["Chào mừng", "Thông tin cơ bản", "Cá nhân hoá"];
  return (
    <ol className="flex items-center gap-2" aria-label="Tiến trình thiết lập">
      {items.map((label, index) => {
        const active = index === step;
        const done = index < step;
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold transition ${
                active
                  ? "bg-[var(--brand-600)] text-white"
                  : done
                    ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                    : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
              }`}
            >
              {done ? (
                <span className="material-symbols-outlined text-base" aria-hidden="true">
                  check
                </span>
              ) : (
                index + 1
              )}
            </span>
            <span
              className={`hidden text-xs font-medium sm:block ${
                active ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"
              }`}
            >
              {label}
            </span>
            {index < items.length - 1 ? (
              <span className="h-px flex-1 bg-[color:var(--shell-border)]" aria-hidden="true" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export default function WelcomePage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [fullName, setFullName] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [bloodType, setBloodType] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [consent, setConsent] = useState(false);

  const hydrate = useCallback((data: PhrOnboarding) => {
    const record = data.record;
    setFullName(record.full_name ?? "");
    setDob(record.date_of_birth ?? "");
    setGender(record.gender ?? "");
    setBloodType(record.blood_type ?? "");
    setHeightCm(record.height_cm != null ? String(record.height_cm) : "");
    setWeightKg(record.weight_kg != null ? String(record.weight_kg) : "");
    setConsent(Boolean(data.personalization_consent));
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getPhrOnboarding();
        if (!active) return;
        hydrate(data);
        if (!data.needs_onboarding) {
          router.replace(getRoleHomePath(getRole()));
          return;
        }
      } catch {
        // Fail open: if onboarding is unavailable, let the user proceed.
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [hydrate, router]);

  const numeric = (value: string): number | null => {
    const parsed = Number(value.replace(",", "."));
    return value.trim() && Number.isFinite(parsed) ? parsed : null;
  };

  const finish = useCallback(
    async (action: "complete" | "skip") => {
      setSaving(true);
      setError("");
      try {
        await updatePhrOnboarding(
          action === "skip"
            ? { action: "skip" }
            : {
                action: "complete",
                confirm_self_declared: true,
                personalization_consent: consent,
                full_name: fullName.trim(),
                date_of_birth: dob || null,
                gender,
                blood_type: bloodType,
                height_cm: numeric(heightCm),
                weight_kg: numeric(weightKg),
              },
        );
        router.replace(getRoleHomePath(getRole()));
        router.refresh();
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "Không thể lưu. Vui lòng thử lại.",
        );
        setSaving(false);
      }
    },
    [bloodType, consent, dob, fullName, gender, heightCm, router, weightKg],
  );

  const submitBasics = (event: FormEvent) => {
    event.preventDefault();
    setStep(2);
  };

  const yearOptions = useMemo(() => null, []);
  void yearOptions;

  return (
    <main className="mx-auto flex min-h-[calc(100vh-1rem)] w-full max-w-2xl flex-col justify-center px-4 py-10">
      <SurfaceCard className="overflow-hidden">
        <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-6 py-5">
          <Badge tone="brand" icon="spa">
            The Clara Care
          </Badge>
          <div className="mt-4">
            <Stepper step={step} />
          </div>
        </div>

        <div className="px-6 py-7">
          {error ? (
            <div className="mb-5">
              <InlineError message={error} />
            </div>
          ) : null}

          {loading ? (
            <div className="space-y-3" aria-label="Đang tải">
              <div className="h-6 w-2/3 animate-pulse rounded bg-[var(--surface-muted)]" />
              <div className="h-24 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
            </div>
          ) : step === 0 ? (
            <div className="space-y-6">
              <div>
                <h1 className="text-[var(--text-title)] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                  Chào mừng bạn đến với CLARA
                </h1>
                <p className="mt-3 max-w-prose text-[15px] leading-7 text-[var(--text-secondary)]">
                  CLARA là trợ lý sức khoẻ đồng hành cùng bạn theo thời gian — ghi nhớ, nhắc
                  nhở và giúp bạn chuẩn bị tốt hơn cho mỗi lần khám. CLARA không thay thế bác
                  sĩ và luôn để bạn nắm quyền kiểm soát dữ liệu của mình.
                </p>
              </div>
              <ul className="grid gap-3 sm:grid-cols-3">
                {[
                  ["timeline", "Hồ sơ sống", "Theo dõi thay đổi theo thời gian"],
                  ["medication", "An toàn thuốc", "Cảnh báo tương tác dựa trên bằng chứng"],
                  ["shield_person", "Bạn kiểm soát", "Chọn chia sẻ gì, với ai"],
                ].map(([icon, title, desc]) => (
                  <li
                    key={title}
                    className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4"
                  >
                    <span
                      className="material-symbols-outlined text-[var(--text-brand)]"
                      aria-hidden="true"
                    >
                      {icon}
                    </span>
                    <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                      {title}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{desc}</p>
                  </li>
                ))}
              </ul>
              <div className="flex flex-col gap-3 sm:flex-row-reverse">
                <Button block icon="arrow_forward" iconTrailing onClick={() => setStep(1)}>
                  Bắt đầu
                </Button>
                <Button
                  variant="ghost"
                  block
                  disabled={saving}
                  onClick={() => void finish("skip")}
                >
                  Bỏ qua, để sau
                </Button>
              </div>
            </div>
          ) : step === 1 ? (
            <form className="space-y-5" onSubmit={submitBasics}>
              <div>
                <h1 className="text-[var(--text-title)] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                  Một vài thông tin cơ bản
                </h1>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  Tất cả đều không bắt buộc. Bạn có thể bỏ trống và cập nhật bất cứ lúc nào
                  trong Hồ sơ.
                </p>
              </div>
              <Field
                label="Tên hiển thị"
                optional
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Ví dụ: Nguyễn An"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  label="Ngày sinh"
                  optional
                  type="date"
                  value={dob}
                  onChange={(event) => setDob(event.target.value)}
                />
                <Select
                  label="Giới tính"
                  optional
                  value={gender}
                  onChange={(event) => setGender(event.target.value)}
                >
                  {GENDERS.map(([value, label]) => (
                    <option key={value || "none"} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
                <Select
                  label="Nhóm máu"
                  optional
                  value={bloodType}
                  onChange={(event) => setBloodType(event.target.value)}
                >
                  {BLOOD_TYPES.map((value) => (
                    <option key={value || "none"} value={value}>
                      {value || "Chưa rõ"}
                    </option>
                  ))}
                </Select>
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Chiều cao"
                    optional
                    hint="(cm)"
                    inputMode="decimal"
                    value={heightCm}
                    onChange={(event) => setHeightCm(event.target.value)}
                    placeholder="170"
                  />
                  <Field
                    label="Cân nặng"
                    optional
                    hint="(kg)"
                    inputMode="decimal"
                    value={weightKg}
                    onChange={(event) => setWeightKg(event.target.value)}
                    placeholder="62"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row-reverse">
                <Button type="submit" block icon="arrow_forward" iconTrailing>
                  Tiếp tục
                </Button>
                <Button type="button" variant="secondary" block onClick={() => setStep(0)}>
                  Quay lại
                </Button>
              </div>
            </form>
          ) : (
            <div className="space-y-5">
              <div>
                <h1 className="text-[var(--text-title)] font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
                  Cá nhân hoá gợi ý cho bạn
                </h1>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  Bạn có thể cho phép CLARA dùng hồ sơ của bạn để cá nhân hoá câu trả lời và
                  cảnh báo an toàn. Bạn có thể thay đổi lựa chọn này bất cứ lúc nào.
                </p>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={consent}
                onClick={() => setConsent((value) => !value)}
                className="focus-ring flex w-full items-center gap-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-left transition hover:border-[color:var(--shell-border-strong)]"
              >
                <span
                  className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                    consent ? "bg-[var(--brand-600)]" : "bg-[var(--surface-muted)]"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                      consent ? "left-[1.375rem]" : "left-0.5"
                    }`}
                  />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[var(--text-primary)]">
                    Cho phép cá nhân hoá
                  </span>
                  <span className="mt-0.5 block text-xs leading-5 text-[var(--text-secondary)]">
                    Dùng hồ sơ sức khoẻ để gợi ý phù hợp hơn. Không bắt buộc.
                  </span>
                </span>
              </button>

              <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]">
                Thông tin bạn nhập là tự khai báo, không phải chẩn đoán y tế. CLARA hỗ trợ
                tham khảo và không thay thế tư vấn của bác sĩ.
              </p>

              <div className="flex flex-col gap-3 sm:flex-row-reverse">
                <Button
                  block
                  icon="check"
                  loading={saving}
                  loadingLabel="Đang lưu…"
                  onClick={() => void finish("complete")}
                >
                  Hoàn tất
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  block
                  disabled={saving}
                  onClick={() => setStep(1)}
                >
                  Quay lại
                </Button>
              </div>
            </div>
          )}
        </div>
      </SurfaceCard>

      {!loading && step === 0 ? (
        <p className="mt-5 text-center text-xs text-[var(--text-muted)]">
          Bạn luôn có thể chỉnh sửa hoặc xoá dữ liệu trong phần Hồ sơ và Quyền dữ liệu.
        </p>
      ) : null}
    </main>
  );
}
