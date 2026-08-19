import type { ReactNode } from "react";
import { ProfessionalLayout } from "@/components/shell/professional-layout";

export default function ProfessionalRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <ProfessionalLayout>{children}</ProfessionalLayout>;
}
