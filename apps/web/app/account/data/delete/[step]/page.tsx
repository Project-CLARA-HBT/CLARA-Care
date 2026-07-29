import { Suspense } from "react";
import { notFound } from "next/navigation";

import DeleteDataFlowClient from "./delete-data-flow-client";

const DELETE_FLOW_STEPS = ["review", "confirm", "status"] as const;

export type DeleteFlowStep = (typeof DELETE_FLOW_STEPS)[number];

function isDeleteFlowStep(step: string): step is DeleteFlowStep {
  return (DELETE_FLOW_STEPS as readonly string[]).includes(step);
}

export function generateStaticParams() {
  return DELETE_FLOW_STEPS.map((step) => ({ step }));
}

export default async function DeleteDataFlowPage({
  params,
}: {
  params: Promise<{ step: string }>;
}) {
  const { step } = await params;
  if (!isDeleteFlowStep(step)) notFound();
  return (
    <Suspense fallback={null}>
      <DeleteDataFlowClient step={step} />
    </Suspense>
  );
}
