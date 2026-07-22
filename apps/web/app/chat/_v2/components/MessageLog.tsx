"use client";

import { memo, useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import type { UILanguage } from "@/lib/ui-language";
import type { UserRole } from "@/lib/auth-store";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import TurnView from "@/app/chat/_v2/components/TurnView";
import { usePrefersReducedMotion } from "@/app/chat/_v2/theme/usePrefersReducedMotion";

/**
 * Virtualized message log for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Virtualizes long turn lists (Requirement 7.1) and exposes the log as an ARIA
 * live region so streaming/new turns are announced (Requirement 5.2). Auto
 * scrolls to the newest turn unless `prefers-reduced-motion` is set, in which
 * case it jumps without smooth animation (Requirement 4.5).
 */

export type MessageLogProps = {
  turns: ConversationItem[];
  uiLanguage: UILanguage;
  isRunning?: boolean;
  role?: UserRole;
  onLaunchResearch?: (query: string) => void;
};

function MessageLog({
  turns,
  uiLanguage,
  isRunning = false,
  role = "normal",
  onLaunchResearch,
}: MessageLogProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  const virtualizer = useVirtualizer({
    count: turns.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 280,
    overscan: 6,
  });

  // Keep the newest turn in view as turns arrive. Respect reduced motion
  // (Requirement 4.5): jump instantly instead of smooth-scrolling.
  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !turns.length) return;
    node.scrollTo({
      top: node.scrollHeight,
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [turns.length, isRunning, prefersReducedMotion]);

  const isEn = uiLanguage === "en";

  return (
    <div
      ref={scrollRef}
      className="clara-scrollbar h-full min-h-0 flex-1 overflow-y-auto"
      role="log"
      aria-live="polite"
      aria-relevant="additions text"
      aria-label={isEn ? "Conversation" : "Cuộc trò chuyện"}
    >
      <div
        style={{ height: `${virtualizer.getTotalSize()}px` }}
        className="relative mx-auto w-full max-w-3xl px-3 py-4"
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
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Memoized so the virtualized log only re-renders when its turn list, language,
 * or running flag change — not on every unrelated parent (`ChatShell`) state
 * update such as search text or transient notices (Requirement 7.2, Property
 * P9).
 */
export default memo(MessageLog);
