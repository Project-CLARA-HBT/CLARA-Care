import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  SeoJsonLd,
  getSeoJsonLdGraph,
  safeJsonLdStringify,
} from "../seo-json-ld";
import { LANDING_COPY_V7 } from "../landing-copy-v7";

describe("SeoJsonLd Component & Schema Serialization", () => {
  it("renders a script tag with type='application/ld+json'", () => {
    const { container } = render(<SeoJsonLd nonce="test-nonce-123" />);
    const script = container.querySelector('script[type="application/ld+json"]');

    expect(script).not.toBeNull();
    expect(script?.getAttribute("nonce")).toBe("test-nonce-123");
  });

  it("produces valid JSON-LD structure with @context and 5 @graph entities", () => {
    const graphData = getSeoJsonLdGraph();

    expect(graphData["@context"]).toBe("https://schema.org");
    expect(Array.isArray(graphData["@graph"])).toBe(true);
    expect(graphData["@graph"]).toHaveLength(5);
  });

  it("contains valid MedicalOrganization entity", () => {
    const graphData = getSeoJsonLdGraph();
    const org = graphData["@graph"].find(
      (item) =>
        Array.isArray(item["@type"])
          ? item["@type"].includes("MedicalOrganization")
          : item["@type"] === "MedicalOrganization"
    );

    expect(org).toBeDefined();
    expect(org?.["@id"]).toBe("https://theclaracare.com/#organization");
    expect(org?.name).toBe("The CLARA Care");
    expect(org?.alternateName).toEqual([
      "CLARA Care",
      "The Clara Care",
      "Trợ lý AI Y tế CLARA",
    ]);
    expect(org?.url).toBe("https://theclaracare.com");
    expect(org?.logo).toBe("https://theclaracare.com/icons/clara-logo.png");
    expect(org?.description).toBe(
      "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam, hỗ trợ tra cứu tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn đa chuyên khoa và dòng thời gian sức khỏe LifeMap."
    );
    expect(org?.medicalSpecialty).toEqual([
      "Cardiology",
      "Nephrology",
      "ClinicalPharmacology",
      "PrimaryCare",
    ]);
  });

  it("contains valid WebApplication entity", () => {
    const graphData = getSeoJsonLdGraph();
    const app = graphData["@graph"].find(
      (item) =>
        Array.isArray(item["@type"])
          ? item["@type"].includes("WebApplication")
          : item["@type"] === "WebApplication"
    );

    expect(app).toBeDefined();
    expect(app?.["@id"]).toBe("https://theclaracare.com/#software");
    expect(app?.name).toBe("CLARA Care System");
    expect(app?.applicationCategory).toBe("HealthApplication");
    expect(app?.operatingSystem).toBe("Web, iOS, Android");
    expect(app?.featureList).toEqual([
      "FIDES Safety Drug-Drug Interaction Verification",
      "Longitudinal Health Timeline LifeMap",
      "Multi-Specialty Medical Council",
      "Ambient Clinical Scribe (SOAP Notes)",
      "Living Evidence Hub (DAV, DrugBank, WHO, FDA, PubMed)",
      "Zero-CoT Banking-Grade Medical Privacy",
    ]);
    expect(app?.offers).toEqual({
      "@type": "Offer",
      price: "0",
      priceCurrency: "VND",
    });
  });

  it("contains valid WebSite entity with potential search action", () => {
    const graphData = getSeoJsonLdGraph();
    const site = graphData["@graph"].find((item) => item["@type"] === "WebSite");

    expect(site).toBeDefined();
    expect(site?.["@id"]).toBe("https://theclaracare.com/#website");
    expect(site?.url).toBe("https://theclaracare.com");
    expect(site?.name).toBe("The CLARA Care");
    expect(site?.inLanguage).toEqual(["vi-VN", "en-US"]);
    expect(site?.potentialAction).toEqual({
      "@type": "SearchAction",
      target: "https://theclaracare.com/chat?q={search_term_string}",
      "query-input": "required name=search_term_string",
    });
  });

  it("contains valid FAQPage matching the 5 canonical FAQ items from LANDING_COPY_V7.vi.faq.items", () => {
    const graphData = getSeoJsonLdGraph();
    const faq = graphData["@graph"].find((item) => item["@type"] === "FAQPage");

    expect(faq).toBeDefined();
    expect(faq?.["@id"]).toBe("https://theclaracare.com/#faq");

    const mainEntity = faq?.mainEntity as Array<{
      "@type": string;
      name: string;
      acceptedAnswer: { "@type": string; text: string };
    }>;

    expect(mainEntity).toHaveLength(5);
    expect(mainEntity).toHaveLength(LANDING_COPY_V7.vi.faq.items.length);

    LANDING_COPY_V7.vi.faq.items.forEach((item, index) => {
      expect(mainEntity[index]["@type"]).toBe("Question");
      expect(mainEntity[index].name).toBe(item.question);
      expect(mainEntity[index].acceptedAnswer["@type"]).toBe("Answer");
      expect(mainEntity[index].acceptedAnswer.text).toBe(item.answer);
    });
  });

  it("contains valid MedicalWebPage entity", () => {
    const graphData = getSeoJsonLdGraph();
    const webPage = graphData["@graph"].find(
      (item) => item["@type"] === "MedicalWebPage"
    );

    expect(webPage).toBeDefined();
    expect(webPage?.["@id"]).toBe("https://theclaracare.com/#medicalwebpage");
    expect(webPage?.about).toBe(
      "Medical Artificial Intelligence & Clinical Decision Support"
    );
    expect(webPage?.aspect).toEqual([
      "DiagnosisSupport",
      "TreatmentGuidance",
      "MedicationSafety",
    ]);
  });

  it("safely escapes HTML tags to prevent XSS in safeJsonLdStringify", () => {
    const maliciousPayload = {
      malicious: "</script><script>alert('XSS')</script>",
      html: "<img src=x onerror=alert(1)>",
      entities: "A & B",
    };

    const sanitized = safeJsonLdStringify(maliciousPayload);

    expect(sanitized).not.toContain("<");
    expect(sanitized).not.toContain(">");
    expect(sanitized).toContain("\\u003c");
    expect(sanitized).toContain("\\u003e");
    expect(sanitized).toContain("\\u0026");

    // Must be safely re-parseable into the exact original payload
    const parsed = JSON.parse(sanitized);
    expect(parsed).toEqual(maliciousPayload);
  });

  it("renders safe HTML string inside script tag when rendered as component", () => {
    const { container } = render(<SeoJsonLd />);
    const script = container.querySelector('script[type="application/ld+json"]');

    expect(script).not.toBeNull();
    const content = script?.innerHTML ?? "";
    expect(content).not.toContain("<script");
    expect(content).not.toContain("</script");

    const parsed = JSON.parse(content);
    expect(parsed["@context"]).toBe("https://schema.org");
    expect(parsed["@graph"]).toHaveLength(5);
  });
});
