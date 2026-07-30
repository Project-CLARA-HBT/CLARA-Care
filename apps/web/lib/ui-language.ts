"use client";

export type UILanguage = "vi" | "en";

export const UI_LANGUAGE_STORAGE_KEY = "clara_ui_language";
export const UI_LANGUAGE_COOKIE_NAME = "clara_ui_language";
const UI_LANGUAGE_CHANGE_EVENT = "clara:ui-language-change";
const UI_LANGUAGE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

function normalizeLanguage(value: unknown): UILanguage {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase();
  return raw === "en" ? "en" : "vi";
}

function applyDocumentLanguage(language: UILanguage) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language;
}

function getCookieLanguage(): UILanguage {
  if (typeof document === "undefined") return "vi";
  try {
    const encoded = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${UI_LANGUAGE_COOKIE_NAME}=`))
      ?.slice(UI_LANGUAGE_COOKIE_NAME.length + 1);
    return normalizeLanguage(encoded ? decodeURIComponent(encoded) : null);
  } catch {
    return "vi";
  }
}

function saveCookieLanguage(language: UILanguage) {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = [
    `${UI_LANGUAGE_COOKIE_NAME}=${encodeURIComponent(language)}`,
    "Path=/",
    `Max-Age=${UI_LANGUAGE_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
    secure.trim(),
  ]
    .filter(Boolean)
    .join("; ");
}

export function getStoredUILanguage(): UILanguage {
  if (typeof window === "undefined") return "vi";
  try {
    const stored = window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
    return stored === null ? getCookieLanguage() : normalizeLanguage(stored);
  } catch {
    return getCookieLanguage();
  }
}

export function saveUILanguage(language: UILanguage) {
  if (typeof window === "undefined") return;
  const normalized = normalizeLanguage(language);
  try {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, normalized);
  } catch {
    // noop
  }
  saveCookieLanguage(normalized);
  applyDocumentLanguage(normalized);
  window.dispatchEvent(new CustomEvent<UILanguage>(UI_LANGUAGE_CHANGE_EVENT, { detail: normalized }));
}

export function onUILanguageChange(listener: (language: UILanguage) => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const onCustomEvent = (event: Event) => {
    const detail = (event as CustomEvent<UILanguage>).detail;
    listener(normalizeLanguage(detail));
  };

  const onStorage = (event: StorageEvent) => {
    if (event.key !== UI_LANGUAGE_STORAGE_KEY) return;
    listener(normalizeLanguage(event.newValue));
  };

  window.addEventListener(UI_LANGUAGE_CHANGE_EVENT, onCustomEvent);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(UI_LANGUAGE_CHANGE_EVENT, onCustomEvent);
    window.removeEventListener("storage", onStorage);
  };
}

export function hydrateUILanguagePreference(): UILanguage {
  const language = getStoredUILanguage();
  // Carry an existing local-storage preference into the server-readable
  // cookie on the first visit after the locale persistence migration.
  saveCookieLanguage(language);
  applyDocumentLanguage(language);
  return language;
}
