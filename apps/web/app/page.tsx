import type { Metadata } from "next";
import LandingV7 from "@/components/landing/v7/landing-v7";

export const metadata: Metadata = {
  title: "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn",
  description:
    "Hệ thống trợ lý AI y tế hỗ trợ quyết định lâm sàng có kiểm chứng FIDES, bảo mật dữ liệu Zero-CoT và quy trình minh bạch cho bác sĩ và người dùng cá nhân.",
};

export default function HomePage() {
  return <LandingV7 />;
}
