"use client";

import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilFlowCanvas from "@/components/council/council-flow-canvas";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { CouncilRunSnapshot, loadCouncilSnapshot } from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

function resolveNeedsMoreInfo(snapshot: CouncilRunSnapshot): boolean {
  const root = snapshot.raw as Record<string, unknown> | null;
  if (!root || typeof root !== "object") return false;

  const direct = root.needs_more_info;
  if (typeof direct === "boolean") return direct;

  const analyze = root.analyze as Record<string, unknown> | null;
  if (analyze && typeof analyze === "object" && typeof analyze.needs_more_info === "boolean") {
    return analyze.needs_more_info;
  }
  return false;
}

export default function CouncilDeepDivePage() {
  const [snapshot, setSnapshot] = useState<CouncilRunSnapshot | null>(null);

  useEffect(() => {
    setSnapshot(loadCouncilSnapshot());
  }, []);

  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);

  return (
    <PageShell
      title="Council Deep Dive"
      description="Trace chuyên sâu cho từng chuyên khoa và raw payload preview để debug/kiểm định."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        {!view ? (
          <CouncilEmptyState
            title="Chưa có dữ liệu deep dive"
            description="Tạo một ca hội chẩn mới để mở Deep Dive."
          />
        ) : (
          <>
            <CouncilFlowCanvas
              isEmergency={view.urgencyTone === "emergency"}
              needsMoreInfo={resolveNeedsMoreInfo(view.snapshot)}
              hasCitations={view.citations.length > 0}
              confidenceScore={view.snapshot.result.confidenceScore ?? null}
            />

            <CouncilSection eyebrow="Deep Sections" title="Bóc tách theo cụm chuyên sâu">
              {!view.deepDive.sections.length ? (
                <p className="text-sm text-[var(--text-secondary)]">Không có deep sections trong payload hiện tại.</p>
              ) : (
                <div className="space-y-3">
                  {view.deepDive.sections.map((section, index) => (
                    <article
                      key={`${section.title}-${index}`}
                      className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4"
                    >
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{section.title}</p>
                      <div className="mt-2">
                        <CouncilList items={section.items} emptyText="Không có chi tiết cho section này." />
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </CouncilSection>

            <CouncilSection eyebrow="Raw Payload" title="Preview dữ liệu thô">
              <pre className="max-h-[560px] overflow-auto rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-xs leading-6 text-[var(--text-secondary)]">
                {view.deepDive.rawPreview}
              </pre>
            </CouncilSection>
          </>
        )}
      </div>
    </PageShell>
  );
}
