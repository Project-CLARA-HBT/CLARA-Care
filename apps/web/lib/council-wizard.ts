import { CouncilCaseDraft } from "@/lib/council";

export type SpecialistOption = {
  id: string;
  label: string;
};

export const SPECIALIST_OPTIONS: SpecialistOption[] = [
  { id: "cardiology", label: "Tim mạch" },
  { id: "neurology", label: "Thần kinh" },
  { id: "endocrinology", label: "Nội tiết" },
  { id: "pharmacology", label: "Dược lâm sàng" },
  { id: "nephrology", label: "Thận học" },
];

export const DEFAULT_DRAFT: CouncilCaseDraft = {
  symptomsInput: "",
  labsInput: "",
  medicationsInput: "",
  historyInput: "",
  specialistCount: 3,
  selectedSpecialists: SPECIALIST_OPTIONS.slice(0, 3).map((item) => item.id),
};

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function normalizeDraft(input: CouncilCaseDraft): CouncilCaseDraft {
  const normalizedCount = clamp(input.specialistCount || 3, 2, SPECIALIST_OPTIONS.length);
  const selected = (input.selectedSpecialists || []).filter((id) =>
    SPECIALIST_OPTIONS.some((item) => item.id === id)
  );
  return {
    ...input,
    specialistCount: normalizedCount,
    selectedSpecialists: selected.slice(0, normalizedCount),
  };
}
