"use client";

import { useEffect, useState } from "react";
import MarkdownAnswer from "@/components/research/markdown-answer";
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
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950/50 sm:p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
          Public Share
        </p>
        <h1 className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">
          {payload?.title || "Shared Conversation"}
        </h1>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Owner: {payload?.owner_label ?? "-"}
        </p>
        {payload?.expires_at ? (
          <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
            Link expires: {new Date(payload.expires_at).toLocaleString("vi-VN")}
          </p>
        ) : null}
      </section>

      {isLoading ? (
        <section className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950/50 dark:text-slate-300">
          Đang tải dữ liệu hội thoại...
        </section>
      ) : null}

      {error ? (
        <section className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </section>
      ) : null}

      {!isLoading && !error && payload?.messages?.length ? (
        <div className="mt-4 space-y-4">
          {payload.messages.map((message) => (
            <article
              key={message.query_id}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950/40"
            >
              <header className="mb-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-cyan-700 dark:text-cyan-300">
                  Câu hỏi
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">
                  {message.query}
                </p>
              </header>
              <div className="rounded-xl border border-slate-200/80 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/40">
                <MarkdownAnswer answer={message.answer} citations={[]} />
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </main>
  );
}

