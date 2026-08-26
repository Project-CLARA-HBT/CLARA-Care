import { notFound } from "next/navigation";

import { isGuidedFlowStep } from "@/lib/guided-flow-registry";

import LifeMapEpisodeStepClient, { isValidLifeMapStep } from "./step-client";

export default async function LifeMapEpisodeStepPage({
  params,
}: {
  params: Promise<{ draftId: string; step: string }>;
}) {
  const { draftId, step } = await params;
  if (!draftId || (!isGuidedFlowStep("lifemapEpisode", step) && !isValidLifeMapStep(step))) {
    notFound();
  }
  return <LifeMapEpisodeStepClient draftId={draftId} step={step} />;
}
