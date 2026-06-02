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
  rule_verification_enabled: {
    label: "Rule Verification",
    hint: "Bật lớp kiểm chứng theo luật/policy trước khi phát hành câu trả lời."
  },
  nli_model_enabled: {
    label: "NLI Model",
    hint: "Bật mô hình NLI để chấm quan hệ claim-evidence."
  },
  rag_reranker_enabled: {
    label: "Neural Reranker",
    hint: "Bật reranker neural để ưu tiên bằng chứng chất lượng cao."
  },
  rag_nli_enabled: {
    label: "RAG NLI",
    hint: "Bật bước NLI trong pipeline RAG cho claim verification."
  },
  rag_graphrag_enabled: {
    label: "GraphRAG",
    hint: "Bật nhánh GraphRAG cho truy xuất theo quan hệ/đồ thị tri thức."
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
