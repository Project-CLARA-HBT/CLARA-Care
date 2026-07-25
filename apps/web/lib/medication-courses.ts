import api from "@/lib/http-client";

export type MedicationCourse = {
  id: string;
  medication_name: string;
  drugbank_id: string | null;
  status: string;
  dose_text: string;
  schedule_text: string;
  truth_state: string;
};

export type DrugBankDdiResult = {
  conclusion_available: boolean;
  required_source: "drugbank";
  source_version: string;
  courses: Array<{ id: string; medication_name: string; drugbank_id: string | null }>;
  ddi_alerts: Array<{ severity?: string; message?: string; source: string }>;
  recommendation: string;
};

export async function getMedicationCourses(): Promise<MedicationCourse[]> {
  return (await api.get<MedicationCourse[]>("/medication-courses")).data;
}

export async function createMedicationCourse(input: {
  medication_name: string;
  drugbank_id?: string;
  dose_text?: string;
  schedule_text?: string;
  indication_text?: string;
}): Promise<MedicationCourse> {
  return (
    await api.post<MedicationCourse>("/medication-courses", input, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
    })
  ).data;
}

export async function checkDrugBankDdi(courseIds: string[]): Promise<DrugBankDdiResult> {
  return (
    await api.post<DrugBankDdiResult>("/medication-courses/safety/ddi", {
      course_ids: courseIds.map((id) => Number(id)),
    })
  ).data;
}
