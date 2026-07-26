import { PRIMARY_ACTIONS, type PrimarySurface } from "@/lib/primary-actions";
import Button from "@/components/ui/button";
import { SurfaceCard } from "@/components/ui/surface";

type GuideTask = {
  title: string;
  detail: string;
  surface: PrimarySurface;
  icon: string;
  steps: string[];
};

const TASKS: GuideTask[] = [
  {
    title: "Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc",
    detail: "Dùng khi bạn cần câu trả lời nhanh, dễ đọc, có nhắc an toàn.",
    surface: "chat",
    icon: "chat",
    steps: ["Nhập câu hỏi bằng ngôn ngữ bình thường.", "Chọn Nhanh nếu chỉ cần trả lời ngắn.", "Đọc phần lưu ý an toàn trước khi làm theo."],
  },
  {
    title: "Tôi muốn câu trả lời kỹ hơn",
    detail: "Dùng Tư duy hoặc Pro khi cần phân tích dài, nhiều nguồn hơn.",
    surface: "chat_thinking",
    icon: "psychology",
    steps: ["Bấm nút chỉnh chế độ cạnh ô nhập.", "Chọn Tư duy cho phân tích kỹ hơn, Pro cho báo cáo dài.", "Chọn Đầy đủ nguồn nếu muốn CLARA kiểm tra nhiều nguồn hơn."],
  },
  {
    title: "Tôi muốn lưu thuốc đang dùng",
    detail: "Tủ thuốc giúp CLARA nhớ danh sách thuốc để kiểm tra tương tác.",
    surface: "selfmed",
    icon: "medication",
    steps: ["Thêm từng thuốc hoặc quét ảnh đơn thuốc.", "Bổ sung liều dùng nếu biết.", "Khi có ít nhất 2 thuốc, chạy kiểm tra tương tác."],
  },
  {
    title: "Tôi muốn kiểm tra hai thuốc có kỵ nhau không",
    detail: "Dùng mục kiểm tra tương tác thuốc trước khi phối hợp nhiều thuốc.",
    surface: "ddi",
    icon: "health_and_safety",
    steps: ["Đảm bảo tủ thuốc đã có ít nhất 2 thuốc.", "Bấm Kiểm tra tương tác thuốc.", "Đọc cặp thuốc bị cảnh báo và phần Bạn nên làm gì."],
  },
  {
    title: "Tôi là bác sĩ và cần hội chẩn ca khó",
    detail: "Hội chẩn AI phù hợp khi ca có nhiều hướng xử trí hoặc nhiều chuyên khoa.",
    surface: "council",
    icon: "groups",
    steps: ["Nhập bối cảnh ca bệnh rõ ràng.", "Thêm kết quả xét nghiệm hoặc ghi chú nếu có.", "Dùng kết quả như tài liệu tham khảo, không thay thế quyết định lâm sàng."],
  },
  {
    title: "Tôi muốn ghi lại buổi khám",
    detail: "Medical scribe giúp chuyển ghi chú thành bản tóm tắt có cấu trúc.",
    surface: "scribe",
    icon: "edit_note",
    steps: ["Nhập hoặc dán nội dung buổi khám.", "Kiểm tra lại bản SOAP trước khi dùng.", "Không đưa thông tin nhạy cảm nếu chưa có đồng ý phù hợp."],
  },
];

const LABELS = [
  { term: "Nhanh", meaning: "Trả lời ngắn, ít chờ, hợp với câu hỏi đơn giản." },
  { term: "Tư duy", meaning: "Phân tích kỹ hơn, hợp với câu hỏi cần lý giải." },
  { term: "Pro", meaning: "Báo cáo dài và đầy đủ hơn, dùng khi cần nghiên cứu sâu." },
  { term: "Tự chọn nguồn", meaning: "CLARA tự chọn phạm vi nguồn phù hợp để tiết kiệm thời gian." },
  { term: "Đầy đủ nguồn", meaning: "CLARA kiểm tra nhiều nguồn hơn, có thể chờ lâu hơn." },
];

export default function GuidePage() {
  return (
    <main className="mx-auto max-w-6xl space-y-6 px-5 py-8 sm:px-6 lg:px-8">
      <SurfaceCard className="p-5 sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Bắt đầu tại đây</p>
        <h1 className="mt-2 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)]">Hướng dẫn sử dụng CLARA</h1>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
          Chọn việc bạn muốn làm, làm theo 3 bước ngắn, rồi mở thẳng đúng màn hình. CLARA chỉ hỗ trợ tham khảo; khi có dấu hiệu nguy hiểm, hãy liên hệ cơ sở y tế.
        </p>
      </SurfaceCard>

      <section className="grid gap-3 md:grid-cols-2">
        {TASKS.map((task) => {
          const action = PRIMARY_ACTIONS[task.surface];
          return (
            <SurfaceCard key={task.title} className="p-4">
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined mt-0.5 text-[22px] text-[var(--brand-600)]">{task.icon}</span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">{task.title}</h2>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{task.detail}</p>
                </div>
              </div>
              <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm leading-6 text-[var(--text-secondary)]">
                {task.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className="mt-4">
                <Button as="link" href={action.href} variant="secondary" size="sm">
                  {action.label}
                </Button>
              </div>
            </SurfaceCard>
          );
        })}
      </section>

      <SurfaceCard className="p-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Các nhãn trong ô chat nghĩa là gì?</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {LABELS.map((item) => (
            <div key={item.term} className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
              <p className="text-sm font-semibold text-[var(--text-primary)]">{item.term}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{item.meaning}</p>
            </div>
          ))}
        </div>
      </SurfaceCard>
    </main>
  );
}
