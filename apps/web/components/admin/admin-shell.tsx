import { ReactNode } from "react";
import AdminCommandStrip from "./admin-command-strip";

export type AdminTabKey =
  | "overview"
  | "knowledge-sources"
  | "answer-flow"
  | "observability"
  | "product-analytics"
  | "clinical-analytics"
  | "users"
  | (string & {});

type AdminShellProps = {
  activeTab: AdminTabKey;
  title: string;
  description: string;
  children: ReactNode;
};

export function AdminShell({
  activeTab,
  title,
  description,
  children,
}: AdminShellProps) {
  return (
    <div className="space-y-4">
      <div className="sr-only">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <AdminCommandStrip activeTab={activeTab} />

      {children}
    </div>
  );
}

export default AdminShell;
