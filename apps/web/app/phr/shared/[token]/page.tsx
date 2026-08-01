import SharedPhrClient from "./shared-phr-client";

type SharedPhrPageProps = {
  params: Promise<{ token: string }>;
};

export default async function SharedPhrPage({ params }: SharedPhrPageProps) {
  const { token } = await params;
  return <SharedPhrClient token={token} />;
}
