import Link from "next/link";

const TRUST_ITEMS = [
  "Nguồn tham chiếu y tế có kiểm chứng",
  "Ưu tiên an toàn khi dùng thuốc tại nhà",
  "Thiết kế cho người mới lẫn chuyên môn"
] as const;

const VALUE_CARDS = [
  {
    title: "CLARA Research",
    text: "Hỏi đáp y tế theo chế độ nhanh hoặc chuyên sâu, có dẫn nguồn để kiểm tra lại.",
    points: ["Trả lời theo mode", "Sources + steps", "Fallback an toàn"]
  },
  {
    title: "CLARA Self-Med",
    text: "Tủ thuốc cá nhân permanent: quét hóa đơn, thêm thuốc tự động, kiểm tra tương tác.",
    points: ["OCR -> Add cabinet", "Auto DDI check", "Risk rõ mức độ"]
  },
  {
    title: "Admin Control Tower",
    text: "Quản trị nguồn RAG, answer flow và quan sát hệ thống kiểu control plane.",
    points: ["RAG sources", "Flow toggles", "Observability"]
  }
] as const;

const FAQS = [
  {
    q: "CLARA có thay thế bác sĩ không?",
    a: "Không. CLARA hỗ trợ tra cứu và giảm sai sót vận hành. Quyết định điều trị cuối cùng vẫn thuộc chuyên gia y tế."
  },
  {
    q: "Người mới có dùng được không?",
    a: "Có. Giao diện ưu tiên đơn giản: nhập câu hỏi, nhận câu trả lời, xem nguồn và hành động tiếp theo."
  },
  {
    q: "Tủ thuốc có lưu lâu dài không?",
    a: "Có. Tủ thuốc gắn với tài khoản, không mất sau khi đăng xuất hoặc kết thúc phiên."
  }
] as const;

