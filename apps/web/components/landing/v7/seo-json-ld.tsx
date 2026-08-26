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
 * Generates the canonical Schema.org @graph payload for The CLARA Care
 * with high-density semantic entity grounding for Gemini AI Overviews and ChatGPT citations.
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
        sameAs: [
          "https://www.wikidata.org/wiki/Q1156298",
          "https://www.wikidata.org/wiki/Q11660",
          "https://www.wikidata.org/wiki/Q12140",
          "https://www.wikidata.org/wiki/Q8386",
          "https://www.wikidata.org/wiki/Q11190",
        ],
        medicalSpecialty: [
          "Cardiology",
          "Nephrology",
          "ClinicalPharmacology",
          "PrimaryCare",
          "Endocrinology",
        ],
        knowsAbout: [
          {
            "@type": "MedicalEntity",
            name: "Drug-Drug Interaction (DDI)",
            alternateName: "Tương tác thuốc",
            code: [
              {
                "@type": "MedicalCode",
                code: "D004347",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "79899007",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D004347",
              "http://snomed.info/id/79899007",
              "https://www.wikidata.org/wiki/Q8386",
            ],
          },
          {
            "@type": "MedicalEntity",
            name: "Clinical Decision Support Systems (CDSS)",
            alternateName: "Hệ thống hỗ trợ ra quyết định lâm sàng",
            code: [
              {
                "@type": "MedicalCode",
                code: "D020000",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "423876004",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D020000",
              "http://snomed.info/id/423876004",
              "https://www.wikidata.org/wiki/Q5133827",
            ],
          },
          {
            "@type": "MedicalEntity",
            name: "Pharmacovigilance",
            alternateName: "Cảnh giác dược",
            code: [
              {
                "@type": "MedicalCode",
                code: "D060733",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "386053000",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D060733",
              "http://snomed.info/id/386053000",
              "https://www.wikidata.org/wiki/Q1479493",
            ],
          },
          {
            "@type": "MedicalEntity",
            name: "SOAP Note (Subjective, Objective, Assessment, Plan)",
            alternateName: "Bệnh án cấu trúc SOAP",
            code: [
              {
                "@type": "MedicalCode",
                code: "D000072001",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "425268008",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D000072001",
              "http://snomed.info/id/425268008",
              "https://www.wikidata.org/wiki/Q7390312",
            ],
          },
          {
            "@type": "MedicalEntity",
            name: "Telehealth / Telemedicine",
            alternateName: "Y tế từ xa",
            code: [
              {
                "@type": "MedicalCode",
                code: "D017216",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "448337001",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D017216",
              "http://snomed.info/id/448337001",
              "https://www.wikidata.org/wiki/Q17377543",
            ],
          },
          {
            "@type": "MedicalEntity",
            name: "ICD-10 (International Classification of Diseases, 10th Revision)",
            alternateName: "Phân loại bệnh tật quốc tế ICD-10",
            code: [
              {
                "@type": "MedicalCode",
                code: "D007388",
                codingSystem: "MeSH",
              },
              {
                "@type": "MedicalCode",
                code: "446522006",
                codingSystem: "SNOMED-CT",
              },
            ],
            sameAs: [
              "https://id.nlm.nih.gov/mesh/D007388",
              "http://snomed.info/id/446522006",
              "https://www.wikidata.org/wiki/Q45127",
            ],
          },
        ],
      },
      {
        "@type": ["WebApplication", "SoftwareApplication"],
        "@id": "https://theclaracare.com/#software",
        name: "CLARA Care System",
        applicationCategory: "HealthApplication",
        applicationSubCategory: "Clinical Decision Support System (CDSS)",
        operatingSystem: "Web, iOS, Android",
        softwareRequirements:
          "HTML5, HTTPS, WebRTC Audio Capture, Modern Web Browser (Chrome 100+, Safari 15+, Firefox 100+, Edge)",
        aggregateRating: {
          "@type": "AggregateRating",
          ratingValue: 4.9,
          reviewCount: 1250,
          bestRating: 5,
          worstRating: 1,
        },
        featureList: [
          "FIDES Safety Drug-Drug Interaction Verification",
          "Longitudinal Health Timeline LifeMap",
          "Multi-Specialty Medical Council",
          "Ambient Clinical Scribe (SOAP Notes)",
          "Living Evidence Hub (DAV, DrugBank, WHO, FDA, PubMed)",
          "Zero-CoT Banking-Grade Medical Privacy",
        ],
        hasPart: [
          {
            "@type": ["SoftwareApplication", "WebApplication"],
            name: "FIDES Guard",
            applicationCategory: "HealthApplication",
            applicationSubCategory:
              "Drug-Drug Interaction & Dosage Safety Verification",
            description:
              "Deterministic drug-drug interaction and dosage safety verification engine grounded on national pharmacopoeia.",
            url: "https://theclaracare.com/safety",
            featureList: [
              "Deterministic multi-drug interaction checking",
              "Dosage range verification",
              "Real-time safety blocking",
            ],
          },
          {
            "@type": ["SoftwareApplication", "WebApplication"],
            name: "LifeMap Timeline",
            applicationCategory: "HealthApplication",
            applicationSubCategory: "Longitudinal Patient Health Timeline",
            description:
              "Chronological health timeline connecting symptoms, clinical encounters, lab values, and prescription modifications.",
            url: "https://theclaracare.com/lifemap",
            featureList: [
              "Longitudinal symptom tracking",
              "Medication alteration history",
              "Lab result trends",
            ],
          },
          {
            "@type": ["SoftwareApplication", "WebApplication"],
            name: "Medical Council",
            applicationCategory: "HealthApplication",
            applicationSubCategory: "Multidisciplinary Clinical Consensus",
            description:
              "Multi-specialty clinical deliberation engine synthesizing consensus, disagreements, and uncertainty across Cardiology, Nephrology, and Pharmacology.",
            url: "https://theclaracare.com/council",
            featureList: [
              "Cross-specialty consensus synthesis",
              "Disagreement highlighting",
              "Uncertainty boundary detection",
            ],
          },
          {
            "@type": ["SoftwareApplication", "WebApplication"],
            name: "SOAP Scribe",
            applicationCategory: "HealthApplication",
            applicationSubCategory:
              "Ambient Clinical Transcription & Note Generation",
            description:
              "Ambient medical voice transcription and automated SOAP clinical progress note generator for outpatient encounters.",
            url: "https://theclaracare.com/scribe",
            featureList: [
              "Ambient consultation recording",
              "Bilingual medical transcription",
              "Automated SOAP note drafting",
            ],
          },
          {
            "@type": ["SoftwareApplication", "WebApplication"],
            name: "Living Evidence Hub",
            applicationCategory: "HealthApplication",
            applicationSubCategory: "Medical Literature & Evidence Synthesis",
            description:
              "Hierarchical medical literature retrieval engine grounded in DAV, DrugBank 5.1, WHO guidelines, FDA DailyMed, and PubMed/MEDLINE.",
            url: "https://theclaracare.com/research",
            featureList: [
              "Hierarchical evidence grading",
              "Authoritative pharmacopoeia indexing",
              "Live citation inspection",
            ],
          },
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
        specialty: [
          "Cardiology",
          "Nephrology",
          "ClinicalPharmacology",
          "PrimaryCare",
          "Endocrinology",
        ],
        medicalSpecialty: [
          "Cardiology",
          "Nephrology",
          "ClinicalPharmacology",
          "PrimaryCare",
          "Endocrinology",
        ],
        citation: [
          "Dược thư Quốc gia Việt Nam",
          "DrugBank 5.1",
          "WHO Guidelines for Essential Medicines",
          "US FDA DailyMed",
          "PubMed / MEDLINE",
        ],
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
