import type { Metadata } from "next";
import LandingV7 from "@/components/landing/v7/landing-v7";
import { SeoJsonLd } from "@/components/landing/v7/seo-json-ld";

export const metadata: Metadata = {
  metadataBase: new URL("https://theclaracare.com"),
  title: "The Clara Care — Trợ lý AI Y tế Lâm sàng & Tham vấn Sức khỏe An toàn | Clinical AI Assistant",
  description:
    "Hệ thống trợ lý AI y tế và hỗ trợ quyết định lâm sàng (CDSS) hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án điện tử SOAP AI Scribe, hội chẩn AI Council đa chuyên khoa và bảo mật Zero-CoT.",
  keywords: [
    // Vietnamese primary search keywords
    "The Clara Care",
    "trợ lý AI y tế",
    "AI y tế Việt Nam",
    "trợ lý lâm sàng AI",
    "tra cứu dược thư quốc gia",
    "kiểm tra tương tác thuốc",
    "hội chẩn AI đa chuyên khoa",
    "bệnh án điện tử SOAP",
    "bác sĩ AI",
    "tủ thuốc gia đình thông minh",
    "phân tích đơn thuốc AI",
    "chăm sóc sức khỏe AI",
    "tham vấn sức khỏe an toàn",
    "kiểm chứng FIDES",
    "bảo mật y tế Zero-CoT",
    // English primary search keywords
    "Clinical AI Assistant",
    "Medical AI Assistant",
    "Medical AI Vietnam",
    "Clinical Decision Support System",
    "CDSS",
    "Drug-Drug Interaction Checker",
    "Vietnamese National Pharmacopoeia",
    "Multispecialty AI Council",
    "SOAP Clinical Notes AI Scribe",
    "Medical LLM",
    "Healthcare AI Platform",
    "Zero-CoT Medical Privacy",
    "FIDES Clinical Verification",
  ],
  alternates: {
    canonical: "/",
    languages: {
      "vi-VN": "/",
      "en-US": "/?lang=en",
    },
  },
  openGraph: {
    title: "The Clara Care — Trợ lý AI Y tế Lâm sàng & Tham vấn Sức khỏe An toàn",
    description:
      "Trợ lý AI y tế và lâm sàng an toàn chuẩn Dược thư Quốc gia Việt Nam, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe và hội chẩn Council đa chuyên khoa.",
    url: "/",
    siteName: "The Clara Care",
    locale: "vi_VN",
    alternateLocale: ["en_US"],
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "The Clara Care — Trợ lý AI Y tế Lâm sàng & Tham vấn Sức khỏe An toàn",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "The Clara Care — Trợ lý AI Y tế Lâm sàng & Tham vấn Sức khỏe An toàn",
    description:
      "Trợ lý AI y tế lâm sàng chuẩn Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, ghi chép SOAP và hội chẩn Council đa chuyên khoa.",
    images: ["/twitter-image"],
    creator: "@theclaracare",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || "google-site-verification-token",
    yandex: process.env.NEXT_PUBLIC_YANDEX_VERIFICATION,
    yahoo: process.env.NEXT_PUBLIC_YAHOO_VERIFICATION,
    other: {
      "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION || "bing-verification-token",
    },
  },
  other: {
    "ai-agent": "https://theclaracare.com/.well-known/ai-plugin.json",
    "mcp-server": "https://theclaracare.com/.well-known/mcp.json",
    "llms-txt": "https://theclaracare.com/llms.txt",
    rating: "general",
    referrer: "origin-when-cross-origin",
    classification: "Medical Artificial Intelligence & Clinical Decision Support System",
  },
};

export default function HomePage() {
  return (
    <>
      <SeoJsonLd />
      <LandingV7 />
    </>
  );
}
