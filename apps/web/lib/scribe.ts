import api from "@/lib/http-client";

export type ScribeSoapRequest = {
  transcript: string;
};

export type ScribeSoapRawResponse = {
  subjective?: string | Record<string, unknown>;
  objective?: string | Record<string, unknown>;
  assessment?: string | Record<string, unknown>;
  plan?: string | Record<string, unknown>;
  S?: string;
  O?: string;
  A?: string;
  P?: string;
  soap?: {
    subjective?: string;
    objective?: string;
    assessment?: string;
    plan?: string;
    S?: string;
    O?: string;
    A?: string;
    P?: string;
  };
  medical_record_note?: unknown;
  [key: string]: unknown;
};

export type SoapSections = {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
};

export type MedicalRecordNote = {
  chiefComplaint: string;
  hpi: string;
  objective: string;
  assessment: string[];
  plan: string[];
  medications: string[];
  followUp: string;
  warnings: string[];
};

function asText(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim();
}

function formatSection(value: unknown): string {
  const direct = asText(value);
  if (direct) return direct;
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";

  const record = value as Record<string, unknown>;
  const parts: string[] = [];
  for (const [key, item] of Object.entries(record)) {
    if (Array.isArray(item)) {
      const values = item.map((x) => asText(x)).filter(Boolean);
      if (values.length) parts.push(`${key}: ${values.join("; ")}`);
      continue;
    }
    if (item && typeof item === "object") {
      const nested = Object.entries(item as Record<string, unknown>)
        .map(([k, v]) => {
          const vv = asText(v);
          return vv ? `${k}=${vv}` : "";
        })
        .filter(Boolean);
      if (nested.length) parts.push(`${key}: ${nested.join(", ")}`);
      continue;
    }
    const text = asText(item);
    if (text) parts.push(`${key}: ${text}`);
  }
  return parts.join("\n");
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asText(item))
    .filter(Boolean);
}

function objectiveToText(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return formatSection(value);
  }
  const record = value as Record<string, unknown>;
  const vitals = record.vitals;
  const findings = record.findings;
  const parts: string[] = [];
  if (vitals && typeof vitals === "object" && !Array.isArray(vitals)) {
    const vitalParts = Object.entries(vitals as Record<string, unknown>)
      .map(([key, item]) => {
        const text = asText(item);
        return text ? `${key}=${text}` : "";
      })
      .filter(Boolean);
    if (vitalParts.length) parts.push(`vitals: ${vitalParts.join(", ")}`);
  }
  const findingList = toStringList(findings);
  if (findingList.length) parts.push(`findings: ${findingList.join("; ")}`);
  if (!parts.length) return formatSection(value);
  return parts.join("\n");
}

export async function createSoap(payload: ScribeSoapRequest): Promise<ScribeSoapRawResponse> {
  const response = await api.post<ScribeSoapRawResponse>("/scribe/soap", payload);
  return response.data;
}

export function normalizeSoapSections(data: ScribeSoapRawResponse): SoapSections {
  const nested = data.soap;

  return {
    subjective: formatSection(data.subjective ?? data.S ?? nested?.subjective ?? nested?.S),
    objective: formatSection(data.objective ?? data.O ?? nested?.objective ?? nested?.O),
    assessment: formatSection(data.assessment ?? data.A ?? nested?.assessment ?? nested?.A),
    plan: formatSection(data.plan ?? data.P ?? nested?.plan ?? nested?.P)
  };
}

export function normalizeMedicalRecordNote(data: ScribeSoapRawResponse): MedicalRecordNote | null {
  const payload =
    data.medical_record_note && typeof data.medical_record_note === "object" && !Array.isArray(data.medical_record_note)
      ? (data.medical_record_note as Record<string, unknown>)
      : null;
  if (!payload) return null;

  const chiefComplaint = asText(payload.chief_complaint);
  const hpi = asText(payload.hpi);
  const objective = objectiveToText(payload.objective);
  const assessment = toStringList(payload.assessment);
  const plan = toStringList(payload.plan);
  const medications = toStringList(payload.medications);
  const followUp = asText(payload.follow_up);
  const warnings = toStringList(payload.warnings);

  if (
    !chiefComplaint &&
    !hpi &&
    !objective &&
    !assessment.length &&
    !plan.length &&
    !medications.length &&
    !followUp &&
    !warnings.length
  ) {
    return null;
  }

  return {
    chiefComplaint,
    hpi,
    objective,
    assessment,
    plan,
    medications,
    followUp,
    warnings,
  };
}
