import { createRef } from "react";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  ChromeSurface,
  Surface,
  type ChromeSurfaceBlur,
  type ChromeSurfaceBorder,
  type ChromeSurfaceElevation,
  type ChromeSurfaceVariant,
} from "./chrome-surface";

const here = dirname(fileURLToPath(import.meta.url));
const tokensCssPath = resolve(here, "..", "..", "styles", "tokens.css");

afterEach(cleanup);

describe("ChromeSurface primitive", () => {
  describe("Variant presets and defaults", () => {
    it("renders default variant ('header') with expected tokenized attributes and classes", () => {
      render(<ChromeSurface data-testid="surface">Header Content</ChromeSurface>);
      const el = screen.getByTestId("surface");

      expect(el).toHaveAttribute("data-chrome-surface", "true");
      expect(el).toHaveAttribute("data-variant", "header");
      expect(el).toHaveAttribute("data-blur", "medium");
      expect(el).toHaveAttribute("data-border", "subtle");
      expect(el).toHaveAttribute("data-elevation", "raised");
      expect(el.className).toContain("chrome-surface");
      expect(el.className).toContain("bg-[var(--glass-bg-header");
      expect(el.className).toContain("backdrop-blur-md");
      expect(el).toHaveTextContent("Header Content");
    });

    it("renders 'navbar' variant with high blur, subtle border, and floating elevation", () => {
      render(
        <ChromeSurface variant="navbar" data-testid="navbar-surface">
          Dock
        </ChromeSurface>
      );
      const el = screen.getByTestId("navbar-surface");

      expect(el).toHaveAttribute("data-variant", "navbar");
      expect(el).toHaveAttribute("data-blur", "high");
      expect(el).toHaveAttribute("data-border", "subtle");
      expect(el).toHaveAttribute("data-elevation", "floating");
      expect(el.className).toContain("bg-[var(--glass-bg-navbar");
      expect(el.className).toContain("backdrop-blur-xl");
    });

    it("renders 'sheet' variant with medium blur and overlay elevation", () => {
      render(
        <ChromeSurface variant="sheet" data-testid="sheet-surface">
          Drawer
        </ChromeSurface>
      );
      const el = screen.getByTestId("sheet-surface");

      expect(el).toHaveAttribute("data-variant", "sheet");
      expect(el).toHaveAttribute("data-blur", "medium");
      expect(el).toHaveAttribute("data-border", "subtle");
      expect(el).toHaveAttribute("data-elevation", "overlay");
      expect(el.className).toContain("bg-[var(--glass-bg-sheet");
    });

    it("renders 'menu' variant with medium blur and overlay elevation", () => {
      render(
        <ChromeSurface variant="menu" data-testid="menu-surface">
          Menu
        </ChromeSurface>
      );
      const el = screen.getByTestId("menu-surface");

      expect(el).toHaveAttribute("data-variant", "menu");
      expect(el).toHaveAttribute("data-blur", "medium");
      expect(el).toHaveAttribute("data-elevation", "overlay");
      expect(el.className).toContain("bg-[var(--glass-bg-menu");
    });

    it("renders 'popover' variant with medium blur and floating elevation", () => {
      render(
        <ChromeSurface variant="popover" data-testid="popover-surface">
          Popover
        </ChromeSurface>
      );
      const el = screen.getByTestId("popover-surface");

      expect(el).toHaveAttribute("data-variant", "popover");
      expect(el).toHaveAttribute("data-blur", "medium");
      expect(el).toHaveAttribute("data-elevation", "floating");
      expect(el.className).toContain("bg-[var(--glass-bg-menu");
    });

    it("renders 'banner' variant with subtle blur and flat elevation", () => {
      render(
        <ChromeSurface variant="banner" data-testid="banner-surface">
          Banner
        </ChromeSurface>
      );
      const el = screen.getByTestId("banner-surface");

      expect(el).toHaveAttribute("data-variant", "banner");
      expect(el).toHaveAttribute("data-blur", "subtle");
      expect(el).toHaveAttribute("data-elevation", "flat");
      expect(el.className).toContain("backdrop-blur-sm");
    });

    it("renders 'opaque' variant with no blur, default border, and flat elevation", () => {
      render(
        <ChromeSurface variant="opaque" data-testid="opaque-surface">
          Clinical Note
        </ChromeSurface>
      );
      const el = screen.getByTestId("opaque-surface");

      expect(el).toHaveAttribute("data-variant", "opaque");
      expect(el).toHaveAttribute("data-blur", "none");
      expect(el).toHaveAttribute("data-border", "default");
      expect(el).toHaveAttribute("data-elevation", "flat");
      expect(el.className).toContain("bg-[var(--surface-panel");
      expect(el.className).toContain("backdrop-blur-none");
    });

    it("supports legacy material alias 'navigation' -> 'navbar'", () => {
      render(
        <ChromeSurface material="navigation" data-testid="material-nav">
          Legacy Nav
        </ChromeSurface>
      );
      const el = screen.getByTestId("material-nav");

      expect(el).toHaveAttribute("data-variant", "navbar");
      expect(el).toHaveAttribute("data-elevation", "floating");
    });
  });

  describe("Opaque Surface Contract (Medical records, clinical notes, tables, charts, forms)", () => {
    it("strictly forces blur to 'none' for opaque variant even if blur prop is passed", () => {
      render(
        <ChromeSurface
          variant="opaque"
          blur="high"
          data-testid="forced-opaque-record"
        >
          Medical Record Content
        </ChromeSurface>
      );
      const el = screen.getByTestId("forced-opaque-record");

      expect(el).toHaveAttribute("data-variant", "opaque");
      expect(el).toHaveAttribute("data-blur", "none");
      expect(el.className).toContain("backdrop-blur-none");
      expect(el.className).not.toContain("backdrop-blur-xl");
      expect(el.className).toContain("bg-[var(--surface-panel");
    });

    it("Surface helper component strictly enforces opaque background and no blur", () => {
      render(
        <Surface data-testid="clinical-surface-helper">
          <h3>Kết quả xét nghiệm máu</h3>
          <p>Glucose: 5.4 mmol/L</p>
        </Surface>
      );
      const el = screen.getByTestId("clinical-surface-helper");

      expect(el).toHaveAttribute("data-variant", "opaque");
      expect(el).toHaveAttribute("data-blur", "none");
      expect(el.className).toContain("bg-[var(--surface-panel");
      expect(el.className).toContain("backdrop-blur-none");
    });

    it("Surface helper component adds interactive hover classes when interactive is true", () => {
      render(
        <Surface interactive data-testid="interactive-card">
          Interactive Medical Card
        </Surface>
      );
      const el = screen.getByTestId("interactive-card");

      expect(el).toHaveAttribute("data-variant", "opaque");
      expect(el).toHaveAttribute("data-blur", "none");
      expect(el.className).toContain("hover:bg-[var(--surface-muted)]");
      expect(el.className).toContain("transition-colors");
    });
  });

  describe("Prop Customization & Polymorphic Rendering", () => {
    it("allows customizing blur, border, and elevation on glass chrome variants", () => {
      render(
        <ChromeSurface
          variant="header"
          blur="subtle"
          border="strong"
          elevation="floating"
          data-testid="customized-header"
        >
          Custom Header
        </ChromeSurface>
      );
      const el = screen.getByTestId("customized-header");

      expect(el).toHaveAttribute("data-blur", "subtle");
      expect(el).toHaveAttribute("data-border", "strong");
      expect(el).toHaveAttribute("data-elevation", "floating");
      expect(el.className).toContain("backdrop-blur-sm");
      expect(el.className).toContain("border-[color:var(--shell-border-strong");
      expect(el.className).toContain("shadow-[var(--shadow-float");
    });

    it("merges custom className without dropping base utility classes", () => {
      render(
        <ChromeSurface
          variant="navbar"
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 p-2"
          data-testid="custom-class-nav"
        >
          Dock Item
        </ChromeSurface>
      );
      const el = screen.getByTestId("custom-class-nav");

      expect(el.className).toContain("chrome-surface");
      expect(el.className).toContain("fixed");
      expect(el.className).toContain("bottom-4");
      expect(el.className).toContain("z-50");
      expect(el.className).toContain("p-2");
    });

    it("renders as different HTML semantic tags via the 'as' prop", () => {
      const { rerender } = render(
        <ChromeSurface as="header" variant="header" data-testid="as-element">
          Header
        </ChromeSurface>
      );
      let el = screen.getByTestId("as-element");
      expect(el.tagName).toBe("HEADER");

      rerender(
        <ChromeSurface as="nav" variant="navbar" data-testid="as-element">
          Nav
        </ChromeSurface>
      );
      el = screen.getByTestId("as-element");
      expect(el.tagName).toBe("NAV");

      rerender(
        <ChromeSurface as="aside" variant="sheet" data-testid="as-element">
          Aside Sheet
        </ChromeSurface>
      );
      el = screen.getByTestId("as-element");
      expect(el.tagName).toBe("ASIDE");

      rerender(
        <ChromeSurface as="section" variant="opaque" data-testid="as-element">
          Section
        </ChromeSurface>
      );
      el = screen.getByTestId("as-element");
      expect(el.tagName).toBe("SECTION");
    });

    it("forwards ref to the underlying DOM node", () => {
      const ref = createRef<HTMLDivElement>();
      render(
        <ChromeSurface ref={ref} data-testid="ref-target">
          Ref Element
        </ChromeSurface>
      );

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
      expect(ref.current).toHaveAttribute("data-chrome-surface", "true");
    });

    it("forwards standard HTML and accessibility attributes", () => {
      render(
        <ChromeSurface
          as="nav"
          variant="navbar"
          aria-label="Thanh điều hướng chính"
          role="navigation"
          id="main-floating-dock"
          data-testid="a11y-nav"
        >
          Links
        </ChromeSurface>
      );
      const el = screen.getByTestId("a11y-nav");

      expect(el).toHaveAttribute("aria-label", "Thanh điều hướng chính");
      expect(el).toHaveAttribute("role", "navigation");
      expect(el).toHaveAttribute("id", "main-floating-dock");
    });
  });

  describe("Design Token Layer & CSS Fallback Contract", () => {
    const tokensCss = readFileSync(tokensCssPath, "utf8");

    it("tokens.css defines all required semantic glass tokens", () => {
      const requiredTokens = [
        "--glass-bg-header",
        "--glass-bg-navbar",
        "--glass-bg-sheet",
        "--glass-bg-menu",
        "--glass-border-subtle",
        "--glass-blur-header",
        "--glass-blur-navbar",
      ];

      for (const token of requiredTokens) {
        expect(tokensCss, `tokens.css must declare ${token}`).toContain(`${token}:`);
      }
    });

    it("tokens.css specifies CSS fallback for prefers-reduced-transparency: reduce", () => {
      expect(tokensCss).toContain("@media (prefers-reduced-transparency: reduce)");
      const reducedTransparencyBlock = tokensCss.split("@media (prefers-reduced-transparency: reduce)")[1];
      expect(reducedTransparencyBlock).toContain(".chrome-surface");
      expect(reducedTransparencyBlock).toContain("background-color: var(--surface-panel");
      expect(reducedTransparencyBlock).toContain("backdrop-filter: none");
    });

    it("tokens.css specifies CSS fallback for unsupported backdrop-filter", () => {
      expect(tokensCss).toContain("@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))");
      const unsupportedBlock = tokensCss.split("@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))")[1];
      expect(unsupportedBlock).toContain(".chrome-surface");
      expect(unsupportedBlock).toContain("background-color: var(--surface-panel");
      expect(unsupportedBlock).toContain("backdrop-filter: none");
    });
  });
});
