import Link from "next/link";

const USE_CASES = [
  {
    title: "Cho người dùng cá nhân",
    description:
      "Theo dõi thuốc, kiểm tra tương tác thuốc cơ bản và nhận nhắc nhở an toàn trong đời sống hằng ngày.",
    href: "/careguard"
  },
  {
    title: "Cho nhà nghiên cứu",
    description:
      "Đặt câu hỏi nghiên cứu, nhận câu trả lời có nguồn tham chiếu và các bước phân tích rõ ràng.",
    href: "/research"
  },
  {
    title: "Cho bác sĩ",
    description:
      "Hội chẩn AI, ghi chép y khoa và theo dõi trạng thái hệ thống phục vụ quyết định lâm sàng.",
    href: "/council"
  }
];

const HOW_IT_WORKS = [
  "Nhập câu hỏi hoặc bối cảnh ca bệnh bằng ngôn ngữ tự nhiên.",
  "CLARA phân tích theo vai trò và truy xuất nguồn dữ liệu phù hợp.",
  "Nhận câu trả lời có cấu trúc, mức độ tin cậy và gợi ý bước tiếp theo."
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-10 pt-12 md:grid-cols-[1.3fr_1fr]">
        <article className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <p className="mb-3 inline-flex rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-semibold tracking-wide text-slate-600">
            CLARA Web
          </p>
          <h1 className="text-3xl font-bold leading-tight text-slate-900 md:text-4xl">
            Trợ lý AI y tế cho hỏi đáp chuyên sâu và quản lý thuốc an toàn tại nhà
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 md:text-base">
            CLARA kết hợp tra cứu tri thức y dược chuẩn hóa, phân tích theo vai trò người dùng và hiển thị kết quả
            minh bạch để bạn ra quyết định tốt hơn.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/login"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Bắt đầu ngay
            </Link>
            <Link
              href="/huong-dan"
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Xem hướng dẫn sử dụng
            </Link>
          </div>

          <div className="mt-8 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nguồn dữ liệu tham chiếu</p>
            <p className="mt-2 text-sm text-slate-600">Bộ Y tế Việt Nam, WHO, PubMed, openFDA, RxNorm.</p>
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bắt đầu đúng vai trò</p>
          <div className="mt-4 space-y-3">
            <Link href="/role-select" className="block rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
              <p className="text-sm font-semibold text-slate-900">Chọn vai trò sử dụng</p>
              <p className="mt-1 text-xs text-slate-600">Người dùng cá nhân, nhà nghiên cứu hoặc bác sĩ.</p>
            </Link>
            <Link href="/research" className="block rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
              <p className="text-sm font-semibold text-slate-900">Mở không gian hỏi đáp</p>
              <p className="mt-1 text-xs text-slate-600">Đặt câu hỏi theo dạng chatbot, nhận câu trả lời có cấu trúc.</p>
            </Link>
            <Link href="/careguard" className="block rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
              <p className="text-sm font-semibold text-slate-900">Kiểm tra an toàn thuốc</p>
              <p className="mt-1 text-xs text-slate-600">Kiểm tra nhanh triệu chứng, thuốc và nguy cơ tương tác.</p>
            </Link>
          </div>
        </article>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-10">
        <h2 className="text-xl font-semibold text-slate-900">CLARA phục vụ ai?</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {USE_CASES.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-slate-900">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
              <Link href={item.href} className="mt-4 inline-block text-sm font-medium text-blue-600 hover:underline">
                Mở tính năng
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-14">
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-900">Cách hoạt động</h2>
          <ol className="mt-4 grid gap-3 md:grid-cols-3">
            {HOW_IT_WORKS.map((step) => (
              <li key={step} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                {step}
              </li>
            ))}
          </ol>
        </article>
      </section>
    </main>
  );
}
