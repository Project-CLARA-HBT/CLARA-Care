import React from "react";
import { describe, it, expect, beforeAll, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MotionProvider } from "../../runtime/motion-provider";

import CouncilSceneDefault, { CouncilScene } from "../council";
import ScribeSceneDefault, { ScribeScene } from "../scribe";
import EvidenceSceneDefault, { EvidenceScene } from "../evidence";
import SafetySceneDefault, { SafetyScene } from "../safety";
import PrivacySceneDefault, { PrivacyScene } from "../privacy";

beforeAll(() => {
  class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: MockIntersectionObserver,
  });

  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe("Landing v7 Scenes (Council, Scribe, Evidence, Safety, Privacy)", () => {
  describe("1. CouncilScene (Spatial Peak 5)", () => {
    it("exports both named and default component cleanly", () => {
      expect(CouncilScene).toBeDefined();
      expect(CouncilSceneDefault).toBeDefined();
      expect(CouncilScene).toBe(CouncilSceneDefault);
    });

    it("renders Council scene with id='council', scale='signature'", () => {
      const { container } = render(
        <MotionProvider initialLanguage="vi">
          <CouncilScene />
        </MotionProvider>
      );

      const section = container.querySelector("section#council");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "council");
      expect(section).toHaveAttribute("data-scene-scale", "signature");
    });

    it("wraps both CouncilDemo and DecisionField with stage synchronization", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <CouncilScene />
        </MotionProvider>
      );

      expect(screen.getByTestId("decision-field")).toBeInTheDocument();
      expect(screen.getByTestId("council-demo")).toBeInTheDocument();

      // Check Peak 5 badge
      expect(
        screen.getByText(/ĐIỂM NHẤN 5 • HỘI CHẨN ĐA CHUYÊN KHOA/i)
      ).toBeInTheDocument();

      // Check disclaimer
      expect(
        screen.getByText(/CLARA không tự quyết định điều trị/i)
      ).toBeInTheDocument();
    });

    it("renders in English when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <CouncilScene />
        </MotionProvider>
      );

      expect(
        screen.getByText(/PEAK 5 • MULTIDISCIPLINARY COUNCIL/i)
      ).toBeInTheDocument();
      expect(
        screen.getAllByText(/MULTIDISCIPLINARY COUNCIL/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/From Multilateral Complexity to Structured Decisions/i)
      ).toBeInTheDocument();
    });
  });

  describe("2. ScribeScene (Transformation Scene)", () => {
    it("exports both named and default component cleanly", () => {
      expect(ScribeScene).toBeDefined();
      expect(ScribeSceneDefault).toBeDefined();
      expect(ScribeScene).toBe(ScribeSceneDefault);
    });

    it("renders Scribe scene with id='scribe', scale='standard', tone='mint'", () => {
      const { container } = render(
        <MotionProvider initialLanguage="vi">
          <ScribeScene />
        </MotionProvider>
      );

      const section = container.querySelector("section#scribe");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "scribe");
      expect(section).toHaveAttribute("data-scene-tone", "mint");
    });

    it("wraps ScribeDemo and CaptureWave", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <ScribeScene />
        </MotionProvider>
      );

      expect(screen.getByTestId("scribe-demo")).toBeInTheDocument();
      expect(
        screen.getAllByText(/TRỢ LÝ GHI CHÉP Y KHOA/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/Chuyển hóa dữ liệu cuộc khám theo thời gian thực/i)
      ).toBeInTheDocument();
    });

    it("renders in English when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <ScribeScene />
        </MotionProvider>
      );

      expect(
        screen.getAllByText(/CLINICAL AMBIENT SCRIBE/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/Real-Time Encounter Transformation/i)
      ).toBeInTheDocument();
    });
  });

  describe("3. EvidenceScene (Living Evidence Hub)", () => {
    it("exports both named and default component cleanly", () => {
      expect(EvidenceScene).toBeDefined();
      expect(EvidenceSceneDefault).toBeDefined();
      expect(EvidenceScene).toBe(EvidenceSceneDefault);
    });

    it("renders Evidence scene with id='evidence', scale='standard', tone='iris'", () => {
      const { container } = render(
        <MotionProvider initialLanguage="vi">
          <EvidenceScene />
        </MotionProvider>
      );

      const section = container.querySelector("section#evidence");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "evidence");
      expect(section).toHaveAttribute("data-scene-tone", "iris");
    });

    it("wraps EvidenceDemo and SourceLens with editorial statement", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <EvidenceScene />
        </MotionProvider>
      );

      expect(screen.getByTestId("evidence-demo")).toBeInTheDocument();
      expect(screen.getByTestId("source-lens")).toBeInTheDocument();
      expect(
        screen.getAllByText(/TRUNG TÂM BẰNG CHỨNG Y VĂN/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/Không phải mọi nguồn đều có trọng lượng như nhau/i)
      ).toBeInTheDocument();
    });

    it("renders in English when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <EvidenceScene />
        </MotionProvider>
      );

      expect(
        screen.getAllByText(/LIVING EVIDENCE HUB/i).length
      ).toBeGreaterThan(0);
      expect(
        screen.getByText(/Inspect Exactly What CLARA Relies On/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Not all evidence carries equal clinical weight/i)
      ).toBeInTheDocument();
    });
  });

  describe("4. SafetyScene (Typography as Artwork — No Cards)", () => {
    it("exports both named and default component cleanly", () => {
      expect(SafetyScene).toBeDefined();
      expect(SafetySceneDefault).toBeDefined();
      expect(SafetyScene).toBe(SafetySceneDefault);
    });

    it("renders Safety scene with id='safety', scale='signature'", () => {
      const { container } = render(
        <MotionProvider initialLanguage="vi">
          <SafetyScene />
        </MotionProvider>
      );

      const section = container.querySelector("section#safety");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "safety");
    });

    it("renders all 4 principles as typography without card wrappers", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <SafetyScene />
        </MotionProvider>
      );

      expect(screen.getByText("NGUYÊN TẮC BẤT BIẾN")).toBeInTheDocument();
      expect(
        screen.getByText("An toàn là cốt lõi. Không phải tính năng phụ.")
      ).toBeInTheDocument();

      // 01 Clear sources
      expect(screen.getByText("01")).toBeInTheDocument();
      expect(screen.getByText("Nguồn trích dẫn rõ ràng")).toBeInTheDocument();
      expect(
        screen.getByText(/Mọi thông tin y khoa đều gắn liền với tài liệu tham chiếu/i)
      ).toBeInTheDocument();

      // 02 Declare uncertainty
      expect(screen.getByText("02")).toBeInTheDocument();
      expect(screen.getByText("Không che giấu điều chưa chắc chắn")).toBeInTheDocument();
      expect(
        screen.getByText(/Nếu dữ liệu không đủ để kết luận/i)
      ).toBeInTheDocument();

      // 03 Never call unvetted safe
      expect(screen.getByText("03")).toBeInTheDocument();
      expect(screen.getByText("Không gọi 'chưa kiểm tra' là 'an toàn'")).toBeInTheDocument();
      expect(
        screen.getByText(/Dữ liệu chưa qua thẩm định FIDES sẽ được gắn nhãn Chưa xác minh/i)
      ).toBeInTheDocument();

      // 04 Escalate to clinicians
      expect(screen.getByText("04")).toBeInTheDocument();
      expect(screen.getByText("Biết rõ khi nào cần chuyển giao chuyên gia")).toBeInTheDocument();
      expect(
        screen.getByText(/Nhận diện dấu hiệu cấp cứu tức thì/i)
      ).toBeInTheDocument();
    });

    it("renders English typography in English mode", () => {
      render(
        <MotionProvider initialLanguage="en">
          <SafetyScene />
        </MotionProvider>
      );

      expect(screen.getByText("NON-NEGOTIABLE SAFETY")).toBeInTheDocument();
      expect(
        screen.getByText("Safety is our core invariant. Not an afterthought.")
      ).toBeInTheDocument();
      expect(screen.getByText("Unambiguous Source Attribution")).toBeInTheDocument();
      expect(screen.getByText("Never Conceal Uncertainty")).toBeInTheDocument();
      expect(screen.getByText("Never Label 'Unchecked' as 'Safe'")).toBeInTheDocument();
      expect(screen.getByText("Know When to Escalate to Humans")).toBeInTheDocument();
    });
  });

  describe("5. PrivacyScene (Zero-CoT Privacy Boundary with PermissionGate)", () => {
    it("exports both named and default component cleanly", () => {
      expect(PrivacyScene).toBeDefined();
      expect(PrivacySceneDefault).toBeDefined();
      expect(PrivacyScene).toBe(PrivacySceneDefault);
    });

    it("renders Privacy scene with id='privacy', scale='standard'", () => {
      const { container } = render(
        <MotionProvider initialLanguage="vi">
          <PrivacyScene />
        </MotionProvider>
      );

      const section = container.querySelector("section#privacy");
      expect(section).toBeInTheDocument();
      expect(section).toHaveAttribute("data-scene-id", "privacy");
    });

    it("renders PermissionGate artwork and interactive revocation button", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <PrivacyScene />
        </MotionProvider>
      );

      expect(screen.getByTestId("permission-gate")).toBeInTheDocument();
      expect(screen.getByText("RANH GIỚI BẢO MẬT DỮ LIỆU")).toBeInTheDocument();
      expect(
        screen.getByText("Quyền kiểm soát dữ liệu hoàn toàn thuộc về bạn")
      ).toBeInTheDocument();

      // Revocation interactive toggle
      const revokeButton = screen.getByRole("button", { name: /Thu hồi quyền tức thì/i });
      expect(revokeButton).toBeInTheDocument();

      fireEvent.click(revokeButton);
      expect(
        screen.getByText(/Đã thu hồi toàn bộ quyền truy cập/i)
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Kích hoạt lại chia sẻ/i })
      ).toBeInTheDocument();
    });

    it("renders 3 privacy guarantees and English copy in English mode", () => {
      render(
        <MotionProvider initialLanguage="en">
          <PrivacyScene />
        </MotionProvider>
      );

      expect(screen.getByText("DATA PRIVACY BOUNDARY")).toBeInTheDocument();
      expect(
        screen.getByText("Complete Sovereignty Over Your Health Data")
      ).toBeInTheDocument();
      expect(screen.getByText("Zero-CoT Reasoning Isolation")).toBeInTheDocument();
      expect(screen.getAllByText("Zero Model Training").length).toBeGreaterThan(0);
      expect(screen.getByText("Sovereignty & Instant Revocation")).toBeInTheDocument();
    });
  });
});
