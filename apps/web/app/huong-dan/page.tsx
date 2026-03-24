import Link from "next/link";

const QUICK_START = [
  {
    role: "Người dùng cá nhân",
    steps: [
      "Đăng nhập và chọn vai trò phù hợp.",
      "Vào mục Kiểm tra an toàn thuốc để nhập thuốc/triệu chứng.",
      "Đọc mức độ rủi ro và khuyến nghị trước khi dùng thuốc tiếp."
    ]
  },
  {
    role: "Nhà nghiên cứu",
    steps: [
      "Mở Không gian hỏi đáp nghiên cứu.",
      "Viết câu hỏi rõ bối cảnh và mục tiêu phân tích.",
      "Đối chiếu phần trả lời với nguồn tham chiếu và bước phân tích."
    ]
  },
  {
    role: "Bác sĩ",
    steps: [
      "Chọn vai trò bác sĩ để mở quyền truy cập nâng cao.",
      "Dùng Hội chẩn AI cho trường hợp phức tạp hoặc nhiều chuyên khoa.",
      "Dùng Trợ lý ghi chép y khoa để chuẩn hóa tóm tắt bệnh án."
    ]
  }
];

const FAQ = [
  {
    q: "CLARA có thay thế bác sĩ không?",
    a: "Không. CLARA hỗ trợ tham khảo thông tin và gợi ý, không thay thế chẩn đoán hoặc chỉ định lâm sàng trực tiếp."
  },
  {
    q: "Khi nào cần gọi cấp cứu ngay?",
    a: "Khi có dấu hiệu nguy hiểm cấp tính (khó thở nặng, đau ngực dữ dội, rối loạn ý thức...), cần gọi 115 hoặc đến cơ sở y tế gần nhất ngay."
  },
  {
    q: "Tôi có thể kiểm tra tương tác thuốc tại nhà không?",
    a: "Có. Vào Kiểm tra an toàn thuốc, nhập danh sách thuốc đang dùng và đọc cảnh báo theo mức độ rủi ro."
  }
];

export default function GuidePage() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Hướng dẫn sử dụng CLARA</h1>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Trang này giúp người mới bắt đầu nhanh theo đúng vai trò, giảm thao tác thử-sai và dùng đúng tính năng ngay từ đầu.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href="/login" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white">
            Đăng nhập
          </Link>
          <Link href="/" className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
            Về trang giới thiệu
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {QUICK_START.map((item) => (
          <article key={item.role} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">{item.role}</h2>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">
              {item.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </article>
        ))}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Câu hỏi thường gặp</h2>
        <div className="mt-4 space-y-3">
          {FAQ.map((item) => (
            <details key={item.q} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <summary className="cursor-pointer text-sm font-semibold text-slate-900">{item.q}</summary>
              <p className="mt-2 text-sm leading-7 text-slate-700">{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
        <h2 className="text-base font-semibold text-amber-900">Lưu ý an toàn</h2>
        <p className="mt-2 text-sm leading-7 text-amber-900">
          CLARA là công cụ hỗ trợ tham khảo. Với tình huống khẩn cấp hoặc có dấu hiệu nguy hiểm, hãy liên hệ cơ sở y tế ngay.
        </p>
      </section>
    </main>
  );
}
