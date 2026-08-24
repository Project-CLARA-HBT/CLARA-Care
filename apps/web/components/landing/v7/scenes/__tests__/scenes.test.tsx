import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MotionProvider } from "../../runtime/motion-provider";

import HeroSceneDefault, { HeroScene } from "../hero";
import TrustSceneDefault, { TrustScene } from "../trust";
import ManifestoSceneDefault, { ManifestoScene } from "../manifesto";
import HowSceneDefault, { HowScene } from "../how";
import ChatSceneDefault, { ChatScene } from "../chat";

describe("Landing v7 Scenes (Hero, Trust, Manifesto, How, Chat)", () => {
  describe("1. HeroScene (Spatial Peak 1)", () => {
    it("exports both named and default component cleanly", () => {
      expect(HeroScene).toBeDefined();
      expect(HeroSceneDefault).toBeDefined();
      expect(HeroScene).toBe(HeroSceneDefault);
    });

    it("renders headline, CTAs, trust bullets, ClaraOrb, and floating metadata in Vietnamese", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <HeroScene />
        </MotionProvider>
      );

      expect(screen.getByText(/Hiểu rõ điều đang xảy ra/i)).toBeInTheDocument();
      expect(screen.getByText(/Biết bước tiếp theo/i)).toBeInTheDocument();
      expect(screen.getByText(/Bắt đầu hỏi CLARA/i)).toBeInTheDocument();
      expect(screen.getByText(/Xem cách hoạt động/i)).toBeInTheDocument();
      expect(screen.getByText(/Y văn Dược thư Quốc gia/i)).toBeInTheDocument();
      expect(screen.getByText(/CLARA Live Safety Stream/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Bối cảnh thuốc/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Kiểm tra FIDES/i)).toBeInTheDocument();
    });

    it("renders in English when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <HeroScene />
        </MotionProvider>
      );

      expect(screen.getByText(/Understand what is happening/i)).toBeInTheDocument();
      expect(screen.getByText(/Know what matters next/i)).toBeInTheDocument();
      expect(screen.getByText(/Start Asking CLARA/i)).toBeInTheDocument();
      expect(screen.getByText(/National Pharmacopoeia Vetted/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Medication Context/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/FIDES Verification/i)).toBeInTheDocument();
    });
  });

  describe("2. TrustScene (Source Rail Transition)", () => {
    it("exports both named and default component cleanly", () => {
      expect(TrustScene).toBeDefined();
      expect(TrustSceneDefault).toBeDefined();
      expect(TrustScene).toBe(TrustSceneDefault);
    });

    it("renders verified sources rail and EvidenceRibbon motifs", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <TrustScene />
        </MotionProvider>
      );

      expect(screen.getByText("NGUỒN MINH BẠCH")).toBeInTheDocument();
      expect(screen.getByText("Nguồn rõ ràng. Giới hạn rõ ràng.")).toBeInTheDocument();
      expect(screen.getByText("WHO")).toBeInTheDocument();
      expect(screen.getByText("FDA")).toBeInTheDocument();
      expect(screen.getByText("DrugBank 5.1")).toBeInTheDocument();
      expect(screen.getByText("DAV")).toBeInTheDocument();
    });

    it("renders English copy when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <TrustScene />
        </MotionProvider>
      );

      expect(screen.getByText("TRANSPARENT SOURCES")).toBeInTheDocument();
      expect(screen.getByText("Clear Sources. Clear Boundaries.")).toBeInTheDocument();
    });
  });

  describe("3. ManifestoScene (Context Constellation Integration)", () => {
    it("exports both named and default component cleanly", () => {
      expect(ManifestoScene).toBeDefined();
      expect(ManifestoSceneDefault).toBeDefined();
      expect(ManifestoScene).toBe(ManifestoSceneDefault);
    });

    it("renders editorial headline, constellation artwork, and resolving statement", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <ManifestoScene />
        </MotionProvider>
      );

      expect(screen.getByText("BỐI CẢNH TOÀN DIỆN")).toBeInTheDocument();
      expect(
        screen.getByText(/Một câu hỏi sức khỏe/i)
      ).toBeInTheDocument();
      expect(screen.getByTestId("context-constellation")).toBeInTheDocument();
      expect(screen.getAllByText(/Điều gì thực sự đáng chú ý lúc này\?/i).length).toBeGreaterThan(0);
    });

    it("allows interacting with nodes in the constellation", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <ManifestoScene />
        </MotionProvider>
      );

      const medButtons = screen.getAllByRole("button", { name: /Thuốc đang dùng/i });
      expect(medButtons.length).toBeGreaterThan(0);
      fireEvent.click(medButtons[0]);
      expect(screen.getByTestId("context-constellation")).toHaveAttribute(
        "data-active-node",
        "medications"
      );
    });
  });

  describe("4. HowScene (Transforming 4-Stage Pipeline)", () => {
    it("exports both named and default component cleanly", () => {
      expect(HowScene).toBeDefined();
      expect(HowSceneDefault).toBeDefined();
      expect(HowScene).toBe(HowSceneDefault);
    });

    it("renders all 4 pipeline steps and morphs the stage surface on selection", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <HowScene />
        </MotionProvider>
      );

      expect(screen.getByText("QUY TRÌNH 4 BƯỚC")).toBeInTheDocument();
      expect(screen.getByText("Cách CLARA xử lý một câu hỏi")).toBeInTheDocument();

      // Step 1 check
      expect(screen.getByText("Bạn đặt câu hỏi")).toBeInTheDocument();
      expect(screen.getByText("Tiếp nhận câu hỏi thô")).toBeInTheDocument();

      // Switch to Step 2
      const step2Btn = screen.getByText("CLARA tìm bối cảnh liên quan");
      fireEvent.click(step2Btn);
      expect(screen.getByText("Trích xuất & Khớp bối cảnh hồ sơ")).toBeInTheDocument();

      // Switch to Step 3
      const step3Btn = screen.getByText("Kiểm tra nguồn & an toàn FIDES");
      fireEvent.click(step3Btn);
      expect(screen.getByText("Chạy thẩm định FIDES & Dược thư")).toBeInTheDocument();

      // Switch to Step 4
      const step4Btn = screen.getByText("Trả lời rõ ràng & gợi ý bước tiếp");
      fireEvent.click(step4Btn);
      expect(screen.getByText("Định dạng câu trả lời & Hành động")).toBeInTheDocument();
    });

    it("renders English copy and steps in English", () => {
      render(
        <MotionProvider initialLanguage="en">
          <HowScene />
        </MotionProvider>
      );

      expect(screen.getByText("4-STEP WORKFLOW")).toBeInTheDocument();
      expect(screen.getByText("How CLARA Processes a Query")).toBeInTheDocument();
      expect(screen.getByText("You ask a question")).toBeInTheDocument();
      expect(screen.getByText("Capture User Question")).toBeInTheDocument();
    });
  });

  describe("5. ChatScene (Spatial Peak 2 Signature Surface)", () => {
    it("exports both named and default component cleanly", () => {
      expect(ChatScene).toBeDefined();
      expect(ChatSceneDefault).toBeDefined();
      expect(ChatScene).toBe(ChatSceneDefault);
    });

    it("renders scene header, ChatDemo product surface, and EvidenceRibbon motifs", () => {
      render(
        <MotionProvider initialLanguage="vi">
          <ChatScene />
        </MotionProvider>
      );

      expect(screen.getByText("TRẢI NGHIỆM TRÒ CHUYỆN")).toBeInTheDocument();
      expect(screen.getByText("Câu trả lời trước. Chi tiết khi bạn cần.")).toBeInTheDocument();
      expect(screen.getByTestId("chat-demo")).toBeInTheDocument();
      expect(screen.getByTestId("fides-safe-badge")).toBeInTheDocument();
      expect(screen.getByTestId("zero-cot-badge")).toBeInTheDocument();
      expect(screen.getByTestId("tier-1-direct-answer")).toBeInTheDocument();
      expect(screen.getByTestId("tier-2-next-action")).toBeInTheDocument();
      expect(screen.getByTestId("tier-3-uncertainty")).toBeInTheDocument();
      expect(screen.getByTestId("tier-4-sources")).toBeInTheDocument();
      expect(screen.getByTestId("tier-5-advanced-pharmacology")).toBeInTheDocument();
    });

    it("renders English copy when language is 'en'", () => {
      render(
        <MotionProvider initialLanguage="en">
          <ChatScene />
        </MotionProvider>
      );

      expect(screen.getByText("CONVERSATION EXPERIENCE")).toBeInTheDocument();
      expect(screen.getByText("Direct Answer First. Depth on Demand.")).toBeInTheDocument();
    });
  });
});
