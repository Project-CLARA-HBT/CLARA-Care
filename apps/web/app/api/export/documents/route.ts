import { NextRequest, NextResponse } from "next/server";
import {
  buildFhirDocumentReference,
  isFhirEncounterExportEnabled,
  sanitizeExportFilename,
  validateRedaction,
  verifyExportConsent,
  CLARA_FHIR_ATTRIBUTION,
  CLARA_FHIR_CONFORMANCE,
  type FhirBundle,
  type FhirExportFormat,
  type FhirExportPurpose,
} from "@/lib/fhir-encounter-export";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  // 1. Feature Flag Check — fail closed if disabled
  if (!isFhirEncounterExportEnabled()) {
    return NextResponse.json(
      {
        code: "feature_disabled",
        message: "FHIR Document Export feature is currently disabled.",
      },
      { status: 404 },
    );
  }

  const { searchParams } = request.nextUrl;
  const docId = searchParams.get("id")?.trim();
  const purpose = (searchParams.get("purpose")?.trim() || "self_download") as FhirExportPurpose;
  const format = (searchParams.get("format")?.trim() || "fhir_json") as FhirExportFormat;
  const profileId = request.headers.get("x-clara-profile-context") || searchParams.get("profile_id") || undefined;

  // 2. Input Validation
  if (!docId) {
    return NextResponse.json(
      {
        code: "invalid_request",
        message: "Missing required query parameter: id",
      },
      { status: 422 },
    );
  }

  // 3. Consent Gate Verification
  const explicitConsentHeader = request.headers.get("x-clara-consent-verified");
  let consentAllowed = explicitConsentHeader === "true";

  if (!consentAllowed) {
    const consentResult = await verifyExportConsent(purpose, profileId);
    consentAllowed = consentResult.allowed;
    if (!consentAllowed) {
      return NextResponse.json(
        {
          code: "consent_required",
          message: consentResult.reason || "Active medical consent required prior to clinical document export.",
          policy_type: consentResult.policy_type || "medical_disclaimer",
        },
        { status: 403 },
      );
    }
  }

  // 4. Construct DocumentReference resource and Bundle
  const docRef = buildFhirDocumentReference(
    {
      id: docId,
      title: `Clinical Document #${docId}`,
      media_type: "text/plain",
      text_content: `Clinical Summary Record #${docId}`,
      created_at: new Date().toISOString(),
    },
    undefined,
    profileId,
  );

  const now = new Date().toISOString();
  const bundle: FhirBundle = {
    resourceType: "Bundle",
    id: `clara-document-${docId}`,
    meta: {
      lastUpdated: now,
      profile: ["http://hl7.org/fhir/StructureDefinition/Bundle"],
      attribution: CLARA_FHIR_ATTRIBUTION,
      conformance: CLARA_FHIR_CONFORMANCE,
    },
    type: "collection",
    timestamp: now,
    entry: [
      {
        fullUrl: `urn:uuid:${docRef.id}`,
        resource: docRef,
      },
    ],
  };

  // 5. Redaction and Safety Inspection
  const redaction = validateRedaction(bundle);
  if (!redaction.safe) {
    return NextResponse.json(
      {
        code: "safety_gate_violation",
        message: "Redaction check failed.",
        findings: redaction.findings,
      },
      { status: 500 },
    );
  }

  // 6. Format and Stream Payload
  const filename = sanitizeExportFilename(
    `clara-doc-${docId}`,
    format === "ndjson" ? "ndjson" : "fhir.json",
  );

  let responseBody: string;
  let contentType = "application/fhir+json; charset=utf-8";

  if (format === "ndjson") {
    contentType = "application/x-ndjson; charset=utf-8";
    responseBody = bundle.entry.map((e) => JSON.stringify(e.resource)).join("\n");
  } else {
    responseBody = JSON.stringify(bundle, null, 2);
  }

  return new NextResponse(responseBody, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
      "X-CLARA-FHIR-Version": "4.0.1",
      "X-CLARA-Conformance": "fhir-r4-summary-not-ips",
    },
  });
}
