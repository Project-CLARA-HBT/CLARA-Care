import type { Metadata } from "next";
import ClaraKp3Landing from "@/components/landing/clara-kp3-landing";

export const metadata: Metadata = {
  title: "The Clara Care — Trợ lý AI Lâm sàng & Y tế An toàn",
  description:
    "Hệ thống trợ lý AI y tế hỗ trợ quyết định lâm sàng có kiểm chứng FIDES, bảo mật dữ liệu Zero-CoT và quy trình minh bạch cho bác sĩ và người dùng cá nhân.",
};

export default function HomePage() {
  return <ClaraKp3Landing />;
}
