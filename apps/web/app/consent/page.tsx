import type { Metadata } from "next";
import MedicalConsentPage from "@/app/legal/consent/page";

export const metadata: Metadata = {
  title: "Đồng thuận sử dụng y tế & Ranh giới lâm sàng | The Clara Care",
  description:
    "Điều khoản đồng thuận bắt buộc trước khi sử dụng các tính năng có tác động lâm sàng trong The Clara Care theo Luật Khám bệnh 2023, Nghị định 13/2023/NĐ-CP và Luật AI 134/2025.",
  alternates: {
    canonical: "/legal/consent",
  },
};

export default function RootConsentPage() {
  return <MedicalConsentPage />;
}
