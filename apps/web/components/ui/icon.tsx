import type { SVGAttributes } from "react";

/**
 * Semantic icons bundled with CLARA.
 *
 * Keep this list deliberately small: feature code chooses a meaning instead of
 * passing a font glyph name. Inline SVG avoids a flash of raw icon-name text
 * when an icon font is unavailable or late to load.
 */
export const ICON_NAMES = [
  "user-card",
  "body",
  "contact",
  "warning",
  "clinical-notes",
  "medication",
  "progress",
  "scan",
  "download",
  "share",
  "emergency",
  "notifications",
  "calendar",
  "check",
  "more",
  "arrow-right",
  "chat",
  "search",
  "folder",
  "menu",
  "send",
  "theme",
  "stop",
  "fallback",
] as const;

export type IconName = (typeof ICON_NAMES)[number];

const ICON_PATHS: Record<IconName, string> = {
  "user-card": "M15 19a6 6 0 0 0-12 0m12 0h6V5H3v14m12 0H9m3-7a3 3 0 1 0 0-6 3 3 0 0 0 0 6m5-3h2m-2 4h2",
  body: "M12 5.5a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5ZM7 8.5l3-1h4l3 1m-8 1.5v4l-1.5 8m7.5-12v4l1.5 8M10 14h4",
  contact: "M4 4h16v16H4zM8 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm-3 6c.7-1.7 1.9-2.5 3-2.5s2.3.8 3 2.5m3-6h3m-3 4h3",
  warning: "M12 3 2.5 20h19L12 3Zm0 6v5m0 3h.01",
  "clinical-notes": "M7 3h10v4h3v14H4V7h3V3Zm0 4h10V3H7v4Zm1 5h8m-8 4h5",
  medication: "m8.5 4.5 11 11a3.54 3.54 0 0 1-5 5l-11-11a3.54 3.54 0 0 1 5-5Zm.5 9 4.5-4.5",
  progress: "M12 3a9 9 0 1 0 9 9m-9-5v5l3 2m1-11h5v5",
  scan: "M4 8V4h4m8 0h4v4m0 8v4h-4M8 20H4v-4M8 9h8v6H8z",
  download: "M12 3v12m-4-4 4 4 4-4M5 20h14",
  share: "M8.5 12.5 15.5 8m-7 3.5 7 4.5M18 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  emergency: "M9 3h6v6h6v6h-6v6H9v-6H3V9h6V3Z",
  notifications: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 12h4",
  calendar: "M7 3v3m10-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Zm3 8h3m2 0h3m-8 4h3m2 0h3",
  check: "m5 12 4 4L19 6",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  "arrow-right": "M5 12h14m-5-5 5 5-5 5",
  chat: "M4 5h16v11H8l-4 4V5Zm4 4h8m-8 3h5",
  search: "m20 20-4.4-4.4M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z",
  folder: "M3 6h7l2 2h9v11H3V6Zm0 3h18",
  menu: "M4 7h16M4 12h16M4 17h16",
  send: "m4 4 16 8-16 8 3-8-3-8Zm3 8h9",
  theme: "M12 3v2m0 14v2m9-9h-2M5 12H3m15.4 6.4-1.4-1.4M7 7 5.6 5.6m12.8 0L17 7M7 17l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  stop: "M6 6h12v12H6z",
  fallback: "M4 4h16v16H4zM9.5 9a2.5 2.5 0 1 1 3.2 2.4c-.7.3-.7.9-.7 1.6m0 3h.01",
};

export type IconProps = Omit<SVGAttributes<SVGSVGElement>, "children" | "name"> & {
  name: IconName;
  /** Supply a concise label only when the icon conveys meaning by itself. */
  label?: string;
  size?: number | string;
};

export function Icon({ name, label, size = "1.25em", className = "", ...props }: IconProps) {
  const path = ICON_PATHS[name] ?? ICON_PATHS.fallback;
  const accessible = Boolean(label?.trim());

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`inline-block shrink-0 ${className}`}
      aria-hidden={accessible ? undefined : true}
      aria-label={accessible ? label : undefined}
      role={accessible ? "img" : undefined}
      focusable="false"
      data-icon={ICON_PATHS[name] ? name : "fallback"}
      {...props}
    >
      {accessible ? <title>{label}</title> : null}
      <path d={path} />
    </svg>
  );
}

export default Icon;
