import { notFound } from "next/navigation";

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
  if (!isWelcomeStepId(step)) notFound();
  return <WelcomeStepClient step={step} />;
}
