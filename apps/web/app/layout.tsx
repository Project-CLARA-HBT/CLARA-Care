import "@/styles/globals.css";
import UnifiedAppShell from "@/components/shell/unified-app-shell";
import { PreferenceProvider } from "@/components/shell/preference-provider";
import { ServerSessionProvider } from "@/components/shell/session-boundary";
import { ProfileProvider } from "@/components/shell/profile-boundary";
import { WorkspaceProvider } from "@/lib/workspace/workspace-provider";
import { ShellModeProvider } from "@/components/shell/shell-mode-provider";
import { CommandPaletteProvider } from "@/components/shell/command-palette-provider";
import AnalyticsConsentBootstrap from "@/components/analytics/analytics-consent-bootstrap";
import { getThemeInitScript } from "@/lib/theme";
import { SeoJsonLd } from "@/components/seo/seo-json-ld";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { UI_LANGUAGE_COOKIE_NAME } from "@/lib/ui-language";

export const metadata: Metadata = {
  metadataBase: new URL("https://theclaracare.com"),
  title: {
    default: "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
    template: "%s | The Clara Care",
  },
  description:
    "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
  keywords: [
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
  ],
  authors: [{ name: "The Clara Care Team", url: "https://theclaracare.com" }],
  creator: "The Clara Care",
  publisher: "The Clara Care",
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
  openGraph: {
    title: "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
    description:
      "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
    url: "https://theclaracare.com",
    siteName: "The Clara Care",
    locale: "vi_VN",
    alternateLocale: ["en_US"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam | Clinical AI Assistant",
    description:
      "Hệ thống trợ lý AI y tế và lâm sàng an toàn hàng đầu Việt Nam. Đối chiếu Dược thư Quốc gia, kiểm chứng tương tác thuốc FIDES, bệnh án SOAP Scribe, hội chẩn Council đa chuyên khoa và bảo mật Zero-CoT.",
    creator: "@theclaracare",
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || "google-site-verification-token",
    yandex: process.env.NEXT_PUBLIC_YANDEX_VERIFICATION,
    yahoo: process.env.NEXT_PUBLIC_YAHOO_VERIFICATION,
    other: {
      "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION || "bing-verification-token",
    },
  },
  alternates: {
    canonical: "https://theclaracare.com",
    languages: {
      "vi-VN": "https://theclaracare.com",
      "en-US": "https://theclaracare.com",
    },
  },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const language = cookieStore.get(UI_LANGUAGE_COOKIE_NAME)?.value === "en" ? "en" : "vi";

  return (
    <html lang={language} suppressHydrationWarning>
      <head>
        <meta name="color-scheme" content="light dark" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap"
        />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap"
        />
        <script id="theme-init" dangerouslySetInnerHTML={{ __html: getThemeInitScript() }} />
        <SeoJsonLd />
      </head>
      <body>
        <AnalyticsConsentBootstrap />
        <PreferenceProvider initialLanguage={language}>
          <ServerSessionProvider>
            <ProfileProvider>
              <WorkspaceProvider>
                <ShellModeProvider>
                  <CommandPaletteProvider>
                    <UnifiedAppShell>{children}</UnifiedAppShell>
                  </CommandPaletteProvider>
                </ShellModeProvider>
              </WorkspaceProvider>
            </ProfileProvider>
          </ServerSessionProvider>
        </PreferenceProvider>
      </body>
    </html>
  );
}
