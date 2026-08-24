import type { Metadata } from "next";
import SharedConversationClient from "@/app/share/[token]/shared-conversation-client";

type ChatSharePageProps = {
  params: Promise<{ token: string }>;
};

export const metadata: Metadata = {
  title: "Gói chia sẻ lâm sàng | The Clara Care",
  description: "Trình đọc gói hội thoại và hồ sơ lâm sàng được chia sẻ chỉ đọc, có chữ ký bảo mật xác thực.",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function ChatSharePage({ params }: ChatSharePageProps) {
  const resolved = await params;
  return <SharedConversationClient token={resolved.token} />;
}
