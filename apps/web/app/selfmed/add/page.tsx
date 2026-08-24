import { redirect } from "next/navigation";

/**
 * Historical alias (Spec v5 Section 6.31).
 * Transition directly to the canonical destination `/medicines/cabinet/add`.
 */
export default function SelfMedAddPage() {
  redirect("/medicines/cabinet/add");
}

