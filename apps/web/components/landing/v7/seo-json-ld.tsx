import React from "react";
import { LANDING_COPY_V7 } from "./landing-copy-v7";

export interface SeoJsonLdProps {
  nonce?: string;
}

export interface SeoJsonLdGraph {
  "@context": "https://schema.org";
  "@graph": Array<Record<string, unknown>>;
}

/**
 * Safely serializes data to a JSON string for application/ld+json script tags,
 * escaping HTML-sensitive characters to prevent XSS and script breakout.
 */
export function safeJsonLdStringify(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

/**
 * Generates the canonical Schema.org @graph payload for The CLARA Care.
 */
export function getSeoJsonLdGraph(): SeoJsonLdGraph {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": ["MedicalOrganization", "Organization"],
        "@id": "https://theclaracare.com/#organization",
        name: "The CLARA Care",
        alternateName: ["CLARA Care", "The Clara Care", "Trợ lý AI Y tế CLARA"],
        url: "https://theclaracare.com",
        logo: "https://theclaracare.com/icons/clara-logo.png",
        description:
          "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam, hỗ trợ tra cứu tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn đa chuyên khoa và dòng thời gian sức khỏe LifeMap.",
        medicalSpecialty: [
          "Cardiology",
          "Nephrology",
          "ClinicalPharmacology",
          "PrimaryCare",
        ],
      },
      {
        "@type": ["WebApplication", "SoftwareApplication"],
        "@id": "https://theclaracare.com/#software",
        name: "CLARA Care System",
        applicationCategory: "HealthApplication",
        operatingSystem: "Web, iOS, Android",
        featureList: [
          "FIDES Safety Drug-Drug Interaction Verification",
          "Longitudinal Health Timeline LifeMap",
          "Multi-Specialty Medical Council",
          "Ambient Clinical Scribe (SOAP Notes)",
          "Living Evidence Hub (DAV, DrugBank, WHO, FDA, PubMed)",
          "Zero-CoT Banking-Grade Medical Privacy",
        ],
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "VND",
        },
      },
      {
        "@type": "WebSite",
        "@id": "https://theclaracare.com/#website",
        url: "https://theclaracare.com",
        name: "The CLARA Care",
        inLanguage: ["vi-VN", "en-US"],
        potentialAction: {
          "@type": "SearchAction",
          target: "https://theclaracare.com/chat?q={search_term_string}",
          "query-input": "required name=search_term_string",
        },
      },
      {
        "@type": "FAQPage",
        "@id": "https://theclaracare.com/#faq",
        mainEntity: LANDING_COPY_V7.vi.faq.items.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: item.answer,
          },
        })),
      },
      {
        "@type": "MedicalWebPage",
        "@id": "https://theclaracare.com/#medicalwebpage",
        url: "https://theclaracare.com",
        name: "The CLARA Care",
        about: "Medical Artificial Intelligence & Clinical Decision Support",
        aspect: [
          "DiagnosisSupport",
          "TreatmentGuidance",
          "MedicationSafety",
        ],
        inLanguage: ["vi-VN", "en-US"],
        isPartOf: {
          "@id": "https://theclaracare.com/#website",
        },
        publisher: {
          "@id": "https://theclaracare.com/#organization",
        },
      },
    ],
  };
}

export function SeoJsonLd({ nonce }: SeoJsonLdProps = {}) {
  const structuredData = getSeoJsonLdGraph();
  const serialized = safeJsonLdStringify(structuredData);

  return (
    <script
      type="application/ld+json"
      nonce={nonce}
      dangerouslySetInnerHTML={{ __html: serialized }}
    />
  );
}

export default SeoJsonLd;
