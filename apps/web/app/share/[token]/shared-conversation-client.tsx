"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { sha256Hex } from "@/lib/analytics";
import {
  WorkspacePublicConversation,
  getWorkspacePublicConversation,
} from "@/lib/workspace";

type SharedConversationClientProps = {
  token: string;
};

export function getProofFingerprint(token: string): string {
  if (!token) return "CAP:00000000...";
  try {
    const hash = sha256Hex(token);
    return `SHA-256:${hash.slice(0, 8)}...${hash.slice(-8)}`;
  } catch {
    return `CAP:${token.slice(0, 8)}...`;
  }
}

export function getExpiryCountdown(
  expiresAt?: string | null,
  language: "vi" | "en" = "vi",
): {
  label: string;
  formattedDate: string;
  tone: BadgeTone;
  isExpired: boolean;
} {
  if (!expiresAt) {
    return {
      label: t(language, "workspace.shared.neverExpires"),
      formattedDate: t(language, "workspace.shared.neverExpires"),
      tone: "neutral",
      isExpired: false,
    };
  }

  const expiryTime = new Date(expiresAt).getTime();
  if (Number.isNaN(expiryTime)) {
    return {
      label: t(language, "workspace.shared.neverExpires"),
      formattedDate: t(language, "workspace.shared.neverExpires"),
      tone: "neutral",
      isExpired: false,
    };
  }

  const formattedDate = formatLocaleDate(language, expiresAt, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const now = Date.now();
  const diffMs = expiryTime - now;

  if (diffMs <= 0) {
    return {
      label: `${t(language, "workspace.shared.expiredBadge")}: ${formattedDate}`,
      formattedDate,
      tone: "danger",
      isExpired: true,
    };
  }

  const diffHours = Math.max(1, Math.ceil(diffMs / (1000 * 60 * 60)));
  const diffDays = Math.max(1, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));

  if (diffHours < 24) {
    const hours = diffHours;
    const timeLabel =
      language === "vi" ? `Hết hạn sau ${hours} giờ` : `Expires in ${hours}h`;
    return {
      label: `${timeLabel} (${formattedDate})`,
      formattedDate,
      tone: "warn",
      isExpired: false,
    };
  }

  const dayLabel =
    language === "vi" ? `Còn ${diffDays} ngày` : `${diffDays} days left`;
  return {
    label: `${dayLabel} (${formattedDate})`,
    formattedDate,
    tone: "ok",
    isExpired: false,
  };
}

