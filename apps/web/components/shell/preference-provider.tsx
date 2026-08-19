"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applyThemePreference,
  getStoredThemePreference,
  saveThemePreference,
  type ThemePreference,
} from "@/lib/theme";
import {
  hydrateUILanguagePreference,
  onUILanguageChange,
  saveUILanguage,
  type UILanguage,
} from "@/lib/ui-language";

export type PreferenceContextValue = {
  themePreference: ThemePreference;
  setThemePreference: (theme: ThemePreference) => void;
  handleThemeChange: (theme: ThemePreference) => void;
  uiLanguage: UILanguage;
  setUiLanguage: (language: UILanguage) => void;
  handleLanguageChange: (language: UILanguage) => void;
};

export const PreferenceContext = createContext<PreferenceContextValue | null>(
  null,
);

export function PreferenceProvider({
  children,
  initialLanguage = "vi",
  initialTheme,
}: {
  children: ReactNode;
  initialLanguage?: UILanguage;
  initialTheme?: ThemePreference;
}) {
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>(
    initialTheme ?? "dark",
  );
  const [uiLanguage, setUiLanguageState] = useState<UILanguage>(initialLanguage);

  useEffect(() => {
    const storedTheme = getStoredThemePreference();
    setThemePreferenceState(storedTheme);
    applyThemePreference(storedTheme);
  }, []);

  useEffect(() => {
    const storedLang = hydrateUILanguagePreference();
    setUiLanguageState(storedLang);
  }, []);

  useEffect(() => {
    return onUILanguageChange((nextLang) => {
      setUiLanguageState(nextLang);
    });
  }, []);

  useEffect(() => {
    document.documentElement.lang = uiLanguage;
  }, [uiLanguage]);

  useEffect(() => {
    if (themePreference !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyThemePreference("system");

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }

    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, [themePreference]);

  const handleThemeChange = useCallback((nextTheme: ThemePreference) => {
    setThemePreferenceState(nextTheme);
    saveThemePreference(nextTheme);
    applyThemePreference(nextTheme);
  }, []);

  const handleLanguageChange = useCallback((nextLang: UILanguage) => {
    setUiLanguageState(nextLang);
    saveUILanguage(nextLang);
  }, []);

  const value = useMemo<PreferenceContextValue>(
    () => ({
      themePreference,
      setThemePreference: handleThemeChange,
      handleThemeChange,
      uiLanguage,
      setUiLanguage: handleLanguageChange,
      handleLanguageChange,
    }),
    [themePreference, handleThemeChange, uiLanguage, handleLanguageChange],
  );

  return (
    <PreferenceContext.Provider value={value}>
      {children}
    </PreferenceContext.Provider>
  );
}

export function usePreferences(): PreferenceContextValue {
  const context = useContext(PreferenceContext);
  if (!context) {
    throw new Error("usePreferences must be used within a PreferenceProvider");
  }
  return context;
}
