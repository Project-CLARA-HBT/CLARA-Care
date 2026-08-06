import "@/styles/globals.css";
import AppShell from "@/components/app-shell";
import AnalyticsConsentBootstrap from "@/components/analytics/analytics-consent-bootstrap";
import { getThemeInitScript } from "@/lib/theme";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { UI_LANGUAGE_COOKIE_NAME } from "@/lib/ui-language";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://theclaracare.com").replace(/\/+$/, "");

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "The Clara Care",
    template: "%s | The Clara Care",
  },
  description: "The Clara Care - trợ lý AI y tế cho research, hội chẩn tham khảo và an toàn thuốc.",
  openGraph: {
    title: "The Clara Care",
    description: "Clinical Agent for Retrieval & Analysis",
    url: SITE_URL,
    siteName: "The Clara Care",
    locale: "vi_VN",
    type: "website",
  },
  alternates: {
    canonical: SITE_URL,
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
      </head>
      <body>
        <AnalyticsConsentBootstrap />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
