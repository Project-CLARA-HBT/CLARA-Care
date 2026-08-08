import type { Metadata } from "next";
import SharedPhrClient from "./shared-phr-client";

type SharedPhrPageProps = {
  params: Promise<{ token: string }>;
};

export const metadata: Metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function SharedPhrPage({ params }: SharedPhrPageProps) {
  const { token } = await params;
  return <SharedPhrClient token={token} />;
}
