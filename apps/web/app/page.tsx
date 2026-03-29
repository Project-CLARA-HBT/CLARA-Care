import Link from "next/link";

const HERO_BULLETS = [
  "Hỏi đáp y tế có citation thay vì câu trả lời chung chung.",
  "Quản lý tủ thuốc cá nhân xuyên phiên, không mất dữ liệu sau mỗi lần chat.",
  "Cảnh báo tương tác thuốc (DDI) theo mức rủi ro trước khi ra quyết định.",
] as const;

const PROOF_STRIP = [
  {
    value: "3 lớp",
    label: "Synthesis -> Verify -> Policy trước khi phản hồi",
  },
  {
    value: "Permanent",
    label: "Tủ thuốc SelfMed lưu lâu dài theo tài khoản",
  },
  {
    value: "DDI Check",
    label: "Phát hiện tương tác thuốc theo mức độ rủi ro",
  },
  {
    value: "RBAC",
    label: "Mã hóa dữ liệu và phân quyền theo vai trò",
  },
] as const;

const OFFERS = [
  {
    tag: "Research",
    title: "CLARA Research",
    subtitle: "Chatflow chuyên sâu có evidence panel",
    bullets: [
      "Trả lời theo ngữ cảnh với citation rõ nguồn.",
      "Upload tài liệu để tạo knowledge source riêng.",
      "Fallback model khi thiếu ngữ cảnh để giảm phản hồi rỗng.",
    ],
    cta: "Vào Clara Research",
    href: "/research",
  },
  {
    tag: "SelfMed",
    title: "CLARA SelfMed",
    subtitle: "Tủ thuốc cá nhân + OCR + DDI",
    bullets: [
      "Scan hóa đơn/đơn thuốc để thêm nhanh vào tủ thuốc.",
      "Theo dõi lịch sử thuốc xuyên phiên sử dụng.",
      "Cảnh báo tương tác thuốc trước khi sử dụng cùng lúc.",
    ],
    cta: "Mở SelfMed",
    href: "/selfmed",
  },
  {
    tag: "Control Tower",
    title: "Admin Dashboard",
    subtitle: "Quan sát và điều phối toàn bộ luồng trả lời",
    bullets: [
      "Quản lý RAG source, policy và answer flow tại một nơi.",
      "Debug preview và run history cho từng phiên xử lý.",
      "Theo dõi chất lượng phản hồi để tối ưu vận hành.",
    ],
    cta: "Mở Admin Dashboard",
    href: "/admin/overview",
  },
] as const;

const MECHANISM_STEPS = [
  {
    step: "01",
    title: "Bạn hỏi hoặc nạp tài liệu",
    detail:
      "Bắt đầu bằng câu hỏi trực tiếp hoặc upload tài liệu để hệ thống hiểu đúng ngữ cảnh cần tra cứu.",
  },
  {
    step: "02",
    title: "CLARA truy hồi và tổng hợp",
    detail:
      "Router chọn luồng phù hợp, truy hồi đa nguồn và tổng hợp câu trả lời có cấu trúc.",
  },
  {
    step: "03",
    title: "Kiểm chứng và chặn rủi ro",
    detail:
      "Lớp verify và policy gate kiểm tra độ tin cậy trước khi hiển thị cho người dùng.",
  },
  {
    step: "04",
    title: "Bạn nhận kết quả có thể hành động",
    detail:
      "Kết quả gồm citation, mức rủi ro và gợi ý bước tiếp theo để quyết định nhanh và an toàn hơn.",
  },
] as const;

const OBJECTIONS = [
  {
    objection: "Tôi sợ câu trả lời AI thiếu căn cứ.",
    response:
      "Mỗi câu trả lời ưu tiên đi kèm citation nguồn để bạn kiểm tra lại ngay trên panel bằng chứng.",
    reassurance: "Nguồn tham chiếu: PubMed, openFDA, Dược thư VN (theo thiết lập hệ thống).",
  },
  {
    objection: "Tôi ngại nhập lại tủ thuốc sau mỗi lần dùng.",
    response:
      "SelfMed lưu dữ liệu theo tài khoản để tiếp tục theo dõi thuốc xuyên phiên, không cần tạo lại từ đầu.",
    reassurance: "OCR-first giúp thêm thuốc nhanh từ ảnh hóa đơn/đơn thuốc.",
  },
  {
    objection: "Tôi không rành kỹ thuật, sợ khó dùng.",
    response:
      "Luồng mặc định tối giản: hỏi ngay, đọc tóm tắt, mở bằng chứng khi cần kiểm tra sâu.",
    reassurance: "Giao diện ưu tiên thao tác một chạm trên mobile và desktop.",
  },
  {
    objection: "Tôi lo dữ liệu sức khỏe bị lộ.",
    response:
      "Nền tảng áp dụng mã hóa dữ liệu và phân quyền theo vai trò để giới hạn truy cập đúng phạm vi.",
    reassurance: "Thiết kế hệ thống ưu tiên kiểm soát truy cập và audit vận hành.",
  },
] as const;

