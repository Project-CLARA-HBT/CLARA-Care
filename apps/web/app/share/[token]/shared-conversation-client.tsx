"use client";

import { useEffect, useState } from "react";
import MarkdownAnswer from "@/components/research/markdown-answer";
import { Badge } from "@/components/ui/badge";
import { InlineError, SurfaceCard } from "@/components/ui/surface";
import {
  WorkspacePublicConversation,
  getWorkspacePublicConversation,
} from "@/lib/workspace";

type SharedConversationClientProps = {
  token: string;
};

export default function SharedConversationClient({ token }: SharedConversationClientProps) {
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
      } catch (cause) {
        if (!active) return;
        setPayload(null);
        setError(
          cause instanceof Error
            ? cause.message
            : "Không thể tải conversation được chia sẻ."
        );
      } finally {
        if (active) setIsLoading(false);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <main className="mx-auto min-h-dvh max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <SurfaceCard className="p-4 sm:p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
          Public Share
        </p>
        <h1 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">
          {payload?.title || "Shared Conversation"}
        </h1>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Owner: {payload?.owner_label ?? "-"}
        </p>
        {payload?.expires_at ? (
          <div className="mt-2">
            <Badge tone="warn" icon="schedule">
              Link expires: {new Date(payload.expires_at).toLocaleString("vi-VN")}
            </Badge>
          </div>
        ) : null}
      </SurfaceCard>

      {isLoading ? (
        <SurfaceCard className="mt-4 p-4 text-sm text-[var(--text-secondary)]">
          Đang tải dữ liệu hội thoại...
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
                  Câu hỏi
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
    </main>
  );
}
