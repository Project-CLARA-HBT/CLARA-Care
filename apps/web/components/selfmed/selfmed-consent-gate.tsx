"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { acceptConsent, getConsentStatus } from "@/lib/consent";

type SelfMedConsentGateProps = {
  children: ReactNode;
};

export default function SelfMedConsentGate({ children }: SelfMedConsentGateProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [accepted, setAccepted] = useState(false);
  const [requiredVersion, setRequiredVersion] = useState("");
  const [acceptedAt, setAcceptedAt] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const acceptedAtDisplay = acceptedAt
    ? new Date(acceptedAt).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" })
    : null;

  const refreshConsent = async (): Promise<boolean> => {
    setError("");
    try {
      const status = await getConsentStatus();
      setRequiredVersion(status.required_version);
      setAccepted(status.accepted);
      setAcceptedAt(status.accepted_at ?? null);
      return status.accepted;
    } catch (cause) {
      setAccepted(false);
      setError(cause instanceof Error ? cause.message : "Không thể kiểm tra consent y tế.");
      return false;
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await refreshConsent();
      setIsLoading(false);
    };
    void init();
  }, []);

  const onAccept = async () => {
    if (!requiredVersion) return;
    if (!checked) {
      setError("Vui lòng tick xác nhận trước khi tiếp tục.");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await acceptConsent({ consent_version: requiredVersion, accepted: true });
      const unlocked = await refreshConsent();
      if (!unlocked) {
        setError("Đã lưu xác nhận nhưng chưa lấy lại trạng thái mới. Vui lòng thử kiểm tra lại.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu xác nhận consent.");
    } finally {
      setIsSaving(false);
    }
  };

  const onRetryStatus = async () => {
    setIsLoading(true);
    await refreshConsent();
    setIsLoading(false);
  };

  if (isLoading) {
    return (
      <section className="chrome-panel rounded-[1.5rem] p-6">
        <p className="text-base font-semibold text-[var(--text-primary)]">Đang kiểm tra điều khoản sử dụng y tế...</p>
      </section>
    );
  }

  if (!accepted) {
    return (
      <section className="chrome-panel rounded-[1.5rem] border border-amber-300/60 p-6">
        <p className="inline-flex rounded-full border border-amber-300/55 bg-amber-100/60 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">
          Bước bắt buộc trước khi dùng
        </p>
        <h2 className="mt-3 text-2xl font-semibold text-[var(--text-primary)]">Tuyên bố miễn trừ trách nhiệm y tế</h2>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[var(--text-secondary)]">
          CLARA chỉ hỗ trợ cảnh báo an toàn thuốc và không thay thế bác sĩ. Không sử dụng ứng dụng để tự chẩn đoán,
          tự kê đơn hoặc tự điều chỉnh liều dùng.
        </p>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Xem đầy đủ tại{" "}
          <Link href="/legal/consent" className="font-semibold text-cyan-300 hover:underline">
            Đồng thuận sử dụng y tế
          </Link>
          {" "}và{" "}
          <Link href="/legal/privacy" className="font-semibold text-cyan-300 hover:underline">
            Chính sách quyền riêng tư
          </Link>
          .
        </p>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Phiên bản điều khoản hiện tại: <span className="font-semibold">{requiredVersion || "-"}</span>
        </p>

        <label className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
            className="mt-1 h-6 w-6 rounded border-[color:var(--shell-border)]"
          />
          <span className="text-sm font-medium leading-6 text-[var(--text-primary)]">
            Tôi đã đọc, hiểu và đồng ý với tuyên bố miễn trừ trách nhiệm y tế của CLARA.
          </span>
        </label>

        <button
          type="button"
          onClick={onAccept}
          disabled={isSaving || !checked}
          className="mt-4 min-h-12 rounded-xl border border-cyan-400/60 bg-cyan-500/20 px-5 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSaving ? "Đang lưu xác nhận..." : "Đồng ý và tiếp tục"}
        </button>

        {error ? (
          <div className="mt-3 space-y-2 rounded-xl border border-red-300/50 bg-red-500/10 p-3">
            <p className="text-sm text-red-200">{error}</p>
            <p className="text-xs text-red-100/90">Nếu mạng hoặc phiên đăng nhập vừa thay đổi, vui lòng kiểm tra lại trạng thái consent.</p>
            <button
              type="button"
              onClick={() => void onRetryStatus()}
              className="inline-flex min-h-11 items-center rounded-xl border border-red-300/55 bg-red-500/20 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/30"
            >
              Thử kiểm tra lại consent
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <section className="chrome-panel rounded-2xl border border-emerald-400/60 bg-emerald-500/10 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="material-symbols-outlined text-emerald-600 dark:text-emerald-300" aria-hidden="true">
            verified_user
          </span>
          <div>
            <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-100">
              Bạn đã đồng ý điều khoản sử dụng y tế của CLARA
            </p>
            <p className="text-xs text-emerald-700 dark:text-emerald-100/85">
              {acceptedAtDisplay ? `Đã xác nhận lúc ${acceptedAtDisplay}` : "Có thể bắt đầu sử dụng tủ thuốc."}
            </p>
          </div>
        </div>
      </section>
      {children}
    </div>
  );
}
