import { notFound, redirect } from "next/navigation";

import WelcomeStepClient from "./welcome-step-client";
import {
  WELCOME_STEP_IDS,
  isWelcomeStepId,
} from "../welcome-steps";

export function generateStaticParams() {
  return WELCOME_STEP_IDS.map((step) => ({ step }));
}

export default async function WelcomeStepPage({
  params,
}: {
  params: Promise<{ step: string }>;
}) {
  const { step } = await params;
  // Preserve bookmarked links from the earlier combined measurements screen.
  if (step === "body") redirect("/welcome/height");
  if (!isWelcomeStepId(step)) notFound();
  return <WelcomeStepClient step={step} />;
}