export default function SharedConversationClient({
  token,
}: SharedConversationClientProps) {
  const language = useUILanguage();
  const copy = (key: UITranslationKey, params?: Record<string, string | number>) =>
    t(language, key, params);

  const [payload, setPayload] = useState<WorkspacePublicConversation | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const run = async () => {
      setIsLoading(true);
      setError("");
      try {
        const data = await getWorkspacePublicConversation(token);
        if (!active) return;
        setPayload(data);
      } catch {
        if (!active) return;
        setPayload(null);
        // Public capability failures deliberately collapse token-not-found,
        // revocation, expiry and transport details into one PII-free state.
        setError(t(language, "workspace.shared.unavailable"));
      } finally {
        if (active) setIsLoading(false);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [token, language]);

  const proofFingerprint = useMemo(() => getProofFingerprint(token), [token]);
  const expiryInfo = useMemo(
    () => getExpiryCountdown(payload?.expires_at, language),
    [payload?.expires_at, language],
  );

  const clinicalTimestamp = useMemo(() => {
    if (!payload?.messages?.length) return null;
    const lastMsg = payload.messages[payload.messages.length - 1];
    const rawTime = lastMsg.created_at;
    if (!rawTime) return null;
    return {
      iso: rawTime,
      formatted: formatLocaleDate(language, rawTime, {
        dateStyle: "medium",
        timeStyle: "short",
      }),
    };
  }, [payload, language]);

  return (
    <div
      className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] antialiased"
      data-shell-mode="PUBLIC_SHARE"
      data-layout-archetype="Public Shared Packet Reader"
      data-testid="public-shared-packet-reader"
    >
      {/* Standalone Brand Header (Suppress all authenticated nav/dock) */}
      <header className="border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-lg focus-ring text-[var(--text-primary)] hover:opacity-90"
            aria-label="The Clara Care"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--brand-600)] text-sm font-black text-[var(--button-primary-text)] shadow-sm">
              C
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-extrabold tracking-tight">
                The <span className="text-[var(--text-brand)]">Clara Care</span>
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                {copy("workspace.shared.portalSubtitle")}
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            <Badge tone="neutral" icon="lock">
              {copy("workspace.shared.readOnly")}
            </Badge>
          </div>
        </div>
      </header>

      {/* Main Content Area (Editorial Constrained Width) */}
      <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8 space-y-6">
        {/* 1. Cryptographic Proof & Signature Banner */}
        <SurfaceCard className="p-4 sm:p-5" data-testid="cryptographic-proof-banner">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Icon name="check" size="1.1rem" className="text-[var(--text-ok)]" />
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  {copy("workspace.shared.cryptoProof")}
                </h2>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                {copy("workspace.shared.provenanceDesc")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ok" icon="check">
                {copy("workspace.shared.cryptoVerified")}
              </Badge>
              <Badge tone="brand" icon="clinical-notes">
                {copy("workspace.shared.fidesStandard")}
              </Badge>
              <Badge tone="neutral" icon="progress">
                {proofFingerprint}
              </Badge>
            </div>
          </div>
        </SurfaceCard>

        {/* 2. Verification Badges & Clinical Timestamps */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Verified Clinical Timestamp */}
          <SurfaceCard className="p-4 sm:p-5" data-testid="clinical-timestamp">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <Icon name="calendar" size="1.1rem" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {copy("workspace.shared.verifiedTimestamp")}
                </p>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {clinicalTimestamp ? clinicalTimestamp.formatted : copy("workspace.shared.activeBadge")}
                </p>
                <p className="text-xs text-[var(--text-secondary)]">
                  {copy("workspace.shared.verifiedTimestampDesc")}
                </p>
              </div>
            </div>
          </SurfaceCard>

          {/* Expiration Status Badge */}
          <SurfaceCard className="p-4 sm:p-5" data-testid="expiration-badge">
            <div className="flex items-start gap-3">
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                  expiryInfo.isExpired
                    ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                    : "bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                }`}
              >
                <Icon name={expiryInfo.isExpired ? "warning" : "calendar"} size="1.1rem" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  {copy("workspace.shared.expires")}
                </p>
                <div>
                  <Badge tone={expiryInfo.tone} icon={expiryInfo.isExpired ? "warning" : "calendar"}>
                    {expiryInfo.label}
                  </Badge>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  {expiryInfo.isExpired
                    ? copy("workspace.shared.unavailable")
                    : copy("workspace.shared.packetScope")}
                </p>
              </div>
            </div>
          </SurfaceCard>
        </div>

        {/* Loading State */}
        {isLoading ? (
          <SurfaceCard className="p-6 text-center" data-testid="loading-state">
            <div className="mx-auto flex h-10 w-10 animate-spin items-center justify-center rounded-full border-2 border-[var(--brand-600)] border-t-transparent text-[var(--text-brand)]">
              <Icon name="progress" size="1.2rem" />
            </div>
            <p className="mt-3 text-sm font-medium text-[var(--text-secondary)]">
              {copy("workspace.shared.loading")}
            </p>
          </SurfaceCard>
        ) : null}

        {/* Error / Expired / Revoked State */}
        {error ? (
          <SurfaceCard className="border-[color:var(--status-danger-border)] p-6 sm:p-8 text-center" data-testid="expired-revoked-state">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]">
              <Icon name="warning" size="1.5rem" />
            </div>
            <h2 className="mt-3 text-lg font-bold text-[var(--text-primary)]">
              {copy("workspace.shared.unavailable")}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-xs sm:text-sm text-[var(--text-secondary)]">
              {language === "vi"
                ? "Liên kết xác thực không hợp lệ, đã hết thời hạn lưu hành hoặc đã bị chủ sở hữu thu hồi quyền truy cập vì lý do an toàn bảo mật."
                : "This authentication capability is invalid, has passed its expiration window, or was revoked by its owner for privacy and safety."}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Badge tone="danger" icon="warning">
                {copy("workspace.shared.expiredBadge")}
              </Badge>
              <Badge tone="ok" icon="check">
                {copy("workspace.shared.zeroCotBadge")}
              </Badge>
            </div>
            <div className="mt-6">
              <Link
                href="/"
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--surface-muted)] border border-[color:var(--shell-border)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-panel)] transition-colors focus-ring"
              >
                <Icon name="arrow-left" size="0.9rem" />
                {copy("workspace.shared.backHome")}
              </Link>
            </div>
          </SurfaceCard>
        ) : null}

        {/* 3. Sanitized Conversation / Visit Packet */}
        {!isLoading && !error && payload ? (
          <div className="space-y-6" data-testid="sanitized-packet">
            {/* Packet Hero Card */}
            <SurfaceCard className="p-5 sm:p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                      {copy("workspace.shared.packetType")}
                    </span>
                    <span className="text-xs text-[var(--text-muted)]">•</span>
                    <span className="text-xs font-mono text-[var(--text-muted)]">
                      #PKT-{payload.conversation_id}
                    </span>
                  </div>
                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                    {payload.title || copy("workspace.shared.title")}
                  </h1>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="neutral">
                    {copy("workspace.shared.totalMessages", {
                      count: payload.messages?.length || 0,
                    })}
                  </Badge>
                </div>
              </div>

              {/* Clinical Safety Disclaimer Box */}
              <div className="mt-4 rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3.5 text-xs leading-relaxed text-[var(--status-warn-text)]">
                <div className="flex items-start gap-2.5">
                  <Icon name="warning" size="1rem" className="shrink-0 mt-0.5" />
                  <p>{copy("workspace.shared.safetyNotice")}</p>
                </div>
              </div>
            </SurfaceCard>

            {/* Sanitized Message Turns List */}
            {payload.messages?.length ? (
              <div className="space-y-4" data-testid="shared-messages-list">
                {payload.messages.map((message, index) => {
                  const isResearch = message.role === "research_report";
                  const msgFormattedTime = message.created_at
                    ? formatLocaleDate(language, message.created_at, {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : null;

                  return (
                    <SurfaceCard
                      key={message.query_id || index}
                      className="p-5 sm:p-6 space-y-4"
                      data-testid={`shared-turn-${message.query_id || index}`}
                    >
                      {/* Query Turn */}
                      <div className="space-y-2" data-testid={`shared-query-${message.query_id || index}`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge tone="brand" icon="chat">
                              {copy("workspace.shared.patientRole")}
                            </Badge>
                          </div>
                          {msgFormattedTime ? (
                            <span className="text-xs text-[var(--text-muted)]">
                              {msgFormattedTime}
                            </span>
                          ) : null}
                        </div>
                        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 px-4 py-3">
                          <p className="whitespace-pre-wrap text-sm sm:text-base font-medium leading-relaxed text-[var(--text-primary)]">
                            {message.query}
                          </p>
                        </div>
                      </div>

                      {/* AI Synthesized Answer Turn */}
                      <div className="space-y-2 pt-2 border-t border-[color:var(--shell-border)]" data-testid={`shared-answer-${message.query_id || index}`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge tone="ok" icon="clinical-notes">
                              {isResearch
                                ? copy("workspace.shared.researchRole")
                                : copy("workspace.shared.assistantRole")}
                            </Badge>
                            <span className="text-[11px] font-semibold text-[var(--text-muted)]">
                              {copy("workspace.shared.aiGrounding")}
                            </span>
                          </div>
                        </div>

                        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
                          <MarkdownAnswer
                            answer={message.answer}
                            citations={[]}
                            uiLanguage={language}
                          />
                        </div>
                      </div>
                    </SurfaceCard>
                  );
                })}
              </div>
            ) : (
              <SurfaceCard className="p-6 text-center text-sm text-[var(--text-secondary)]" data-testid="empty-state">
                {copy("workspace.shared.empty")}
              </SurfaceCard>
            )}

            {/* 4. Sources & Provenance Footer */}
            <SurfaceCard className="p-4 sm:p-5" data-testid="packet-provenance">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-0.5">
                  <p className="text-xs font-bold text-[var(--text-primary)]">
                    {copy("workspace.shared.provenanceTitle")}
                  </p>
                  <p className="text-[11px] text-[var(--text-secondary)]">
                    Dược thư Quốc gia Việt Nam 2022 · Bộ Y tế · openFDA · DrugBank v5.1
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="ok" icon="check">
                    Zero-CoT Privacy
                  </Badge>
                  <Badge tone="brand" icon="clinical-notes">
                    FIDES Sealed
                  </Badge>
                </div>
              </div>
            </SurfaceCard>
          </div>
        ) : null}
      </main>
    </div>
  );
}