export default function HomePage() {
  return (
    <main className="relative overflow-hidden bg-slate-50 pb-16 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[34rem] bg-[radial-gradient(circle_at_20%_18%,rgba(14,165,233,0.18),transparent_36%),radial-gradient(circle_at_82%_16%,rgba(37,99,235,0.16),transparent_42%),linear-gradient(to_bottom,rgba(15,23,42,0.04),transparent)]" />

      <section className="relative mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-10">
        <header className="rounded-2xl border border-slate-200/70 bg-white/85 px-4 py-3 shadow-[0_18px_44px_-32px_rgba(15,23,42,0.35)] backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-700 dark:text-cyan-300">
                CLARA Care Platform
              </p>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Research + SelfMed + Control Tower
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/huong-dan"
                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Xem hướng dẫn
              </Link>
              <Link
                href="/login"
                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Đăng nhập
              </Link>
              <Link
                href="/register"
                className="rounded-full bg-cyan-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-cyan-700"
              >
                Dùng thử miễn phí
              </Link>
            </div>
          </div>
        </header>
      </section>

      <section className="relative mx-auto mt-6 grid w-full max-w-7xl gap-5 px-4 sm:px-6 lg:grid-cols-[1.24fr_0.76fr] lg:px-10">
        <article className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_26px_80px_-46px_rgba(2,132,199,0.6)] sm:p-8 dark:border-slate-800 dark:bg-slate-900">
          <p className="inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-700 dark:border-cyan-900 dark:bg-cyan-950/30 dark:text-cyan-300">
            Conversion-first hero
          </p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight tracking-tight text-slate-950 sm:text-5xl dark:text-white">
            Tra cứu y tế có căn cứ, giảm rủi ro dùng thuốc và ra quyết định nhanh hơn trong một luồng duy nhất.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600 sm:text-base dark:text-slate-300">
            CLARA kết hợp chatbot research, tủ thuốc thông minh và lớp kiểm chứng trước phản hồi để giúp bạn
            hành động chắc chắn hơn, thay vì tự lọc thông tin rời rạc từ nhiều nguồn.
          </p>

          <ul className="mt-5 grid gap-2 text-sm text-slate-700 sm:grid-cols-2 dark:text-slate-200">
            {HERO_BULLETS.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 leading-6 dark:border-slate-700 dark:bg-slate-800/60"
              >
                {item}
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-700"
            >
              Bắt đầu miễn phí
            </Link>
            <Link
              href="/research"
              className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Xem demo chatbot
            </Link>
          </div>
        </article>

        <aside className="rounded-3xl border border-cyan-200 bg-gradient-to-br from-cyan-600 via-cyan-600 to-blue-700 p-6 text-white shadow-[0_26px_72px_-40px_rgba(3,105,161,0.9)] dark:border-cyan-400/30 sm:p-7">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-cyan-100">Why now</p>
          <h2 className="mt-2 text-2xl font-semibold leading-tight sm:text-3xl">
            Vấn đề không phải thiếu thông tin. Vấn đề là thiếu hệ thống để ra quyết định an toàn.
          </h2>
          <p className="mt-3 text-sm leading-7 text-cyan-50/95">
            Nếu tra cứu rời rạc, bạn phải tự kiểm chứng từng nguồn và tự đối chiếu rủi ro thuốc. CLARA gom tất cả
            vào một workflow có kiểm chứng để rút ngắn thời gian và giảm sai sót.
          </p>
          <div className="mt-5 rounded-2xl border border-white/35 bg-white/12 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-100">Primary outcome</p>
            <p className="mt-2 text-sm leading-6 text-white">
              Từ "không chắc nên tin gì" sang "có căn cứ, có cảnh báo, có bước hành động tiếp theo".
            </p>
          </div>
        </aside>
      </section>

      <section className="relative mx-auto mt-6 w-full max-w-7xl px-4 sm:px-6 lg:px-10">
        <article className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_20px_50px_-36px_rgba(15,23,42,0.4)] dark:border-slate-800 dark:bg-slate-900 sm:p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Proof strip
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PROOF_STRIP.map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/60"
              >
                <p className="text-sm font-semibold text-cyan-700 dark:text-cyan-300">{item.value}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-slate-300">{item.label}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="relative mx-auto mt-6 w-full max-w-7xl px-4 sm:px-6 lg:px-10">
        <article className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_72px_-40px_rgba(2,132,199,0.35)] dark:border-slate-800 dark:bg-slate-900 sm:p-7">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                Offer blocks
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl dark:text-white">
                Chọn điểm vào phù hợp, nhưng vẫn nằm trong một hệ thống thống nhất
              </h2>
            </div>
            <Link
              href="/register"
              className="rounded-xl border border-cyan-300 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-700 transition hover:bg-cyan-100 dark:border-cyan-900 dark:bg-cyan-950/30 dark:text-cyan-300 dark:hover:bg-cyan-950/50"
            >
              Tạo tài khoản ngay
            </Link>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            {OFFERS.map((offer) => (
              <div
                key={offer.title}
                className="group rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-[0_16px_44px_-28px_rgba(2,132,199,0.55)] dark:border-slate-700 dark:bg-slate-800/60"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-700 dark:text-cyan-300">
                  {offer.tag}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900 dark:text-slate-100">{offer.title}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{offer.subtitle}</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-200">
                  {offer.bullets.map((point) => (
                    <li key={point} className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900/70">
                      {point}
                    </li>
                  ))}
                </ul>
                <Link
                  href={offer.href}
                  className="mt-4 inline-flex rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-700"
                >
                  {offer.cta}
                </Link>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="relative mx-auto mt-6 w-full max-w-7xl px-4 sm:px-6 lg:px-10">
        <article className="rounded-3xl border border-cyan-200 bg-gradient-to-r from-cyan-600 to-blue-700 p-6 text-white shadow-[0_28px_76px_-42px_rgba(3,105,161,0.9)] sm:p-7 dark:border-cyan-400/30">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-cyan-100">Mechanism</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            Cơ chế vận hành: rõ ràng, có kiểm soát, dễ theo dõi
          </h2>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {MECHANISM_STEPS.map((item) => (
              <div key={item.step} className="rounded-2xl border border-white/30 bg-white/10 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-100">Step {item.step}</p>
                <p className="mt-1 text-sm font-semibold text-white">{item.title}</p>
                <p className="mt-1 text-sm leading-6 text-cyan-50/95">{item.detail}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="relative mx-auto mt-6 w-full max-w-7xl px-4 sm:px-6 lg:px-10">
        <article className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)] dark:border-slate-800 dark:bg-slate-900 sm:p-7">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Objection handling
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl dark:text-white">
            Các lo ngại phổ biến trước khi bắt đầu
          </h2>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {OBJECTIONS.map((item) => (
              <div
                key={item.objection}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60"
              >
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.objection}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-200">{item.response}</p>
                <p className="mt-2 rounded-lg border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs leading-5 text-cyan-700 dark:border-cyan-900 dark:bg-cyan-950/30 dark:text-cyan-300">
                  {item.reassurance}
                </p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="relative mx-auto mt-6 w-full max-w-7xl px-4 sm:px-6 lg:px-10">
        <article className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-slate-50 shadow-[0_24px_80px_-42px_rgba(15,23,42,0.85)] sm:p-8 dark:border-slate-700">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-cyan-300">Final CTA</p>
          <h2 className="mt-2 max-w-4xl text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
            Dành 3 phút để thiết lập luồng tra cứu và quản lý thuốc an toàn hơn cho bạn và gia đình.
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
            Không cần thay đổi quy trình ngay lập tức. Bắt đầu từ một câu hỏi hoặc một đơn thuốc, sau đó mở rộng
            dần theo nhu cầu thực tế của bạn.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
            >
              Bắt đầu miễn phí ngay
            </Link>
            <Link
              href="/huong-dan"
              className="rounded-xl border border-slate-600 bg-slate-900 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-slate-800"
            >
              Xem hướng dẫn triển khai
            </Link>
          </div>
        </article>
      </section>

      <footer className="relative mx-auto mt-6 w-full max-w-7xl border-t border-slate-200 px-5 pt-5 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400 sm:px-6 lg:px-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p>© 2026 CLARA Care. All rights reserved.</p>
          <div className="flex flex-wrap gap-3">
            <a href="#" className="transition hover:text-slate-700 dark:hover:text-slate-200">
              Điều khoản
            </a>
            <a href="#" className="transition hover:text-slate-700 dark:hover:text-slate-200">
              Bảo mật
            </a>
            <a href="#" className="transition hover:text-slate-700 dark:hover:text-slate-200">
              Miễn trừ y khoa
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
