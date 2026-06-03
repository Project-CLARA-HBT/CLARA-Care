import Link from "next/link";

type GuideTask = {
  title: string;
  detail: string;
  href: string;
  action: string;
  icon: string;
  steps: string[];
};

const TASKS: GuideTask[] = [
  {
    title: "Tôi muốn hỏi CLARA về triệu chứng hoặc thuốc",
    detail: "Dùng khi bạn cần câu trả lời nhanh, dễ đọc, có nhắc an toàn.",
    href: "/chat",
    action: "Mở hỏi CLARA",
    icon: "chat",
    steps: ["Nhập câu hỏi bằng ngôn ngữ bình thường.", "Chọn Nhanh nếu chỉ cần trả lời ngắn.", "Đọc phần lưu ý an toàn trước khi làm theo."],
  },
  {
    title: "Tôi muốn câu trả lời kỹ hơn",
    detail: "Dùng Tư duy hoặc Pro khi cần phân tích dài, nhiều nguồn hơn.",
    href: "/chat",
    action: "Mở chế độ Tư duy",
    icon: "psychology",
    steps: ["Bấm nút chỉnh chế độ cạnh ô nhập.", "Chọn Tư duy cho phân tích kỹ hơn, Pro cho báo cáo dài.", "Chọn Đầy đủ nguồn nếu muốn CLARA kiểm tra nhiều nguồn hơn."],
  },
  {
    title: "Tôi muốn lưu thuốc đang dùng",
    detail: "Tủ thuốc giúp CLARA nhớ danh sách thuốc để kiểm tra tương tác.",
    href: "/selfmed",
    action: "Mở tủ thuốc",
    icon: "medication",
    steps: ["Thêm từng thuốc hoặc quét ảnh đơn thuốc.", "Bổ sung liều dùng nếu biết.", "Khi có ít nhất 2 thuốc, chạy kiểm tra tương tác."],
  },
  {
    title: "Tôi muốn kiểm tra hai thuốc có kỵ nhau không",
    detail: "Dùng mục kiểm tra tương tác thuốc trước khi phối hợp nhiều thuốc.",
    href: "/selfmed/ddi",
    action: "Kiểm tra tương tác",
    icon: "health_and_safety",
    steps: ["Đảm bảo tủ thuốc đã có ít nhất 2 thuốc.", "Bấm Kiểm tra tương tác thuốc.", "Đọc cặp thuốc bị cảnh báo và phần Bạn nên làm gì."],
  },
  {
    title: "Tôi là bác sĩ và cần hội chẩn ca khó",
    detail: "Hội chẩn AI phù hợp khi ca có nhiều hướng xử trí hoặc nhiều chuyên khoa.",
    href: "/council",
    action: "Mở hội chẩn AI",
    icon: "groups",
    steps: ["Nhập bối cảnh ca bệnh rõ ràng.", "Thêm kết quả xét nghiệm hoặc ghi chú nếu có.", "Dùng kết quả như tài liệu tham khảo, không thay thế quyết định lâm sàng."],
  },
  {
    title: "Tôi muốn ghi lại buổi khám",
    detail: "Medical scribe giúp chuyển ghi chú thành bản tóm tắt có cấu trúc.",
    href: "/scribe",
    action: "Mở ghi chép y khoa",
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
      <section className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Bắt đầu tại đây</p>
        <h1 className="mt-2 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)]">Hướng dẫn sử dụng CLARA</h1>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
          Chọn việc bạn muốn làm, làm theo 3 bước ngắn, rồi mở thẳng đúng màn hình. CLARA chỉ hỗ trợ tham khảo; khi có dấu hiệu nguy hiểm, hãy liên hệ cơ sở y tế.
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        {TASKS.map((task) => (
          <article key={task.title} className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
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
            <Link href={task.href} className="mt-4 inline-flex min-h-10 items-center rounded-md bg-[var(--text-primary)] px-3 text-sm font-semibold text-[var(--bg-canvas)] transition hover:opacity-90">
              {task.action}
            </Link>
          </article>
        ))}
      </section>

      <section className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Các nhãn trong ô chat nghĩa là gì?</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {LABELS.map((item) => (
            <div key={item.term} className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
              <p className="text-sm font-semibold text-[var(--text-primary)]">{item.term}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{item.meaning}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
