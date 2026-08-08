import type { Metadata } from "next";
import SharedConversationClient from "./shared-conversation-client";

type SharedConversationPageProps = {
  params: Promise<{ token: string }>;
};

export const metadata: Metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function SharedConversationPage({
  params,
}: SharedConversationPageProps) {
  const resolved = await params;
  return <SharedConversationClient token={resolved.token} />;
}
