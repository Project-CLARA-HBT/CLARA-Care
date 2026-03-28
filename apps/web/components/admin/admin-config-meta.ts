import { FlowToggleKey } from "@/components/admin/use-control-tower-config";

export const FLOW_FLAG_META: Record<FlowToggleKey, { label: string; hint: string }> = {
  role_router_enabled: {
    label: "Role Router",
    hint: "Route theo vai trò chuyên môn trước khi truy xuất dữ liệu."
  },
  intent_router_enabled: {
    label: "Intent Router",
    hint: "Chọn nhánh xử lý theo loại yêu cầu (clinical, policy, triage)."
  },
  verification_enabled: {
    label: "Verification",
    hint: "Bật lớp kiểm chứng FIDES trước khi phát hành câu trả lời."
  },
  deepseek_fallback_enabled: {
    label: "DeepSeek Fallback",
    hint: "Fallback khi RAG confidence thấp hoặc context không đủ."
  },
  scientific_retrieval_enabled: {
    label: "Scientific Retrieval",
    hint: "Bật truy xuất từ PubMed/EuropePMC cho câu hỏi cần chứng cứ."
  },
  web_retrieval_enabled: {
    label: "Web Retrieval",
    hint: "Bật truy xuất bổ sung từ nguồn web uy tín (khi được cấu hình)."
  },
  file_retrieval_enabled: {
    label: "File Retrieval",
    hint: "Sử dụng nội dung file người dùng upload trong bước retrieval."
  }
};

export const DEFAULT_SOURCE_CATEGORIES = [
  "guideline",
  "policy",
  "faq",
  "drug-safety",
  "protocol",
  "research",
  "general"
];
