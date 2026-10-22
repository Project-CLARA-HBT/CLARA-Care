/**
 * Separate Control Plane Admin Design Tokens.
 *
 * Tailored for operational density, high contrast, and accessible governance.
 */

export const ADMIN_TOKENS = {
  colors: {
    bg: "#020617", // slate-950
    surface: "#0f172a", // slate-900
    border: "#1e293b", // slate-800
    brand: "#0284c7", // sky-600
    brandHover: "#0369a1", // sky-700
    textPrimary: "#f8fafc",
    textSecondary: "#94a3b8",
    statusHealthy: "#10b981", // emerald-500
    statusWarning: "#f59e0b", // amber-500
    statusDanger: "#ef4444", // red-500
  },
  typography: {
    fontMono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  },
  spacing: {
    sidebarWidth: "260px",
    headerHeight: "64px",
  },
} as const;
