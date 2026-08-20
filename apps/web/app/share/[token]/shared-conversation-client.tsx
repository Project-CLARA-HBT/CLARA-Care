"use client";

import { useEffect, useState } from "react";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { Badge } from "@/components/ui/badge";
import { InlineError, SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  WorkspacePublicConversation,
  getWorkspacePublicConversation,
} from "@/lib/workspace";

type SharedConversationClientProps = {
  token: string;
};

export default function SharedConversationClient({
  token,
}: SharedConversationClientProps) {
  const language = useUILanguage();
  const copy = (key: UITranslationKey) => t(language, key);
  const [payload, setPayload] = useState<WorkspacePublicConversation | null>(
    null,
  );
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

  return (
    <main className="mx-auto min-h-dvh max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <SurfaceCard className="p-4 sm:p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
          {copy("workspace.shared.eyebrow")}
        </p>
        <h1 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">
          {payload?.title || copy("workspace.shared.title")}
        </h1>
        {payload?.expires_at ? (
          <div className="mt-2">
            <Badge tone="warn" icon="schedule">
              {copy("workspace.shared.expires")}:{" "}
              {formatLocaleDate(language, payload.expires_at, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </Badge>
          </div>
        ) : null}
        <div className="mt-2">
          <Badge tone="neutral" icon="lock">
            {copy("workspace.shared.readOnly")}
          </Badge>
        </div>
      </SurfaceCard>

      {isLoading ? (
        <SurfaceCard className="mt-4 p-4 text-sm text-[var(--text-secondary)]">
          {copy("workspace.shared.loading")}
        </SurfaceCard>
      ) : null}

      {error ? (
        <div className="mt-4">
          <InlineError message={error} />
        </div>
      ) : null}

      {!isLoading && !error && payload?.messages?.length ? (
        <div className="mt-4 space-y-4">
          {payload.messages.map((message) => (
            <SurfaceCard key={message.query_id} className="p-4">
              <header className="mb-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-brand)]">
                  {copy("workspace.shared.question")}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-[var(--text-primary)]">
                  {message.query}
                </p>
              </header>
              <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <MarkdownAnswer answer={message.answer} citations={[]} />
              </div>
            </SurfaceCard>
          ))}
        </div>
      ) : null}

      {!isLoading && !error && !payload?.messages?.length ? (
        <SurfaceCard className="mt-4 p-4 text-sm text-[var(--text-secondary)]">
          {copy("workspace.shared.empty")}
        </SurfaceCard>
      ) : null}
    </main>
  );
}
