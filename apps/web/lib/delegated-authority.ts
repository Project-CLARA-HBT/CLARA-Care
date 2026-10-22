/**
 * Delegated & Family Authority Restriction Policy (PDPD Vietnam & Civil Code).
 *
 * Enforces:
 * 1. Minors (< 18) require parent or legal guardian for medical consent.
 * 2. Adult patients retain sole consent authority unless formal legal guardianship is active.
 * 3. Family proxies cannot sign medical disclaimers or request data export on behalf of adult users.
 */

export type AuthorityRelationship = "self" | "parent" | "legal_guardian" | "proxy";

export interface AuthorityContext {
  relationship: AuthorityRelationship;
  patientAge: number;
  hasSharingConsent: boolean;
  legalDocumentationVerified?: boolean;
}

export function canSignMedicalConsent(context: AuthorityContext): boolean {
  if (context.relationship === "self" && context.patientAge >= 18) {
    return true;
  }
  if (context.patientAge < 18) {
    return context.relationship === "parent" || context.relationship === "legal_guardian";
  }
  if (context.relationship === "legal_guardian" && context.legalDocumentationVerified) {
    return true;
  }
  return false;
}

export function canViewPatientPhr(context: AuthorityContext): boolean {
  if (context.relationship === "self") {
    return true;
  }
  if (context.patientAge < 18 && (context.relationship === "parent" || context.relationship === "legal_guardian")) {
    return true;
  }
  return context.hasSharingConsent;
}

export function canExportDsarData(context: AuthorityContext): boolean {
  if (context.relationship === "self" && context.patientAge >= 18) {
    return true;
  }
  if (context.patientAge < 18 && (context.relationship === "parent" || context.relationship === "legal_guardian")) {
    return true;
  }
  return false;
}
