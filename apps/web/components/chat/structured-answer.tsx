"use client";

import AnswerRenderer, {
  type AnswerRendererProps,
} from "@/app/chat/_v2/components/AnswerRenderer";

export type { AnswerRendererProps as StructuredAnswerProps };
export const StructuredAnswer = AnswerRenderer;
export default AnswerRenderer;
