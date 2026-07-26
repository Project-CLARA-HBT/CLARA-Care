import { redirect } from "next/navigation";

export default function SelfMedPage() {
  redirect("/medicines?tab=cabinet");
}
