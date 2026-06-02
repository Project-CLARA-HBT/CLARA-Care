"use client";

export type UILanguage = "vi" | "en";

export const UI_LANGUAGE_STORAGE_KEY = "clara_ui_language";
const UI_LANGUAGE_CHANGE_EVENT = "clara:ui-language-change";

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

export function getStoredUILanguage(): UILanguage {
  if (typeof window === "undefined") return "vi";
  try {
    return normalizeLanguage(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY));
  } catch {
    return "vi";
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
  applyDocumentLanguage(language);
  return language;
}
