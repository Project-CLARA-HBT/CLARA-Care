import { describe, expect, it } from "vitest";
import { metadata } from "./layout";

describe("RootLayout Metadata & SEO Suite", () => {
  it("exports metadataBase configured to https://theclaracare.com", () => {
    expect(metadata.metadataBase?.toString()).toBe("https://theclaracare.com/");
  });

  it("exports rich title template and default", () => {
    expect(metadata.title).toEqual({
      default:
        "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
      template: "%s | The Clara Care",
    });
  });

  it("exports description mentioning pharmacopoeia, FIDES, SOAP, Council and Zero-CoT", () => {
    expect(metadata.description).toBe(
      "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
    );
  });

  it("exports comprehensive bilingual keywords array", () => {
    expect(metadata.keywords).toEqual([
      "trợ lý AI y tế",
      "trợ lý AI lâm sàng",
      "AI y tế Việt Nam",
      "kiểm tra tương tác thuốc",
      "tra cứu dược thư quốc gia online",
      "bệnh án điện tử SOAP AI",
      "hội chẩn đa chuyên khoa AI",
      "tủ thuốc gia đình thông minh",
      "dòng thời gian sức khỏe LifeMap",
      "phân tích xét nghiệm AI",
      "bảo mật y tế Zero-CoT",
      "clinical AI assistant Vietnam",
      "medical AI assistant",
      "FIDES medical AI verification",
      "zero-cot medical privacy",
      "SOAP clinical notes AI scribe",
      "living evidence hub medical AI",
    ]);
  });

  it("exports authors, creator, and publisher", () => {
    expect(metadata.authors).toEqual([
      { name: "The Clara Care Team", url: "https://theclaracare.com" },
    ]);
    expect(metadata.creator).toBe("The Clara Care");
    expect(metadata.publisher).toBe("The Clara Care");
  });

  it("exports robots configuration with GoogleBot specifications", () => {
    expect(metadata.robots).toEqual({
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    });
  });

  it("exports OpenGraph metadata with locale and alternateLocale", () => {
    expect(metadata.openGraph).toEqual({
      title:
        "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
      description:
        "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
      url: "https://theclaracare.com",
      siteName: "The Clara Care",
      locale: "vi_VN",
      alternateLocale: ["en_US"],
      type: "website",
    });
  });

  it("exports Twitter Card metadata", () => {
    expect(metadata.twitter).toEqual({
      card: "summary_large_image",
      title:
        "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
      description:
        "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
      creator: "@theclaracare",
    });
  });

  it("exports verification and alternates with vi-VN and en-US", () => {
    expect(metadata.alternates).toEqual({
      canonical: "https://theclaracare.com",
      languages: {
        "vi-VN": "https://theclaracare.com",
        "en-US": "https://theclaracare.com",
      },
    });
    expect(metadata.verification).toBeDefined();
  });
});
