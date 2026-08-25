import type { Metadata } from "next";
import PrivacyPolicyPage from "@/app/legal/privacy/page";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân | The Clara Care",
  description:
    "Chính sách bảo vệ dữ liệu cá nhân, quyền của chủ thể dữ liệu (DSAR) theo Nghị định 13/2023/NĐ-CP, cam kết Zero-PII/Zero-CoT và minh bạch AI theo Luật 134/2025.",
  alternates: {
    canonical: "/legal/privacy",
  },
};

export default function RootPrivacyPage() {
  return <PrivacyPolicyPage />;
}
