import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PreferenceProvider, usePreferences } from "./preference-provider";
import * as themeLib from "@/lib/theme";
import * as langLib from "@/lib/ui-language";

function PreferenceConsumer() {
  const {
    themePreference,
    handleThemeChange,
    uiLanguage,
    handleLanguageChange,
  } = usePreferences();

  return (
    <div>
      <span data-testid="theme">{themePreference}</span>
      <span data-testid="lang">{uiLanguage}</span>
      <button onClick={() => handleThemeChange("light")}>Set Light</button>
      <button onClick={() => handleThemeChange("dark")}>Set Dark</button>
      <button onClick={() => handleThemeChange("system")}>Set System</button>
      <button onClick={() => handleLanguageChange("en")}>Set EN</button>
      <button onClick={() => handleLanguageChange("vi")}>Set VI</button>
    </div>
  );
}

describe("PreferenceProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    document.documentElement.lang = "vi";
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        media: "(prefers-color-scheme: dark)",
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    );
  });

  it("provides initial language and theme preferences", () => {
    render(
      <PreferenceProvider initialLanguage="vi" initialTheme="dark">
        <PreferenceConsumer />
      </PreferenceProvider>,
    );

    expect(screen.getByTestId("theme")).toHaveTextContent("dark");
    expect(screen.getByTestId("lang")).toHaveTextContent("vi");
  });

  it("updates and persists theme changes", () => {
    const saveThemeSpy = vi.spyOn(themeLib, "saveThemePreference");
    const applyThemeSpy = vi.spyOn(themeLib, "applyThemePreference");

    render(
      <PreferenceProvider initialLanguage="vi" initialTheme="dark">
        <PreferenceConsumer />
      </PreferenceProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Set Light" }));
    expect(screen.getByTestId("theme")).toHaveTextContent("light");
    expect(saveThemeSpy).toHaveBeenCalledWith("light");
    expect(applyThemeSpy).toHaveBeenCalledWith("light");
  });

  it("updates and persists language changes and updates html lang attribute", () => {
    const saveLangSpy = vi.spyOn(langLib, "saveUILanguage");

    render(
      <PreferenceProvider initialLanguage="vi" initialTheme="dark">
        <PreferenceConsumer />
      </PreferenceProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Set EN" }));
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
    expect(saveLangSpy).toHaveBeenCalledWith("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
