import { getNavItemsByRole, type UserRole } from "@/lib/navigation.config";

export type { UserRole };

export const roleMenus: Record<UserRole, { label: string; href: string }[]> = {
  normal: getNavItemsByRole("normal").map((item) => ({ label: item.label, href: item.href })),
  researcher: getNavItemsByRole("researcher").map((item) => ({ label: item.label, href: item.href })),
  doctor: getNavItemsByRole("doctor").map((item) => ({ label: item.label, href: item.href })),
  admin: getNavItemsByRole("admin").map((item) => ({ label: item.label, href: item.href })),
};
