import { redirect } from "next/navigation";

export default function CareguardPage() {
  redirect("/medicines?tab=safety");
}
