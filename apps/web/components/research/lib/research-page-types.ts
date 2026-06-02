import { getChatIntentDebug } from "@/lib/chat";
import { ResearchTier2Result } from "@/lib/research";

export type Tier1Result = {
  tier: "tier1";
  answer: string;
  debug: ReturnType<typeof getChatIntentDebug> | null;
};

export type Tier2Result = {
  tier: "tier2";
} & ResearchTier2Result;

export type ResearchResult = Tier1Result | Tier2Result;

export type ConversationItem = {
  id: string;
  query: string;
  result: ResearchResult;
  createdAt: number;
};

export type FlowVisibilityMode =
  | "idle"
  | "flow-events"
  | "metadata-stages"
  | "local-fallback";
