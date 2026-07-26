import { redirect } from "next/navigation";

export default function SelfMedDdiPage() {
  redirect("/medicines?tab=safety");
}
