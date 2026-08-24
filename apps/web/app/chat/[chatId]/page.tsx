"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";

import { isChatV2Enabled } from "@/app/chat/_v2/flag";

/**
 * CLARA Dynamic Chat Route — /chat/[chatId]
 * Spec v5 Section 6.34: Shell: READ_COMPOSE, Archetype: Spatial Conversation Canvas.
 *
 * Renders the Spatial Conversation Canvas initialized with the requested conversation ID.
 */
const ChatV2Shell = dynamic(() => import("@/app/chat/_v2/ChatShell"), {
  ssr: false,
});

const LegacyChatWorkspacePage = dynamic(
  () => import("@/app/chat/_legacy/page-legacy"),
  { ssr: false },
);

export default function ChatConversationPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = Array.isArray(params?.chatId) ? params.chatId[0] : params?.chatId;

  if (isChatV2Enabled()) {
    return <ChatV2Shell initialChatId={chatId} />;
  }
  return <LegacyChatWorkspacePage />;
}
