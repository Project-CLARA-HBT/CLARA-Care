import "@/styles/globals.css";
import AppShell from "@/components/app-shell";

export const metadata = {
  title: "CLARA Web",
  description: "CLARA - trợ lý AI y tế cho hỏi đáp và quản lý thuốc an toàn"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
