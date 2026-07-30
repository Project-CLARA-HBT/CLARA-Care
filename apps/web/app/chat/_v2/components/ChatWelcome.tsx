"use client";

import type { UserRole } from "@/lib/auth-store";
import type { UILanguage } from "@/lib/ui-language";

type WelcomeContent = {
  eyebrow: string;
  title: string;
  description: string;
  prompts: Array<{ icon: string; label: string; prompt: string }>;
};

const CONTENT: Record<
  "normal" | "researcher" | "doctor",
  Record<UILanguage, WelcomeContent>
> = {
  normal: {
    vi: {
      eyebrow: "Hỏi theo cách của bạn",
      title: "Bạn muốn tìm hiểu điều gì?",
      description:
        "Mô tả triệu chứng, thuốc đang dùng hoặc kết quả xét nghiệm. CLARA sẽ trả lời rõ ràng và chỉ ra khi nào bạn nên gặp bác sĩ.",
      prompts: [
        {
          icon: "symptoms",
          label: "Hiểu triệu chứng",
          prompt: "Tôi nên theo dõi những dấu hiệu nào khi bị đau đầu kéo dài?",
        },
        {
          icon: "pill",
          label: "Hỏi về thuốc",
          prompt:
            "Giải thích cách dùng thuốc này và những tác dụng phụ cần lưu ý.",
        },
        {
          icon: "experiment",
          label: "Đọc xét nghiệm",
          prompt:
            "Giúp tôi hiểu kết quả xét nghiệm này bằng ngôn ngữ đơn giản.",
        },
        {
          icon: "health_and_safety",
          label: "Kiểm tra an toàn",
          prompt:
            "Các thuốc và thực phẩm bổ sung tôi đang dùng có tương tác không?",
        },
      ],
    },
    en: {
      eyebrow: "Ask in your own words",
      title: "What would you like to understand?",
      description:
        "Describe a symptom, medicine, or lab result. CLARA gives a clear answer and tells you when professional care may be needed.",
      prompts: [
        {
          icon: "symptoms",
          label: "Understand symptoms",
          prompt:
            "What warning signs should I watch for with a persistent headache?",
        },
        {
          icon: "pill",
          label: "Ask about medicine",
          prompt:
            "Explain how to take this medicine and which side effects matter.",
        },
        {
          icon: "experiment",
          label: "Read lab results",
          prompt: "Help me understand these lab results in plain language.",
        },
        {
          icon: "health_and_safety",
          label: "Check safety",
          prompt: "Could my medicines and supplements interact?",
        },
      ],
    },
  },
  researcher: {
    vi: {
      eyebrow: "Tìm hiểu có dẫn nguồn",
      title: "Bắt đầu từ một câu hỏi nghiên cứu",
      description:
        "Yêu cầu CLARA tổng hợp bằng chứng, đối chiếu kết quả và nêu rõ giới hạn của dữ liệu.",
      prompts: [
        {
          icon: "manage_search",
          label: "Tổng quan bằng chứng",
          prompt:
            "Tổng hợp bằng chứng gần đây về chủ đề này, nêu nguồn đã dùng và các giới hạn còn lại.",
        },
        {
          icon: "difference",
          label: "So sánh nghiên cứu",
          prompt:
            "So sánh thiết kế, quần thể và kết quả chính của các nghiên cứu liên quan.",
        },
        {
          icon: "fact_check",
          label: "Kiểm tra một nhận định",
          prompt: "Kiểm tra nhận định này, tìm bằng chứng ủng hộ và phản biện.",
        },
        {
          icon: "biotech",
          label: "Tìm khoảng trống",
          prompt:
            "Các khoảng trống bằng chứng và câu hỏi nghiên cứu tiếp theo là gì?",
        },
      ],
    },
    en: {
      eyebrow: "Evidence with traceable sources",
      title: "Start with a research question",
      description:
        "Ask CLARA to synthesize evidence, compare findings, and state the limits of the available data.",
      prompts: [
        {
          icon: "manage_search",
          label: "Evidence overview",
          prompt:
            "Synthesize recent evidence on this topic, state the sources used, and explain remaining limitations.",
        },
        {
          icon: "difference",
          label: "Compare studies",
          prompt:
            "Compare the design, population, and main findings of relevant studies.",
        },
        {
          icon: "fact_check",
          label: "Check a claim",
          prompt:
            "Check this claim and find both supporting and conflicting evidence.",
        },
        {
          icon: "biotech",
          label: "Find evidence gaps",
          prompt: "What evidence gaps and next research questions remain?",
        },
      ],
    },
  },
  doctor: {
    vi: {
      eyebrow: "Hỗ trợ quyết định lâm sàng",
      title: "Bạn đang cần làm rõ điều gì?",
      description:
        "Nhập bối cảnh ca bệnh để nhận tóm tắt có cấu trúc, chẩn đoán phân biệt, cảnh báo an toàn và bằng chứng liên quan.",
      prompts: [
        {
          icon: "clinical_notes",
          label: "Tóm tắt ca bệnh",
          prompt:
            "Tóm tắt ca bệnh này, nêu dữ kiện quan trọng và thông tin còn thiếu.",
        },
        {
          icon: "account_tree",
          label: "Chẩn đoán phân biệt",
          prompt:
            "Lập chẩn đoán phân biệt có ưu tiên và giải thích dữ kiện ủng hộ hoặc phản đối.",
        },
        {
          icon: "medication",
          label: "Rà soát thuốc",
          prompt:
            "Rà soát đơn thuốc này về tương tác, chống chỉ định và theo dõi cần thiết.",
        },
        {
          icon: "emergency",
          label: "Đánh giá nguy cơ",
          prompt:
            "Xác định dấu hiệu nguy hiểm và mức độ cần chuyển tuyến trong ca bệnh này.",
        },
      ],
    },
    en: {
      eyebrow: "Clinical decision support",
      title: "What do you need to clarify?",
      description:
        "Add the case context for a structured summary, differential, safety flags, and relevant evidence.",
      prompts: [
        {
          icon: "clinical_notes",
          label: "Summarize a case",
          prompt:
            "Summarize this case, highlight key facts, and identify missing information.",
        },
        {
          icon: "account_tree",
          label: "Build a differential",
          prompt:
            "Build a prioritized differential with supporting and opposing findings.",
        },
        {
          icon: "medication",
          label: "Review medicines",
          prompt:
            "Review this medication list for interactions, contraindications, and monitoring.",
        },
        {
          icon: "emergency",
          label: "Assess risk",
          prompt:
            "Identify red flags and the appropriate escalation level for this case.",
        },
      ],
    },
  },
};

