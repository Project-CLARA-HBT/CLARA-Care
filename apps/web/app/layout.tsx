import "@/styles/globals.css";
import "material-symbols/outlined.css";
import AppShell from "@/components/app-shell";
import { getThemeInitScript } from "@/lib/theme";
import type { Metadata } from "next";
import { Manrope } from "next/font/google";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://theclaracare.com").replace(/\/+$/, "");
const manrope = Manrope({
  subsets: ["latin", "vietnamese"],
  display: "swap",
  weight: ["200", "300", "400", "500", "600", "700", "800"],
});

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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" suppressHydrationWarning className={manrope.className}>
      <head>
        <meta name="color-scheme" content="light dark" />
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css" />
        <script id="theme-init" dangerouslySetInnerHTML={{ __html: getThemeInitScript() }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
