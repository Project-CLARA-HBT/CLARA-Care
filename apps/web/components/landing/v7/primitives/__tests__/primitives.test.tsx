import React, { createRef } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MotionProvider } from "../../runtime/motion-provider";
import {
  LandingScene,
  SceneHeader,
  StickyStage,
  SpatialStage,
  AmbientField,
  ArtworkLayer,
  ProductSurface,
  FloatingChrome,
  Reveal,
} from "../index";

function renderWithMotion(ui: React.ReactElement) {
  return render(<MotionProvider>{ui}</MotionProvider>);
}

describe("CLARA Landing v7 Primitives", () => {
  describe("LandingScene", () => {
    it("renders with default props and attributes", () => {
      const ref = createRef<HTMLElement>();
      const { container } = renderWithMotion(
        <LandingScene ref={ref} id="test-scene">
          <div>Scene Content</div>
        </LandingScene>
      );

      const section = container.querySelector("#test-scene");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "test-scene");
      expect(section).toHaveAttribute("data-scene-scale", "standard");
      expect(section).toHaveAttribute("data-scene-tone", "canvas");
      expect(screen.getByText("Scene Content")).toBeInTheDocument();
    });

    it("applies scales and tones correctly", () => {
      const { container } = renderWithMotion(
        <LandingScene id="signature-scene" scale="signature" tone="azure" sticky>
          <div>Signature Content</div>
        </LandingScene>
      );

      const section = container.querySelector("#signature-scene");
      expect(section).toHaveAttribute("data-scene-scale", "signature");
      expect(section).toHaveAttribute("data-scene-tone", "azure");
      expect(section?.className).toContain("clara-ambient-azure");
    });
  });

  describe("SceneHeader", () => {
    it("renders title, eyebrow, badge, and description", () => {
      render(
        <SceneHeader
          eyebrow="TỔNG QUAN"
          badge="Live Safety"
          title="Tiêu chuẩn an toàn"
          accent="hàng đầu"
          description="Hệ thống đa tầng bảo vệ người dùng."
          align="center"
          tone="mint"
          asH1={true}
        />
      );

      expect(screen.getByText("TỔNG QUAN")).toBeInTheDocument();
      expect(screen.getByText("Live Safety")).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Tiêu chuẩn an toàn hàng đầu");
      expect(screen.getByText("Hệ thống đa tầng bảo vệ người dùng.")).toBeInTheDocument();
    });

    it("renders split alignment correctly", () => {
      const { container } = render(
        <SceneHeader
          title="Đơn giản hóa"
          align="split"
          description="Mô tả phân tách hai bên"
        />
      );

      expect(container.firstChild).toHaveClass("md:flex-row");
    });
  });

  describe("StickyStage", () => {
    it("renders function child with progress", () => {
      const { container } = renderWithMotion(
        <StickyStage id="sticky-test" stageHeightMultiplier={3.0}>
          {(p) => <div>Progress is {p}</div>}
        </StickyStage>
      );

      const stage = container.querySelector("#sticky-test");
      expect(stage).toBeInTheDocument();
      expect(screen.getByText(/Progress is/)).toBeInTheDocument();
    });

    it("renders static node child", () => {
      renderWithMotion(
        <StickyStage id="sticky-static">
          <div data-testid="static-content">Static Stage</div>
        </StickyStage>
      );

      expect(screen.getByTestId("static-content")).toBeInTheDocument();
    });
  });

  describe("SpatialStage", () => {
    it("renders children with spatial-stage class and supports ref", () => {
      const ref = createRef<HTMLDivElement>();
      const { container } = renderWithMotion(
        <SpatialStage ref={ref} enablePointerTilt>
          <div>3D Content</div>
        </SpatialStage>
      );

      expect(container.querySelector(".clara-spatial-stage")).toBeInTheDocument();
      expect(screen.getByText("3D Content")).toBeInTheDocument();
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe("AmbientField", () => {
    it("renders all tone variants", () => {
      const tones = ["azure", "mint", "iris", "multi"] as const;
      for (const tone of tones) {
        const { container } = render(<AmbientField tone={tone} />);
        const field = container.querySelector(`[data-ambient-tone="${tone}"]`);
        expect(field).toBeInTheDocument();
        expect(field?.className).toContain(`clara-ambient-${tone}`);
      }
    });
  });

  describe("ArtworkLayer", () => {
    it("renders with depth planes Z0, Z1, Z2, Z3", () => {
      const planes = ["Z0", "Z1", "Z2", "Z3"] as const;
      for (const plane of planes) {
        const { container } = render(
          <ArtworkLayer depthPlane={plane}>
            <div>Plane {plane}</div>
          </ArtworkLayer>
        );

        const el = container.querySelector(`[data-depth-plane="${plane}"]`);
        expect(el).toBeInTheDocument();
        expect(screen.getByText(`Plane ${plane}`)).toBeInTheDocument();
      }
    });
  });

  describe("ProductSurface", () => {
    it("renders with elevation variants", () => {
      const elevations = ["flat", "low", "floating"] as const;
      for (const elevation of elevations) {
        const { container } = render(
          <ProductSurface elevation={elevation}>
            <div>Surface {elevation}</div>
          </ProductSurface>
        );

        const surface = container.querySelector(`[data-elevation="${elevation}"]`);
        expect(surface).toBeInTheDocument();
        expect(surface?.className).toContain("clara-product-surface");
      }
    });
  });

  describe("FloatingChrome", () => {
    it("renders liquid glass chrome container", () => {
      const { container } = render(
        <FloatingChrome className="custom-test">
          <span>Badge</span>
        </FloatingChrome>
      );

      const chrome = container.querySelector(".clara-floating-chrome");
      expect(chrome).toBeInTheDocument();
      expect(chrome).toHaveClass("custom-test");
      expect(screen.getByText("Badge")).toBeInTheDocument();
    });
  });

  describe("Reveal", () => {
    it("renders with directions up, fade, and scale", () => {
      const directions = ["up", "fade", "scale"] as const;
      for (const dir of directions) {
        const { container } = renderWithMotion(
          <Reveal direction={dir} delayMs={150}>
            <div>Revealed {dir}</div>
          </Reveal>
        );

        const el = container.querySelector(`[data-reveal-direction="${dir}"]`);
        expect(el).toBeInTheDocument();
        expect(screen.getByText(`Revealed ${dir}`)).toBeInTheDocument();
      }
    });
  });
});
