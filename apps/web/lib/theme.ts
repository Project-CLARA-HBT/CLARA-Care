export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "clara-theme";
const THEME_ATTRIBUTE = "data-theme";
const THEME_QUERY = "(prefers-color-scheme: dark)";

const isThemePreference = (value: string | null): value is ThemePreference => {
  return value === "light" || value === "dark" || value === "system";
};

export const resolveTheme = (preference: ThemePreference, prefersDark: boolean): ResolvedTheme => {
  if (preference === "system") {
    return prefersDark ? "dark" : "light";
  }

  return preference;
};

export const getSystemTheme = (): ResolvedTheme => {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia(THEME_QUERY).matches ? "dark" : "light";
};

export const getStoredThemePreference = (): ThemePreference => {
  if (typeof window === "undefined") {
    return "light";
  }

  const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(raw) ? raw : "light";
};

export const saveThemePreference = (preference: ThemePreference): void => {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(THEME_STORAGE_KEY, preference);
};

export const applyThemePreference = (preference: ThemePreference): ResolvedTheme => {
  const root = document.documentElement;
  const resolvedTheme = resolveTheme(preference, getSystemTheme() === "dark");

  root.setAttribute(THEME_ATTRIBUTE, resolvedTheme);
  root.classList.toggle("dark", resolvedTheme === "dark");
  root.style.colorScheme = resolvedTheme;

  return resolvedTheme;
};

export const getThemeInitScript = (): string =>
  `(() => {
    try {
      const key = "${THEME_STORAGE_KEY}";
      const raw = window.localStorage.getItem(key);
      const preference = raw === "light" || raw === "dark" || raw === "system" ? raw : "light";
      const prefersDark = window.matchMedia("${THEME_QUERY}").matches;
      const resolved = preference === "system" ? (prefersDark ? "dark" : "light") : preference;
      const root = document.documentElement;
      root.setAttribute("${THEME_ATTRIBUTE}", resolved);
      root.classList.toggle("dark", resolved === "dark");
      root.style.colorScheme = resolved;
    } catch (_) {}
  })();`;
