import { redirect } from "next/navigation";

/**
 * Historical Research landing bookmark. Research execution now lives in the
 * governed Chat flow, so this route deliberately owns no second workspace,
 * state, or API surface.
 */
export default function ResearchPage() {
  redirect("/chat");
}
