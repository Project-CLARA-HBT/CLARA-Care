import type { ReactNode } from "react";
import { ConsumerLayout } from "@/components/shell/consumer-layout";

export default function ConsumerRouteLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <ConsumerLayout>{children}</ConsumerLayout>;
}
