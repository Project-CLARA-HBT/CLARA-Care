import type { Metadata } from "next";
import CookiePolicyPage from "@/app/legal/cookies/page";

export const metadata: Metadata = {
  title: "Chính sách cookie & Quản lý phiên làm việc | The Clara Care",
  description:
    "Mô tả chi tiết cách The Clara Care sử dụng cookie thiết yếu, token bảo mật (CSRF, X-Session) và tùy chọn giao diện; cam kết 100% không theo dõi quảng cáo bên thứ ba theo Nghị định 13/2023/NĐ-CP.",
  alternates: {
    canonical: "/legal/cookies",
  },
};

export default function RootCookiesPage() {
  return <CookiePolicyPage />;
}
