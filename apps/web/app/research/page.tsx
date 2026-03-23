"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import api from "@/lib/http-client";
import { UserRole, getRole } from "@/lib/auth-store";
import { ChatResponse, getChatIntentDebug, getChatReply } from "@/lib/chat";

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Normal",
  researcher: "Researcher",
  doctor: "Doctor"
};

export default function ResearchPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [chatDebug, setChatDebug] = useState<ReturnType<typeof getChatIntentDebug> | null>(null);

  useEffect(() => {
    setRole(getRole());
  }, []);

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? "Normal", [role]);
  const isDev = process.env.NODE_ENV !== "production";

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextQuery = query.trim();
    if (!nextQuery) return;

    setError("");
    setIsSubmitting(true);
    setLastQuery(nextQuery);
    setAnswer("");

    try {
      const response = await api.post<ChatResponse>("/chat", { message: nextQuery });
      const nextAnswer = getChatReply(response.data);

      if (!nextAnswer) {
        throw new Error("Phản hồi từ chat không có nội dung.");
      }

      setAnswer(nextAnswer);
      setChatDebug(getChatIntentDebug(response.data));
      setQuery("");
    } catch (submitError) {
      const fallbackMessage = "Không thể gửi câu hỏi. Vui lòng thử lại.";
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell title="Research Workspace">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-slate-600">Đặt câu hỏi nghiên cứu và nhận phản hồi từ CLARA.</p>
          <span className="rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            Role: {roleLabel}
          </span>
        </div>

        <form className="space-y-3" onSubmit={onSubmit}>
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            placeholder="Nhập câu hỏi nghiên cứu..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            disabled={isSubmitting}
          />
          <button
            type="submit"
            disabled={isSubmitting || !query.trim()}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSubmitting ? "Đang xử lý..." : "Gửi câu hỏi"}
          </button>
        </form>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        ) : null}

        {isSubmitting ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            CLARA đang phân tích câu hỏi...
          </div>
        ) : null}

        {answer ? (
          <article className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Q</p>
            <p className="text-sm text-slate-700">{lastQuery}</p>
            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">A</p>
            <p className="whitespace-pre-wrap text-sm text-slate-900">{answer}</p>
          </article>
        ) : null}

        {isDev ? (
          <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Intent Debug (dev only)</p>
            <div className="mt-2 grid gap-1 text-sm text-slate-700">
              <p>role: {chatDebug?.role ?? "N/A"}</p>
              <p>intent: {chatDebug?.intent ?? "N/A"}</p>
              <p>confidence: {chatDebug?.confidence ?? "N/A"}</p>
              <p>emergency: {chatDebug?.emergency === undefined ? "N/A" : String(chatDebug.emergency)}</p>
              <p>model_used: {chatDebug?.model_used ?? "N/A"}</p>
            </div>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
