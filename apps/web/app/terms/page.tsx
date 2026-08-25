import type { Metadata } from "next";
import TermsOfServicePage from "@/app/legal/terms/page";

export const metadata: Metadata = {
  title: "Điều khoản sử dụng & Thỏa thuận người dùng | The Clara Care",
  description:
    "Thỏa thuận người dùng quy định quyền, nghĩa vụ, ranh giới y tế theo Luật Khám bệnh 2023, bảo vệ dữ liệu theo Nghị định 13/2023/NĐ-CP và minh bạch AI theo Luật 134/2025.",
  alternates: {
    canonical: "/legal/terms",
  },
};

export default function RootTermsPage() {
  return <TermsOfServicePage />;
}