function MiniAnalyticsVisual() {
  return (
    <div className="glass-card rounded-2xl p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Live Snapshot</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-sky-100 bg-sky-50/80 p-3">
          <p className="text-[11px] uppercase tracking-wide text-sky-700">Questions/day</p>
          <p className="mt-1 text-xl font-semibold text-slate-900">12.4K</p>
          <div className="mt-2 h-1.5 rounded-full bg-sky-100">
            <div className="h-1.5 w-[72%] rounded-full bg-sky-500" />
          </div>
        </div>
        <div className="rounded-xl border border-teal-100 bg-teal-50/80 p-3">
          <p className="text-[11px] uppercase tracking-wide text-teal-700">DDI Checks/day</p>
          <p className="mt-1 text-xl font-semibold text-slate-900">4.8K</p>
          <div className="mt-2 h-1.5 rounded-full bg-teal-100">
            <div className="h-1.5 w-[61%] rounded-full bg-teal-500" />
          </div>
        </div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/80 p-3">
          <p className="text-[11px] uppercase tracking-wide text-indigo-700">Source Coverage</p>
          <p className="mt-1 text-xl font-semibold text-slate-900">92%</p>
          <div className="mt-2 h-1.5 rounded-full bg-indigo-100">
            <div className="h-1.5 w-[92%] rounded-full bg-indigo-500" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden px-4 pb-12 pt-6 sm:px-6 lg:px-10">
      <div className="pointer-events-none absolute -left-16 top-20 h-72 w-72 rounded-full bg-sky-300/25 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-28 h-72 w-72 rounded-full bg-teal-300/25 blur-3xl" />

      <section className="mx-auto max-w-7xl">
        <header className="glass-card rounded-2xl px-4 py-3 sm:px-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700">CLARA Care Platform</p>
              <p className="text-sm text-slate-600">Nền tảng AI y tế hiện đại cho Research và Self-Med</p>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/login" className="rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700">
                Đăng nhập
              </Link>
              <Link href="/register" className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white">
                Dùng thử miễn phí
              </Link>
            </div>
          </div>
        </header>

        <div className="mt-6 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <article className="glass-card rounded-3xl p-6 sm:p-8">
            <p className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-sky-700">
              healthcare ai copilot
            </p>
            <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight text-slate-950 sm:text-5xl">
              Một nền tảng cho <span className="med-gradient-text">hỏi đáp y tế</span> và{" "}
              <span className="med-gradient-text">tủ thuốc cá nhân</span>
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600 sm:text-base">
              CLARA giúp bạn trả lời câu hỏi y khoa nhanh, có nguồn tham chiếu, đồng thời quản lý thuốc tại nhà an toàn hơn với luồng
              quét hóa đơn và kiểm tra tương tác tự động.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/register" className="rounded-xl bg-sky-600 px-5 py-3 text-sm font-semibold text-white hover:bg-sky-700">
                Bắt đầu ngay
              </Link>
              <Link href="/research" className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                Xem trải nghiệm chat
              </Link>
              <Link href="/selfmed" className="rounded-xl border border-teal-200 bg-teal-50 px-5 py-3 text-sm font-semibold text-teal-700 hover:border-teal-300">
                Xem module Self-Med
              </Link>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {TRUST_ITEMS.map((item) => (
                <span key={item} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                  {item}
                </span>
              ))}
            </div>
          </article>

          <aside className="glass-card rounded-3xl p-5 sm:p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Flow 3 bước cho người mới</p>
            <ol className="mt-3 space-y-3">
              <li className="rounded-2xl border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Bước 1</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">Đặt câu hỏi hoặc quét hóa đơn thuốc</p>
                <p className="mt-1 text-sm text-slate-600">Bắt đầu từ nhu cầu thực tế, không cần cấu hình phức tạp.</p>
              </li>
              <li className="rounded-2xl border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Bước 2</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">Nhận trả lời rõ nguồn và mức rủi ro</p>
                <p className="mt-1 text-sm text-slate-600">Kết quả luôn ưu tiên hành động an toàn, dễ hiểu.</p>
              </li>
              <li className="rounded-2xl border border-slate-200 bg-white p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Bước 3</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">Lưu tủ thuốc và theo dõi lâu dài</p>
                <p className="mt-1 text-sm text-slate-600">Dữ liệu lưu permanent theo tài khoản, không mất theo phiên.</p>
              </li>
            </ol>
          </aside>
        </div>
      </section>

      <section className="mx-auto mt-6 max-w-7xl">
        <MiniAnalyticsVisual />
      </section>

      <section className="mx-auto mt-6 grid max-w-7xl gap-4 md:grid-cols-3">
        {VALUE_CARDS.map((card) => (
          <article key={card.title} className="glass-card rounded-2xl p-5">
            <h2 className="text-lg font-semibold text-slate-900">{card.title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{card.text}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {card.points.map((point) => (
                <span key={point} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">
                  {point}
                </span>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="mx-auto mt-6 max-w-7xl">
        <article className="rounded-3xl border border-sky-200 bg-gradient-to-r from-sky-600 to-cyan-600 p-6 text-white shadow-[0_24px_72px_-38px_rgba(2,132,199,0.85)] sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-100">Ready to launch</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Bắt đầu onboarding và chạy thử ngay hôm nay</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-sky-50">
            Phù hợp cho cá nhân, phòng khám và đội nghiên cứu muốn một giao diện rõ ràng, dễ triển khai và có thể kiểm chứng nguồn.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/register" className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-sky-700 hover:bg-sky-50">
              Tạo tài khoản
            </Link>
            <Link href="/huong-dan" className="rounded-xl border border-white/60 bg-white/10 px-5 py-3 text-sm font-semibold text-white hover:bg-white/20">
              Xem hướng dẫn
            </Link>
          </div>
        </article>
      </section>

      <section className="mx-auto mt-6 max-w-7xl">
        <article className="glass-card rounded-3xl p-6 sm:p-7">
          <h3 className="text-xl font-semibold text-slate-900">Câu hỏi thường gặp</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {FAQS.map((item) => (
              <div key={item.q} className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-sm font-semibold text-slate-900">{item.q}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.a}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <footer className="mx-auto mt-6 max-w-7xl border-t border-slate-200 px-1 pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <p>© 2026 CLARA Care. All rights reserved.</p>
          <div className="flex flex-wrap gap-3">
            <a href="#" className="hover:text-slate-700">
              Điều khoản
            </a>
            <a href="#" className="hover:text-slate-700">
              Bảo mật
            </a>
            <a href="#" className="hover:text-slate-700">
              Miễn trừ y khoa
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
