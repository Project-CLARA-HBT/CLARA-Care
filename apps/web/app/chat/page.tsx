"use client";

import dynamic from "next/dynamic";

import LegacyChatWorkspacePage from "@/app/chat/_legacy/page-legacy";
import { isChatV2Enabled } from "@/app/chat/_v2/flag";

/**
 * CLARA Chat route gate (Requirement 8.1, 8.6; design Property P1).
 *
 * The rebuilt, componentized chat (`_v2/ChatShell`) is now the default. This
 * route renders it unless `CHAT_V2` is explicitly turned OFF
 * (`NEXT_PUBLIC_CHAT_V2=false|0|off`), in which case it falls back to the legacy
 * `ChatWorkspacePage` implementation verbatim and unchanged for instant rollback.
 *
 * The v2 shell is loaded lazily via `next/dynamic` so its code (and the new
 * design system) is never pulled into the bundle while the flag is off — the
 * legacy experience stays fully isolated.
 */
const ChatV2Shell = dynamic(() => import("@/app/chat/_v2/ChatShell"), {
  ssr: false,
});

export default function ChatRouteGate() {
  if (isChatV2Enabled()) {
    return <ChatV2Shell />;
  }
  return <LegacyChatWorkspacePage />;
}
