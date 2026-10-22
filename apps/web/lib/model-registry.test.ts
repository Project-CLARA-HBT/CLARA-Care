import { describe, expect, it } from "vitest";
import { ModelRegistryClient } from "./model-registry";

describe("ModelRegistryClient Provider Identity Binding", () => {
  it("resolves approved DeepSeek models with appropriate attestation requirements", () => {
    const model = ModelRegistryClient.getModel("deepseek-reasoner");
    expect(model).toBeDefined();
    expect(model?.provider).toBe("deepseek");
    expect(model?.minAttestationLevel).toBe("PROVIDER_RECEIPT_VERIFIED");
  });

  it("validates approved model for specific clinical task family", () => {
    expect(
      ModelRegistryClient.validateModelForTask("deepseek-reasoner", "clinical_reasoning")
    ).toBe(true);

    expect(
      ModelRegistryClient.validateModelForTask("deepseek-chat", "clinical_reasoning")
    ).toBe(false);
  });

  it("rejects unauthorized third-party model identifiers", () => {
    expect(ModelRegistryClient.isModelApproved("unapproved-third-party-llm")).toBe(false);
    expect(ModelRegistryClient.getModel("gpt-4o")).toBeNull();
  });
});
