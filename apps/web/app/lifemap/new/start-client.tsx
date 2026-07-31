"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { GuidedFlowShell } from "@/components/guided-flow";
import {
  createLifeMapEpisodeDraft,
  listLifeMapEpisodeDrafts,
} from "@/lib/guided-flows";
import { guidedFlowSteps } from "@/lib/guided-flow-registry";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `lifemap-${Date.now()}-create`;
}

export default function LifeMapDraftStart() {
  const router = useRouter();
  const language = useUILanguage();
  const started = useRef(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let active = true;

    void listLifeMapEpisodeDrafts()
      .then(async (drafts) => drafts[0] ?? createLifeMapEpisodeDraft(newIdempotencyKey()))
      .then((draft) => {
        if (active) {
          router.replace(`/lifemap/new/${encodeURIComponent(draft.id)}/${draft.current_step}`);
        }
      })
      .catch(() => {
        if (active) setError(true);
      });

    return () => {
      active = false;
    };
  }, [router]);

  return (
    <GuidedFlowShell
      eyebrow={t(language, "lifemap.guided.eyebrow")}
      title={t(language, "lifemap.guided.start.title")}
      description={t(language, "lifemap.guided.start.description")}
      steps={guidedFlowSteps("lifemapEpisode", language)}
      currentStep={0}
      saveState={
        error
          ? {
              kind: "error",
              message: t(language, "lifemap.guided.start.loadError"),
            }
          : { kind: "saving", message: t(language, "lifemap.guided.start.preparing") }
      }
    >
      <div
        aria-label={t(language, "lifemap.guided.start.preparingAria")}
        className="h-28 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]"
      />
    </GuidedFlowShell>
  );
}
