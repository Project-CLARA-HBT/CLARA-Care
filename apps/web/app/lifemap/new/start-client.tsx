"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { GuidedFlowShell } from "@/components/guided-flow";
import {
  createLifeMapEpisodeDraft,
  listLifeMapEpisodeDrafts,
} from "@/lib/guided-flows";
import { guidedFlowSteps } from "@/lib/guided-flow-registry";

const STEPS = guidedFlowSteps("lifemapEpisode", "vi");

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `lifemap-${Date.now()}-create`;
}

export default function LifeMapDraftStart() {
  const router = useRouter();
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
      eyebrow="LifeMap"
      title="Tạo hành trình sức khoẻ"
      description="Đang mở bản nháp an toàn của bạn…"
      steps={STEPS}
      currentStep={0}
      saveState={
        error
          ? {
              kind: "error",
              message: "Chưa thể mở bản nháp. Vui lòng tải lại trang để thử lại.",
            }
          : { kind: "saving", message: "Đang chuẩn bị…" }
      }
    >
      <div
        aria-label="Đang chuẩn bị hành trình"
        className="h-28 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]"
      />
    </GuidedFlowShell>
  );
}
