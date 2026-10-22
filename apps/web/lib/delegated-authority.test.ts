import { describe, expect, it } from "vitest";
import {
  canExportDsarData,
  canSignMedicalConsent,
  canViewPatientPhr,
} from "./delegated-authority";

describe("Delegated & Family Authority Restriction Policy", () => {
  it("allows adult patient self-authority across all consent operations", () => {
    const adult = {
      relationship: "self" as const,
      patientAge: 25,
      hasSharingConsent: true,
    };
    expect(canSignMedicalConsent(adult)).toBe(true);
    expect(canViewPatientPhr(adult)).toBe(true);
    expect(canExportDsarData(adult)).toBe(true);
  });

  it("blocks minors from signing medical consent directly; requires parent/guardian", () => {
    const minorSelf = {
      relationship: "self" as const,
      patientAge: 16,
      hasSharingConsent: false,
    };
    expect(canSignMedicalConsent(minorSelf)).toBe(false);

    const minorParent = {
      relationship: "parent" as const,
      patientAge: 16,
      hasSharingConsent: false,
    };
    expect(canSignMedicalConsent(minorParent)).toBe(true);
    expect(canViewPatientPhr(minorParent)).toBe(true);
    expect(canExportDsarData(minorParent)).toBe(true);
  });

  it("restricts family proxies from signing consent or exporting data for adult patients", () => {
    const proxyNoConsent = {
      relationship: "proxy" as const,
      patientAge: 45,
      hasSharingConsent: false,
    };
    expect(canSignMedicalConsent(proxyNoConsent)).toBe(false);
    expect(canViewPatientPhr(proxyNoConsent)).toBe(false);
    expect(canExportDsarData(proxyNoConsent)).toBe(false);

    const proxyWithSharing = {
      relationship: "proxy" as const,
      patientAge: 45,
      hasSharingConsent: true,
    };
    expect(canSignMedicalConsent(proxyWithSharing)).toBe(false);
    expect(canViewPatientPhr(proxyWithSharing)).toBe(true);
    expect(canExportDsarData(proxyWithSharing)).toBe(false);
  });
});
