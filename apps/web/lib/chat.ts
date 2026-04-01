export type ChatResponse = {
  message?: string;
  reply?: string;
  answer?: string;
  fallback?: boolean;
  fallback_reason?: string;
  role?: string;
  intent?: string;
  confidence?: number;
  emergency?: boolean;
  model_used?: string;
};

export type ChatIntentDebug = Pick<ChatResponse, "role" | "intent" | "confidence" | "emergency" | "model_used">;

export function getChatReply(data: ChatResponse): string | null {
  if (typeof data.reply === "string" && data.reply.trim()) return data.reply;
  if (typeof data.answer === "string" && data.answer.trim()) return data.answer;
  return null;
}

export function getChatIntentDebug(data: ChatResponse): ChatIntentDebug {
  return {
    role: data.role,
    intent: data.intent,
    confidence: data.confidence,
    emergency: data.emergency,
    model_used: data.model_used
  };
}
