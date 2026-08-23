"use client";

import MessageLog, {
  type MessageLogProps,
} from "@/app/chat/_v2/components/MessageLog";
import TurnView, {
  type TurnViewProps,
} from "@/app/chat/_v2/components/TurnView";

export type { MessageLogProps as ChatFeedProps, TurnViewProps as ChatTurnBubbleProps };
export const ChatFeed = MessageLog;
export const ChatTurnBubble = TurnView;
export default MessageLog;
