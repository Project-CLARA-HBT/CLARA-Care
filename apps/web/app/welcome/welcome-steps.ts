import {
  WELCOME_STEP_IDS,
  isGuidedFlowStep,
} from "@/lib/guided-flow-registry";

export type WelcomeStepId = (typeof WELCOME_STEP_IDS)[number];

export function isWelcomeStepId(value: string): value is WelcomeStepId {
  return isGuidedFlowStep("welcome", value);
}

export { WELCOME_STEP_IDS };