export default function ChatWelcome({
  role,
  uiLanguage,
  onChoosePrompt,
}: {
  role: UserRole;
  uiLanguage: UILanguage;
  onChoosePrompt: (prompt: string) => void;
}) {
  const experience =
    role === "researcher"
      ? "researcher"
      : role === "doctor" || role === "admin"
        ? "doctor"
        : "normal";
  const content = CONTENT[experience][uiLanguage];

  return (
    <div className="clara-scrollbar flex min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-7 sm:py-12">
      <section className="mx-auto flex w-full max-w-3xl flex-col justify-center">
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--brand-600)] text-white shadow-[0_14px_30px_-18px_rgba(37,99,235,.85)]">
          <span
            className="material-symbols-outlined text-[25px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
            aria-hidden="true"
          >
            medical_services
          </span>
        </div>
        <p className="text-xs font-semibold text-[var(--text-brand)]">
          {content.eyebrow}
        </p>
        <h2 className="mt-2 max-w-2xl text-[clamp(1.8rem,4vw,2.65rem)] font-semibold leading-[1.08] tracking-[-0.045em] text-[var(--text-primary)]">
          {content.title}
        </h2>
        <p className="mt-3 max-w-2xl text-[15px] leading-6 text-[var(--text-secondary)]">
          {content.description}
        </p>

        <div className="mt-8 grid gap-2.5 sm:grid-cols-2">
          {content.prompts.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => onChoosePrompt(item.prompt)}
              className="group flex min-h-[64px] items-center gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-left shadow-[0_8px_24px_-24px_rgba(15,23,42,.55)] transition hover:-translate-y-0.5 hover:border-[color:var(--shell-border-strong)] hover:shadow-[0_14px_30px_-24px_rgba(37,99,235,.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] motion-reduce:transform-none"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <span
                  className="material-symbols-outlined text-[19px]"
                  aria-hidden="true"
                >
                  {item.icon}
                </span>
              </span>
              <span className="min-w-0 flex-1 text-[13px] font-semibold text-[var(--text-primary)]">
                {item.label}
              </span>
              <span
                className="material-symbols-outlined text-[18px] text-[var(--text-muted)] transition group-hover:translate-x-0.5"
                aria-hidden="true"
              >
                arrow_forward
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
