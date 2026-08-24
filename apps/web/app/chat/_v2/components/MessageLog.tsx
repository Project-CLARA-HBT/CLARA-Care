"use client";

import { memo, useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import type { UILanguage } from "@/lib/ui-language";
import { t } from "@/lib/i18n/catalog";
import type { UserRole } from "@/lib/auth-store";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import TurnView from "@/app/chat/_v2/components/TurnView";
import { usePrefersReducedMotion } from "@/app/chat/_v2/theme/usePrefersReducedMotion";
import type { SourceInspectionItem } from "@/components/shell/inspector-drawer";

/**
 * Virtualized message log for CLARA Chat (CHAT_V2 / Spec v8 READ_COMPOSE).
 * Constrains the main reading column to 760-900px centered canvas.
 */

export type MessageLogProps = {
  turns: ConversationItem[];
  uiLanguage: UILanguage;
  isRunning?: boolean;
  role?: UserRole;
  onLaunchResearch?: (query: string) => void;
  onSaveNote?: (answerText: string) => void;
  onInspectSource?: (source: SourceInspectionItem) => void;
  onInspectAllSources?: (sources: SourceInspectionItem[]) => void;
};

function MessageLog({
  turns,
  uiLanguage,
  isRunning = false,
  role = "normal",
  onLaunchResearch,
  onSaveNote,
  onInspectSource,
  onInspectAllSources,
}: MessageLogProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  const virtualizer = useVirtualizer({
    count: turns.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 280,
    overscan: 6,
  });

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !turns.length) return;
    node.scrollTo({
      top: node.scrollHeight,
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [turns.length, isRunning, prefersReducedMotion]);

  return (
    <div
      ref={scrollRef}
      className="clara-scrollbar h-full min-h-0 flex-1 overflow-y-auto"
      role="log"
      aria-live="polite"
      aria-relevant="additions text"
      aria-label={t(uiLanguage, "chat.messageLog.aria")}
    >
      {/* Centered reading column (760–900px) */}
      <div
        style={{ height: `${virtualizer.getTotalSize()}px` }}
        className="relative mx-auto w-full max-w-[860px] px-4 sm:px-6 py-4"
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const turn = turns[virtualRow.index];
          if (!turn) return null;
          return (
            <div
              key={turn.id}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
              className="pb-4"
            >
              <TurnView
                turn={turn}
                uiLanguage={uiLanguage}
                role={role}
                onLaunchResearch={onLaunchResearch}
                onSaveNote={onSaveNote}
                onInspectSource={onInspectSource}
                onInspectAllSources={onInspectAllSources}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default memo(MessageLog);
