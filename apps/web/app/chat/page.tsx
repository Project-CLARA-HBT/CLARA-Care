"use client";

import dynamic from "next/dynamic";

import { isChatV2Enabled } from "@/app/chat/_v2/flag";

/**
 * CLARA Chat route gate (Requirement 8.1, 8.6; design Property P1).
 *
 * The rebuilt, componentized chat (`_v2/ChatShell`) is now the default. This
 * route renders it unless `CHAT_V2` is explicitly turned OFF
 * (`NEXT_PUBLIC_CHAT_V2=false|0|off`), in which case it falls back to the legacy
 * `ChatWorkspacePage` implementation verbatim and unchanged for instant rollback.
 *
 * Both implementations are loaded lazily. This keeps the preserved rollback
 * page available without coupling its large legacy workspace to the default
 * V2 route bundle.
 */
const ChatV2Shell = dynamic(() => import("@/app/chat/_v2/ChatShell"), {
  ssr: false,
});

const LegacyChatWorkspacePage = dynamic(
  () => import("@/app/chat/_legacy/page-legacy"),
  { ssr: false },
);

export default function ChatRouteGate() {
  if (isChatV2Enabled()) {
    return <ChatV2Shell />;
  }
  return <LegacyChatWorkspacePage />;
}
