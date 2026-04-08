import Image from "next/image";
import Link from "next/link";

import { SPONSORS } from "@/components/landing/clara-kp3-data";

export default function ClaraKp3Landing() {
  const flowSteps = [
    {
      title: "Nêu vấn đề bạn đang cần xử lý",
      detail: "Bạn có thể hỏi tự do hoặc chọn gợi ý theo ca bệnh, thuốc hay guideline.",
    },
    {
      title: "CLARA tìm nguồn trước khi trả lời",
      detail: "Hệ thống lọc tài liệu liên quan, ưu tiên nguồn chính thống và gắn mức tin cậy theo từng ý.",
    },
    {
      title: "Nhận câu trả lời kèm nguồn trích",
      detail: "Mỗi luận điểm có citation rõ ràng để kiểm tra lại ngay, không phải lục lại từng tài liệu.",
    },
  ] as const;

  const metrics = [
    { label: "Phản hồi có nguồn trích", value: "95%+" },
    { label: "Thời gian trả lời trung vị", value: "< 20s" },
    { label: "Nguồn tri thức đã tích hợp", value: "8+" },
    { label: "Số bước để ra kết luận", value: "3 bước" },
  ] as const;

  const moduleOverview = [
    {
      tag: "Nghiên cứu",
      title: "CLARA Research",
      description: "Hỏi đáp theo ngữ cảnh lâm sàng, trả lời kèm citation để kiểm chứng nhanh.",
      highlight: "Phù hợp bác sĩ, sinh viên y và nhóm nghiên cứu.",
      cta: "Mở Research",
      href: "/research",
    },
    {
      tag: "Hội chẩn",
      title: "CLARA Council",
      description: "Flow hội chẩn theo từng bước để thu thập ý kiến, tổng hợp và chốt phương án rõ ràng.",
      highlight: "Giảm rối khi làm ca đa chuyên khoa.",
      cta: "Mở Council",
      href: "/council/new",
    },
    {
      tag: "Tự quản lý thuốc",
      title: "CLARA Self-Med",
      description: "Quản lý tủ thuốc cá nhân, nhắc lịch dùng thuốc và theo dõi theo tài khoản.",
      highlight: "Dễ dùng cho bệnh nhân và người chăm sóc.",
      cta: "Mở Self-Med",
      href: "/selfmed",
    },
    {
      tag: "An toàn thuốc",
      title: "CLARA CareGuard",
      description: "Cảnh báo tương tác thuốc theo mức độ để ưu tiên xử lý đúng việc cần làm trước.",
      highlight: "Hữu ích cho ca đa thuốc và ngoại trú.",
      cta: "Mở CareGuard",
      href: "/careguard",
    },
    {
      tag: "Ghi chép",
      title: "CLARA Scribe",
      description: "Chuẩn hóa ghi chú lâm sàng sau ca, giảm bớt thao tác hành chính lặp lại.",
      highlight: "Giúp bàn giao ca trực gọn và rõ.",
      cta: "Mở Scribe",
      href: "/scribe",
    },
    {
      tag: "Quản trị",
      title: "Control Tower",
      description: "Theo dõi nguồn tri thức, luồng trả lời và chất lượng vận hành trong một nơi.",
      highlight: "Dành cho admin và nhóm vận hành hệ thống.",
      cta: "Mở Control Tower",
      href: "/admin/overview",
    },
  ] as const;

  const differentiators = [
    {
      title: "Kiểm chứng nguồn theo từng bước",
      detail:
        "Research tách rõ `details`, `citations`, `deepdive`, `analyze` để bạn kiểm tra nguồn mạch lạc, không phải đọc một đoạn quá dài rồi tự dò lại.",
    },
    {
      title: "Hội chẩn có wizard rõ ràng",
      detail:
        "Council đi theo các bước intake → specialists → review trước khi tổng hợp, nên ca phức tạp vẫn giữ được trật tự.",
    },
    {
      title: "Tập trung vào an toàn thuốc thực tế",
      detail:
        "Từ tủ thuốc cá nhân, nhắc giờ dùng đến cảnh báo DDI theo mức độ, đủ dùng cho cả gia đình và phòng khám nhỏ.",
    },
    {
      title: "Cơ chế an toàn có thể bật/tắt theo môi trường",
      detail:
        "Hệ thống đã có các lớp guardrail như reranker, NLI, policy gate, confidence và fallback để kiểm soát chất lượng phản hồi.",
    },
    {
      title: "Control Tower cho vận hành hằng ngày",
      detail:
        "Admin có sẵn các trang observability, answer-flow, source-hub, knowledge-sources để theo dõi và kiểm tra chất lượng.",
    },
    {
      title: "Nguồn tri thức quốc tế và nội địa",
      detail:
        "Kết hợp nguồn chuẩn quốc tế với hướng dẫn trong nước để câu trả lời phù hợp bối cảnh Việt Nam hơn.",
    },
  ] as const;

  const testimonials = [
    {
      name: "Trần Đức Phúc",
      role: "Sinh viên Y6",
      quote: "Mình không còn phải mở quá nhiều tab để tìm nguồn. Câu trả lời có citation giúp làm seminar nhanh và chắc hơn.",
    },
    {
      name: "BS. Nguyễn Hoài Nam",
      role: "Bác sĩ Nội tổng quát",
      quote: "Phần mạnh nhất là tách rõ kết luận, nguồn tham chiếu và giới hạn. Dùng trong chuẩn bị hội chẩn rất ổn.",
    },
    {
      name: "Dương Quốc Bảo",
      role: "Research Assistant",
      quote: "Research flow gọn, follow-up tự nhiên và kiểm tra nguồn rất nhanh khi cần đối chiếu nhiều guideline.",
    },
  ] as const;

  const faqs = [
    {
      q: "CLARA có thay thế quyết định bác sĩ không?",
      a: "Không. CLARA là trợ lý Research và Chatbot có citation để hỗ trợ tham khảo. Quyết định chuyên môn cuối cùng vẫn do bác sĩ và cơ sở y tế.",
    },
    {
      q: "Điểm khác biệt so với chatbot thông thường là gì?",
      a: "CLARA tối ưu cho truy xuất bằng chứng: câu trả lời ưu tiên nguồn, hiển thị mức tin cậy và nêu rõ giới hạn khi thiếu dữ liệu.",
    },
    {
      q: "Bắt đầu onboarding nên đi từ đâu?",
      a: "Bắt đầu từ flow Research 3 bước: hỏi, kiểm chứng citation, chốt ghi chú. Khi KPI ổn định mới mở rộng sang Council hoặc SelfMed.",
    },
  ] as const;

  return (
    <main className="relative overflow-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-36 -top-28 h-80 w-80 rounded-full bg-cyan-200/55 blur-3xl dark:bg-cyan-900/35" />
        <div className="absolute right-0 top-16 h-[26rem] w-[26rem] rounded-full bg-blue-200/45 blur-3xl dark:bg-blue-900/25" />
      </div>

      <nav className="fixed inset-x-0 top-0 z-50 border-b border-slate-200/85 bg-white/90 px-4 py-4 backdrop-blur-xl dark:border-slate-800/85 dark:bg-slate-950/85 min-[1024px]:px-8">
        <div className="mx-auto flex w-full max-w-[1320px] items-center justify-between gap-3">
          <span className="text-xl font-black tracking-tight">Project CLARA</span>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#flow">
              Cách hoạt động
            </a>
            <a className="text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#modules">
              Tính năng
            </a>
            <a className="text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#workspace">
              Màn hình mẫu
            </a>
            <a className="text-sm font-semibold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#faq">
              Câu hỏi thường gặp
            </a>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/research"
              className="inline-flex min-h-10 items-center rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
            >
              Vào CLARA Research
            </Link>
          </div>
        </div>
      </nav>

      <section className="relative px-4 pb-20 pt-28 min-[1024px]:px-8 min-[1024px]:pt-32">
        <div className="mx-auto grid w-full max-w-[1320px] items-center gap-12 min-[1100px]:grid-cols-2">
          <div className="relative z-10">
            <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-sm font-semibold text-cyan-800 dark:border-cyan-900/60 dark:bg-cyan-950/40 dark:text-cyan-200">
              <span className="inline-block h-2 w-2 rounded-full bg-cyan-500 dark:bg-cyan-300" />
              Trợ lý nghiên cứu y khoa
            </span>

            <h1 className="mb-6 text-4xl font-black leading-tight tracking-tight min-[640px]:text-5xl min-[1280px]:text-6xl">
              Hỏi nhanh.
              <br />
              Có nguồn rõ ràng.
              <br />
              <span className="text-cyan-700 dark:text-cyan-300">Dễ chốt hướng xử lý.</span>
            </h1>

            <p className="mb-8 max-w-xl text-lg leading-relaxed text-slate-600 dark:text-slate-300">
              CLARA giúp bạn đi từ câu hỏi đến bằng chứng trong một luồng gọn: hỏi, kiểm tra nguồn, rồi quyết định.
              Mọi thứ tập trung vào khả năng dùng được ngay trong công việc thật.
            </p>

            <div className="mb-8 flex flex-wrap gap-4">
              <Link
                href="/research"
                className="inline-flex min-h-12 items-center gap-2 rounded-xl bg-slate-900 px-8 text-base font-bold text-white transition-all hover:-translate-y-0.5 hover:bg-slate-800 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
              >
                Bắt đầu tra cứu
              </Link>
              <Link
                href="/register"
                className="inline-flex min-h-12 items-center rounded-xl border border-slate-300 bg-white px-8 text-base font-bold text-slate-900 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
              >
                Đăng ký dùng thử
              </Link>
            </div>

            <div className="flex flex-wrap gap-3">
              {["Tóm tắt guideline", "Rà soát tương tác thuốc", "Chuẩn bị trước hội chẩn"].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="relative z-10 rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_24px_70px_-45px_rgba(15,23,42,0.55)] dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 dark:border-slate-700 dark:bg-slate-950">
              <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Không gian tra cứu CLARA
              </span>
              <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-950/45 dark:text-emerald-300">
                Đang hoạt động
              </span>
            </div>

            <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
                Bệnh nhân tăng huyết áp đang dùng Amlodipine + Simvastatin. Nguy cơ tương tác và hướng xử trí?
              </div>

              <div className="ml-auto max-w-[94%] rounded-2xl border border-cyan-200 bg-cyan-50 p-3 dark:border-cyan-900/60 dark:bg-cyan-950/35">
                <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-100">
                  Có nguy cơ tăng nồng độ Simvastatin khi phối hợp với Amlodipine. Nên cân nhắc giới hạn liều
                  Simvastatin và theo dõi triệu chứng đau cơ.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {["Nguồn PubMed", "Nguồn openFDA", "Ghi chú guideline"].map((chip) => (
                    <span
                      key={chip}
                      className="rounded-md border border-cyan-300/70 bg-white px-2 py-1 text-[11px] font-semibold text-cyan-800 dark:border-cyan-700 dark:bg-slate-900 dark:text-cyan-200"
                    >
                      {chip}
                    </span>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-2 text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  <span className="h-2 w-2 rounded-full bg-amber-500" />
                  Độ tin cậy: Khá cao | Cần đối chiếu phác đồ tại đơn vị
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-950">
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                  Gợi ý nhanh
                </p>
                <div className="flex flex-wrap gap-2">
                  {[
                    "So sánh guideline A vs B",
                    "Tóm tắt nghiên cứu trong 6 tháng gần đây",
                    "Những điểm cần chuyển bác sĩ chuyên khoa",
                  ].map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white/70 py-12 dark:border-slate-800 dark:bg-slate-900/70">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <p className="mb-8 text-center text-xs font-bold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
            Đối tác hạ tầng
          </p>
          <div className="grid grid-cols-1 gap-4 min-[900px]:grid-cols-2">
            {SPONSORS.map((sponsor) => (
              <a
                key={sponsor.name}
                href={sponsor.href}
                target="_blank"
                rel="noreferrer"
                className="flex min-h-[124px] items-center justify-center rounded-2xl border border-slate-200 bg-white px-5 py-4 transition-all hover:-translate-y-0.5 hover:shadow-md dark:border-slate-700 dark:bg-slate-950"
              >
                <Image
                  src={sponsor.logo}
                  alt={`${sponsor.name} logo`}
                  width={sponsor.name === "BNIX" ? 300 : 560}
                  height={sponsor.name === "BNIX" ? 86 : 180}
                  className={sponsor.name === "BNIX" ? "h-14 w-auto object-contain" : "h-20 w-auto object-contain"}
                />
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50 py-24 dark:bg-slate-950" id="flow">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <div className="mb-14 text-center">
            <h2 className="mb-4 text-3xl font-extrabold tracking-tight min-[900px]:text-4xl">
              Quy trình 3 bước cho CLARA Research
            </h2>
            <p className="mx-auto max-w-2xl text-slate-600 dark:text-slate-300">
              Mục tiêu là dùng thuận tay hằng ngày: nhập câu hỏi, kiểm tra nguồn, rồi chốt hướng xử lý.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-7 min-[900px]:grid-cols-3">
            {flowSteps.map((step, idx) => (
              <article
                key={step.title}
                className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-cyan-100 text-sm font-bold text-cyan-800 dark:bg-cyan-950/40 dark:text-cyan-200">
                  {idx + 1}
                </div>
                <h3 className="mb-3 text-xl font-bold">{step.title}</h3>
                <p className="text-slate-600 dark:text-slate-300">{step.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white py-24 dark:bg-slate-900" id="modules">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <div className="mb-12 text-center">
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-700 dark:text-cyan-300">
              Hệ sinh thái CLARA
            </p>
            <h2 className="mb-4 text-3xl font-extrabold tracking-tight min-[900px]:text-4xl">
              Toàn bộ chức năng chính trong một hệ thống
            </h2>
            <p className="mx-auto max-w-3xl text-slate-600 dark:text-slate-300">
              Bắt đầu từ Research là nhanh nhất. Khi cần mở rộng, bạn đã có sẵn hội chẩn, an toàn thuốc, ghi chép và
              bảng quản trị vận hành trong cùng một hệ thống.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 min-[900px]:grid-cols-2 min-[1280px]:grid-cols-3">
            {moduleOverview.map((module) => (
              <article
                key={module.title}
                className="group rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:-translate-y-0.5 hover:shadow-md dark:border-slate-700 dark:bg-slate-950"
              >
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-cyan-700 dark:text-cyan-300">
                  {module.tag}
                </p>
                <h3 className="mb-2 text-xl font-bold">{module.title}</h3>
                <p className="mb-4 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{module.description}</p>
                <p className="mb-5 text-xs font-semibold text-slate-500 dark:text-slate-400">{module.highlight}</p>
                <Link
                  href={module.href}
                  className="inline-flex min-h-9 items-center rounded-lg border border-slate-300 px-3 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  {module.cta}
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white py-24 dark:bg-slate-900" id="workspace">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-700 dark:text-cyan-300">
                Màn hình Research
              </p>
              <h2 className="text-3xl font-extrabold tracking-tight min-[900px]:text-4xl">
                Câu trả lời và nguồn trích hiển thị tách bạch
              </h2>
            </div>
            <Link
              href="/research"
              className="inline-flex min-h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Xem màn hình thật
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-6 min-[1100px]:grid-cols-[1.2fr_0.8fr]">
            <article className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-950">
              <div className="mb-5 flex items-center gap-2">
                {["Câu trả lời", "Nguồn trích", "Đào sâu"].map((tab, idx) => (
                  <span
                    key={tab}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                      idx === 0
                        ? "bg-cyan-100 text-cyan-800 dark:bg-cyan-950/40 dark:text-cyan-200"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    }`}
                  >
                    {tab}
                  </span>
                ))}
              </div>
              <h3 className="mb-2 text-xl font-bold">Tóm tắt câu trả lời theo luận điểm</h3>
              <p className="mb-4 text-slate-600 dark:text-slate-300">
                Mỗi đoạn trả lời đều gắn nguồn tương ứng để bạn kiểm tra nhanh và tự tin hơn khi dùng.
              </p>
              <div className="space-y-3">
                {[
                  "Luận điểm 1: Cơ chế tương tác thuốc và mức độ ảnh hưởng lâm sàng.",
                  "Luận điểm 2: Khuyến nghị theo guideline và ngưỡng cần theo dõi.",
                  "Luận điểm 3: Điều kiện cần chuyển bác sĩ chuyên khoa.",
                ].map((point) => (
                  <div
                    key={point}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  >
                    {point}
                  </div>
                ))}
              </div>
            </article>

            <article className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-950">
              <h3 className="mb-4 text-xl font-bold">Bảng nguồn trích</h3>
              <div className="space-y-3">
                {[
                  "PubMed: PMID 30588647",
                  "openFDA: Drug interaction label",
                  "Bộ Y tế: Hướng dẫn điều trị",
                ].map((ref) => (
                  <div
                    key={ref}
                    className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                  >
                    {ref}
                  </div>
                ))}
              </div>
              <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
                Nếu thiếu dữ liệu nền, hệ thống sẽ tự hạ độ tin cậy và nhắc bạn kiểm tra thêm.
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="bg-slate-50 py-24 dark:bg-slate-950">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <div className="mb-12 text-center">
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-700 dark:text-cyan-300">
              Điểm khác biệt
            </p>
            <h2 className="mb-4 text-3xl font-extrabold tracking-tight min-[900px]:text-4xl">
              Những điểm nổi bật đang có sẵn trong sản phẩm
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-6 min-[900px]:grid-cols-2 min-[1280px]:grid-cols-3">
            {differentiators.map((item) => (
              <article
                key={item.title}
                className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900"
              >
                <h3 className="mb-3 text-lg font-bold">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50 py-24 dark:bg-slate-950">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-extrabold tracking-tight min-[900px]:text-4xl">Các chỉ số bạn có thể theo dõi ngay</h2>
          </div>
          <div className="grid grid-cols-2 gap-5 min-[1024px]:grid-cols-4">
            {metrics.map((metric) => (
              <article key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5 text-center dark:border-slate-700 dark:bg-slate-900">
                <div className="mb-2 text-4xl font-black text-cyan-700 dark:text-cyan-300">{metric.value}</div>
                <p className="text-xs font-bold uppercase tracking-[0.13em] text-slate-600 dark:text-slate-300">{metric.label}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white py-24 dark:bg-slate-900">
        <div className="mx-auto w-full max-w-[1320px] px-4 min-[1024px]:px-8">
          <h2 className="mb-14 text-center text-3xl font-bold min-[900px]:text-4xl">Người dùng nói gì về CLARA</h2>
          <div className="grid grid-cols-1 gap-8 min-[1000px]:grid-cols-3">
            {testimonials.map((item) => (
              <article key={item.name} className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-950">
                <p className="mb-7 text-lg leading-relaxed text-slate-700 dark:text-slate-200">&quot;{item.quote}&quot;</p>
                <div>
                  <p className="text-sm font-bold">{item.name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{item.role}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white py-24 dark:bg-slate-900" id="faq">
        <div className="mx-auto w-full max-w-4xl px-4 min-[1024px]:px-8">
          <h2 className="mb-12 text-center text-3xl font-bold">Câu hỏi thường gặp</h2>
          <div className="space-y-4">
            {faqs.map((faq) => (
              <details key={faq.q} className="group overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-950">
                <summary className="flex cursor-pointer list-none items-center justify-between p-6">
                  <span className="font-bold">{faq.q}</span>
                  <span className="text-slate-500 transition-transform group-open:rotate-180 dark:text-slate-300">▾</span>
                </summary>
                <div className="px-6 pb-6 text-sm text-slate-600 dark:text-slate-300">{faq.a}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-24 min-[1024px]:px-8">
        <div className="mx-auto max-w-5xl rounded-[2rem] border border-slate-200 bg-slate-900 p-10 text-center min-[1024px]:p-16 dark:border-slate-700 dark:bg-slate-950">
          <h2 className="mb-6 text-4xl font-extrabold text-white min-[1024px]:text-5xl dark:text-slate-100">
            Từ câu hỏi đến bằng chứng
            <br />
            trong một màn hình.
          </h2>
          <p className="mx-auto mb-10 max-w-2xl text-lg text-slate-200 dark:text-slate-300">
            Bắt đầu từ CLARA Research để chuẩn hóa hỏi đáp có nguồn trích. Khi đã quen, bạn có thể mở rộng sang Council
            hoặc Self-Med mà không phải đổi cách làm việc.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              href="/research"
              className="inline-flex min-h-12 items-center rounded-xl bg-cyan-400 px-10 text-lg font-bold text-slate-900 transition-colors hover:bg-cyan-300 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
            >
              Dùng Research ngay
            </Link>
            <Link
              href="/register"
              className="inline-flex min-h-12 items-center rounded-xl border border-slate-600 px-10 text-lg font-bold text-slate-100 transition-colors hover:bg-slate-800 dark:border-slate-500 dark:hover:bg-slate-900"
            >
              Đăng ký dùng thử
            </Link>
          </div>
        </div>
      </section>

      <footer className="grid grid-cols-1 gap-8 border-t border-slate-200 bg-slate-100 px-6 py-14 min-[900px]:grid-cols-4 min-[1024px]:px-12 dark:border-slate-800 dark:bg-slate-950">
        <div>
          <span className="mb-4 block text-lg font-bold">Project CLARA</span>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            Trợ lý lâm sàng cho truy xuất và phân tích bằng chứng.
            <br />
            Tập trung vào câu trả lời có nguồn trích rõ ràng.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <span className="mb-2 text-xs font-bold uppercase tracking-[0.16em]">Luồng cốt lõi</span>
          <span className="text-sm text-slate-600 dark:text-slate-300">Đặt câu hỏi</span>
          <span className="text-sm text-slate-600 dark:text-slate-300">Kiểm tra nguồn trích</span>
          <span className="text-sm text-slate-600 dark:text-slate-300">Nhận tóm tắt để ra quyết định</span>
        </div>

        <div className="flex flex-col gap-2">
          <span className="mb-2 text-xs font-bold uppercase tracking-[0.16em]">Pháp lý</span>
          <Link className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="/legal/terms">
            Điều khoản sử dụng
          </Link>
          <Link className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="/legal/privacy">
            Chính sách quyền riêng tư
          </Link>
          <Link className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="/legal/consent">
            Đồng thuận y tế
          </Link>
          <Link className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="/legal/cookies">
            Chính sách cookie
          </Link>
        </div>

        <div className="flex flex-col gap-2">
          <span className="mb-2 text-xs font-bold uppercase tracking-[0.16em]">Liên hệ</span>
          <a className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="mailto:clara@thiennn.icu">
            clara@thiennn.icu
          </a>
          <a className="text-sm text-slate-600 hover:text-cyan-700 dark:text-slate-300 dark:hover:text-cyan-300" href="tel:0853374247">
            0853374247
          </a>
          <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
            <span className="text-xs text-slate-500 dark:text-slate-400">© 2026 Project CLARA. Bảo lưu mọi quyền.</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
