"use client";

import { useEffect, useMemo, useState } from "react";
import ResearchEmptyState from "@/components/research/research-empty-state";
import FlowTimelinePanel from "@/components/research/flow-timeline-panel";
import ResearchLabNav from "@/components/research/research-lab-nav";
import { createConversationItemFromPersisted, resolveFlowModeFromResult } from "@/components/research/lib/research-page-helpers";
import { ConversationItem, Tier2Result } from "@/components/research/lib/research-page-types";
import TelemetryDetailsPanel from "@/components/research/telemetry-details-panel";
import PageShell from "@/components/ui/page-shell";
import { listResearchConversations } from "@/lib/research";

type Tier2Conversation = ConversationItem & { result: Tier2Result };

function isTier2Conversation(item: ConversationItem): item is Tier2Conversation {
  return item.result.tier === "tier2";
}

export default function ResearchAnalyzePage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [conversation, setConversation] = useState<Tier2Conversation | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadLatest = async () => {
      setIsLoading(true);
      setError("");
      try {
        const rows = await listResearchConversations(120);
        if (cancelled) return;

        const items = rows
          .map((row) => createConversationItemFromPersisted(row))
          .sort((a, b) => b.createdAt - a.createdAt);
        setConversation(items.find((item) => isTier2Conversation(item)) ?? null);
      } catch (loadError) {
        if (cancelled) return;
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Không thể tải conversation tier2 mới nhất."
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadLatest();
    return () => {
      cancelled = true;
    };
  }, []);

  const flowMode = useMemo(
    () => (conversation ? resolveFlowModeFromResult(conversation.result) : "idle"),
    [conversation]
  );

  return (
    <PageShell
      title="Research Analyze"
      description="Theo dõi telemetry, verification và flow từ conversation tier2 mới nhất."
    >
      <div className="space-y-4">
        <ResearchLabNav />

        {isLoading ? (
          <section className="chrome-panel research-panel-modern rounded-[1.35rem] p-4 text-sm text-[var(--text-secondary)]">
            Đang tải dữ liệu phân tích...
          </section>
        ) : null}

        {error ? (
          <section className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            {error}
          </section>
        ) : null}

        {!isLoading && !error && !conversation ? (
          <ResearchEmptyState
            title="Chưa có conversation tier2 để phân tích"
            description="Chạy Research hoặc Deepdive trước khi mở Analyze."
          />
        ) : null}

        {conversation ? (
          <>
            <section className="chrome-panel research-panel-modern rounded-[1.35rem] p-5 sm:p-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                Latest Tier2 Conversation
              </p>
              <p className="mt-2 text-sm text-[var(--text-primary)]">
                <span className="font-semibold">Query:</span> {conversation.query}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
                  flow: {flowMode}
                </span>
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
                  verification: {conversation.result.verificationStatus?.verdict ?? "n/a"}
                </span>
                <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
                  confidence:{" "}
                  {typeof conversation.result.verificationStatus?.confidence === "number"
                    ? conversation.result.verificationStatus.confidence.toFixed(2)
                    : "n/a"}
                </span>
              </div>
            </section>

            <FlowTimelinePanel
              stages={conversation.result.flowStages}
              events={conversation.result.flowEvents}
              mode={flowMode}
              isProcessing={false}
            />

            <TelemetryDetailsPanel
              telemetry={conversation.result.telemetry}
              isProcessing={false}
            />
          </>
        ) : null}
      </div>
    </PageShell>
  );
}
