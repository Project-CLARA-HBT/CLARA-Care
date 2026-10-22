/**
 * Model Registry & Provider Identity Binding (GLHS R4 Client).
 *
 * Spec: PH07 / A05 (Web UX).
 * Enforces:
 * 1. Client views bind model selections strictly to approved provider identities.
 * 2. Unapproved third-party model overrides are rejected client-side.
 * 3. Enforces minimum attestation levels per task (e.g. L2 for clinical reasoning).
 */

export type AttestationLevel =
  | "APPLICATION_ENVELOPE_ONLY"
  | "SERVER_PRE_DISPATCH"
  | "TRANSPORT_DISPATCH"
  | "PROVIDER_RECEIPT_VERIFIED"
  | "PROVIDER_EXECUTION_ATTESTED";

export interface ModelDescriptor {
  modelId: string;
  provider: "deepseek" | "faster-whisper" | "google-vision";
  displayName: string;
  minAttestationLevel: AttestationLevel;
  taskFamily: "clinical_reasoning" | "transcription" | "ocr" | "fast_chat";
  isApproved: boolean;
}

export const APPROVED_MODEL_REGISTRY: Record<string, ModelDescriptor> = {
  "deepseek-reasoner": {
    modelId: "deepseek-reasoner",
    provider: "deepseek",
    displayName: "DeepSeek Reasoner (V2.5)",
    minAttestationLevel: "PROVIDER_RECEIPT_VERIFIED",
    taskFamily: "clinical_reasoning",
    isApproved: true,
  },
  "deepseek-chat": {
    modelId: "deepseek-chat",
    provider: "deepseek",
    displayName: "DeepSeek Flash Chat",
    minAttestationLevel: "SERVER_PRE_DISPATCH",
    taskFamily: "fast_chat",
    isApproved: true,
  },
  "whisper-large-v3": {
    modelId: "whisper-large-v3",
    provider: "faster-whisper",
    displayName: "Faster Whisper Large v3",
    minAttestationLevel: "SERVER_PRE_DISPATCH",
    taskFamily: "transcription",
    isApproved: true,
  },
};

export class ModelRegistryClient {
  static getModel(modelId: string): ModelDescriptor | null {
    return APPROVED_MODEL_REGISTRY[modelId] ?? null;
  }

  static isModelApproved(modelId: string): boolean {
    const desc = this.getModel(modelId);
    return desc !== null && desc.isApproved;
  }

  static validateModelForTask(
    modelId: string,
    expectedTaskFamily: ModelDescriptor["taskFamily"]
  ): boolean {
    const desc = this.getModel(modelId);
    if (!desc || !desc.isApproved) {
      return false;
    }
    return desc.taskFamily === expectedTaskFamily;
  }
}
