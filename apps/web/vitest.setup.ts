import "@testing-library/jest-dom/vitest";

/**
 * Web Storage polyfill.
 *
 * jsdom only exposes `window.localStorage` / `window.sessionStorage` for
 * non-opaque origins, and under this Vitest jsdom environment they are absent.
 * Component tests (e.g. the AI Transparency Notice gate) read/write the UI
 * language preference through these APIs, so we install a minimal in-memory
 * implementation when one is missing. This keeps tests deterministic without
 * touching production code paths.
 */
function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? (store.get(key) as string) : null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  } as Storage;
}

for (const name of ["localStorage", "sessionStorage"] as const) {
  let usable = false;
  try {
    usable = typeof window !== "undefined" && window[name] != null;
    if (usable) {
      // Touch the API to surface opaque-origin SecurityErrors.
      window[name].getItem("__probe__");
    }
  } catch {
    usable = false;
  }
  if (!usable) {
    Object.defineProperty(window, name, {
      configurable: true,
      writable: true,
      value: createMemoryStorage(),
    });
  }
}
