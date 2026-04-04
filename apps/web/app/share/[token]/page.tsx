import SharedConversationClient from "./shared-conversation-client";

type SharedConversationPageProps = {
  params: Promise<{ token: string }>;
};

export default async function SharedConversationPage({ params }: SharedConversationPageProps) {
  const resolved = await params;
  return <SharedConversationClient token={resolved.token} />;
}

