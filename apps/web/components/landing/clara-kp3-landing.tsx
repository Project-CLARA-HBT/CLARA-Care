import Link from "next/link";

import LandingFaqAccordion from "@/components/landing/landing-faq-accordion";
import {
  FAQ_ITEMS,
  FINAL_CTA,
  HERO_METRICS,
  MODEL_STEPS,
  OFFICES,
  OPEN_LETTER_PARAGRAPHS,
  PARTNER_STRIP,
  SERVICE_CARDS,
  TESTIMONIALS,
} from "@/components/landing/clara-kp3-data";

function SectionContainer({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`mx-auto w-full max-w-[1480px] px-4 min-[641px]:max-[1024px]:px-7 min-[1025px]:max-[1535px]:px-10 min-[1536px]:px-14 ${className}`}
    >
      {children}
    </section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-center text-xs font-semibold uppercase tracking-[0.14em] text-blue-300/95 md:text-xs">{children}</p>
  );
}

function StarIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="clara-star-icon h-3.5 w-3.5 fill-current">
      <path d="M10 1.8 12.5 7l5.7.8-4.1 4 1 5.7L10 14.7l-5.1 2.8 1-5.7-4.1-4L7.5 7 10 1.8Z" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-[0.8em] w-[0.8em] fill-current">
      <path d="M6.5 4.8c0-1 1.08-1.62 1.95-1.12l11 6.2c.89.5.89 1.77 0 2.28l-11 6.2A1.3 1.3 0 0 1 6.5 17.2V4.8Z" />
    </svg>
  );
}

function NeonButton({
  href,
  children,
  className = "",
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={`clara-neon-button inline-flex min-h-12 items-center justify-center rounded-xl px-6 py-3 text-center text-sm font-bold uppercase tracking-[0.04em] text-white sm:min-h-14 sm:min-w-[178px] sm:text-base ${className}`}
    >
      {children}
    </Link>
  );
}

function NeonGhostButton({
  href,
  children,
  className = "",
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex min-h-12 items-center justify-center rounded-xl border border-cyan-300/40 bg-[#071839]/72 px-6 py-3 text-center text-sm font-semibold uppercase tracking-[0.06em] text-cyan-100 transition hover:border-cyan-200/65 hover:bg-[#0a1f48] hover:text-white sm:min-h-14 sm:min-w-[178px] sm:text-base ${className}`}
    >
      {children}
    </Link>
  );
}

function RatingPill({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`clara-rating-pill ${className}`}>
      <span className="inline-flex items-center gap-1 text-cyan-200" aria-hidden="true">
        <StarIcon />
        <StarIcon />
        <StarIcon />
        <StarIcon />
        <StarIcon />
      </span>
      <span>{children}</span>
    </p>
  );
}

export default function ClaraKp3Landing() {
  return (
    <main className="clara-shell relative overflow-hidden text-slate-100">
      <div className="clara-grid-overlay pointer-events-none absolute inset-0 opacity-60" aria-hidden="true" />
      <div className="clara-ambient-layers pointer-events-none absolute inset-0" aria-hidden="true" />

      <SectionContainer className="relative z-30 pt-6">
        <header className="clara-nav-frame sticky top-3 z-30 flex flex-col gap-3 rounded-[2rem] border border-blue-400/25 bg-[#07122a]/84 px-4 py-3 backdrop-blur-xl min-[641px]:max-[1024px]:flex-row min-[641px]:max-[1024px]:items-center min-[641px]:max-[1024px]:justify-between min-[1025px]:max-[1535px]:flex-row min-[1025px]:max-[1535px]:items-center min-[1025px]:max-[1535px]:justify-between min-[1025px]:max-[1535px]:px-6 min-[1025px]:max-[1535px]:py-4 min-[1536px]:flex-row min-[1536px]:items-center min-[1536px]:justify-between min-[1536px]:px-8 min-[1536px]:py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-200">CLARA.CARE</p>
            <p className="text-sm text-slate-300">Clinical Agent for Retrieval & Analysis</p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 text-xs font-semibold min-[641px]:max-[1024px]:w-auto min-[641px]:max-[1024px]:text-sm min-[1025px]:max-[1535px]:w-auto min-[1025px]:max-[1535px]:gap-3 min-[1025px]:max-[1535px]:text-sm min-[1536px]:w-auto min-[1536px]:gap-4">
            <Link href="/huong-dan" className="clara-nav-link rounded-lg border border-blue-300/30 px-3 py-2 text-blue-100 hover:bg-blue-500/10">
              Hướng dẫn
            </Link>
            <Link href="/research" className="clara-nav-link rounded-lg border border-blue-300/30 px-3 py-2 text-blue-100 hover:bg-blue-500/10">
              CLARA Research
            </Link>
            <Link href="/council" className="clara-nav-link rounded-lg border border-blue-300/30 px-3 py-2 text-blue-100 hover:bg-blue-500/10">
              Hội chẩn AI
            </Link>
            <Link href="/selfmed" className="clara-nav-link rounded-lg border border-blue-300/30 px-3 py-2 text-blue-100 hover:bg-blue-500/10">
              CLARA Self-Med
            </Link>
            <Link href="/careguard" className="clara-nav-link rounded-lg border border-blue-300/30 px-3 py-2 text-blue-100 hover:bg-blue-500/10">
              CareGuard
            </Link>
            <NeonButton href="/register">Bắt đầu miễn phí</NeonButton>
          </div>
        </header>
      </SectionContainer>

      <SectionContainer className="relative z-10 mt-5 pb-12 min-[641px]:max-[1024px]:mt-8 min-[641px]:max-[1024px]:pb-16 min-[1025px]:max-[1535px]:mt-10 min-[1025px]:max-[1535px]:pb-24 min-[1536px]:mt-12 min-[1536px]:pb-28">
        <article className="clara-wave-top clara-hero-panel relative overflow-hidden rounded-[1.5rem] border border-blue-300/20 px-4 py-8 min-[641px]:max-[1024px]:rounded-[2rem] min-[641px]:max-[1024px]:px-8 min-[641px]:max-[1024px]:py-14 min-[1025px]:max-[1535px]:px-12 min-[1025px]:max-[1535px]:py-20 min-[1536px]:rounded-[2.5rem] min-[1536px]:px-16 min-[1536px]:py-24">
          <div className="clara-hero-constellation" aria-hidden="true">
            <span className="clara-const-node clara-const-node-a" />
            <span className="clara-const-node clara-const-node-b" />
            <span className="clara-const-node clara-const-node-c" />
            <span className="clara-const-node clara-const-node-d" />
            <span className="clara-const-link clara-const-link-a" />
            <span className="clara-const-link clara-const-link-b" />
          </div>
          <div className="mx-auto max-w-5xl text-center">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-200">Hệ sinh thái AI y tế có kiểm soát</p>
            <h1 className="clara-display-title mt-4 text-[2.6rem] font-black uppercase text-white min-[641px]:max-[1024px]:text-[4.8rem] min-[1025px]:max-[1535px]:text-[6.7rem] min-[1536px]:text-[8.4rem]">
              AI Y TẾ
              <br />
              <span className="clara-neon-text">HIỆU SUẤT CAO</span>
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-[0.95rem] leading-7 text-slate-200 min-[641px]:max-[1024px]:text-[1.05rem] min-[641px]:max-[1024px]:leading-8 min-[1025px]:max-[1535px]:max-w-4xl min-[1025px]:max-[1535px]:text-[1.15rem] min-[1025px]:max-[1535px]:leading-8 min-[1536px]:text-xl min-[1536px]:leading-9">
              Một nền tảng duy nhất cho toàn bộ vòng đời quyết định: hỏi đáp có citation, hội chẩn đa chuyên khoa, quản lý tủ thuốc,
              kiểm tra tương tác DDI, medical scribe và control tower vận hành.
            </p>

            <div className="clara-cta-panel mx-auto mt-8 flex w-full max-w-[980px] flex-col gap-3 rounded-2xl border border-blue-200/20 bg-[#091431]/80 p-3 min-[641px]:max-[1024px]:flex-row min-[641px]:max-[1024px]:items-center min-[1025px]:max-[1535px]:p-4 min-[1536px]:p-5">
              <input
                className="h-[52px] flex-1 rounded-xl border border-blue-200/25 bg-white/95 px-4 text-sm text-slate-900 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-blue-400 min-[641px]:max-[1024px]:h-14 min-[641px]:max-[1024px]:text-base min-[1025px]:max-[1535px]:h-16 min-[1025px]:max-[1535px]:px-5 min-[1025px]:max-[1535px]:text-base min-[1536px]:h-[72px] min-[1536px]:text-lg"
                placeholder="Nhập email để nhận chiến lược triển khai CLARA"
                aria-label="Email nhận chiến lược"
              />
              <div className="flex w-full flex-col gap-2 min-[641px]:max-[1024px]:w-auto min-[1025px]:max-[1535px]:w-auto">
                <NeonButton href="/register" className="min-[641px]:max-[1024px]:w-auto min-[1025px]:max-[1535px]:px-8 min-[1536px]:px-10">
                  Bắt đầu miễn phí
                </NeonButton>
                <NeonGhostButton href="/research" className="min-[641px]:max-[1024px]:min-h-12 min-[641px]:max-[1024px]:text-sm">
                  Dùng thử ngay
                </NeonGhostButton>
              </div>
            </div>

            <RatingPill>4.8/5 từ nhóm dùng thử nội bộ và đối tác đào tạo y khoa</RatingPill>
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-100/90">
              Không cần tích hợp phức tạp. Khởi tạo pilot trong 7 ngày.
            </p>
          </div>

          <div className="mt-10 grid gap-3 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-4 min-[1536px]:grid-cols-4 min-[1536px]:gap-5">
            {HERO_METRICS.map((item) => (
              <div key={item.label} className="clara-kpi-card clara-glass-panel rounded-2xl border border-blue-300/25 bg-[#091431]/88 p-4 text-left min-h-[116px] min-[641px]:max-[1024px]:min-h-[138px] min-[1025px]:max-[1535px]:min-h-[152px] min-[1536px]:min-h-[168px] md:p-5">
                <p className="text-3xl font-black text-white">{item.value}</p>
                <p className="mt-2 text-sm leading-6 text-blue-100/90">{item.label}</p>
              </div>
            ))}
          </div>
        </article>
      </SectionContainer>

      <SectionContainer className="relative z-10 pb-12">
        <article className="clara-dome-panel overflow-hidden rounded-[1.75rem] border border-blue-200/20 bg-[#0b1738] p-3 min-[641px]:max-[1024px]:p-5 min-[1025px]:max-[1535px]:p-8 min-[1536px]:p-10">
          <div className="rounded-2xl border border-blue-200/25 bg-gradient-to-br from-slate-200 to-slate-400 p-3">
            <div className="relative overflow-hidden rounded-xl bg-[#0a142f] p-5">
              <div className="aspect-video rounded-xl border border-blue-300/20 bg-gradient-to-br from-[#0b1f4f] via-[#0c1530] to-[#060a18]" />
              <button
                type="button"
                className="clara-play-button absolute left-1/2 top-1/2 inline-flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-2xl bg-blue-500/85 text-2xl font-bold text-white shadow-[0_10px_40px_rgba(59,130,246,0.65)] min-[641px]:max-[1024px]:h-20 min-[641px]:max-[1024px]:w-20 min-[641px]:max-[1024px]:text-3xl min-[1025px]:max-[1535px]:h-24 min-[1025px]:max-[1535px]:w-24 min-[1025px]:max-[1535px]:text-4xl min-[1536px]:h-28 min-[1536px]:w-28 min-[1536px]:text-5xl"
                aria-label="Xem video demo CLARA"
              >
                <PlayIcon />
              </button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-lg font-semibold text-blue-100/85">
            {PARTNER_STRIP.map((item) => (
              <span key={item} className="opacity-90">
                {item}
              </span>
            ))}
          </div>
        </article>
      </SectionContainer>

      <section className="clara-section relative z-10 mt-4 bg-transparent text-slate-100">
        <SectionContainer>
          <article className="clara-glass-panel mx-auto max-w-4xl rounded-[2rem] border border-blue-200/30 bg-[#061530]/86 px-5 py-9 shadow-[0_24px_60px_-40px_rgba(37,99,235,0.55)] min-[641px]:max-[1024px]:px-8 min-[641px]:max-[1024px]:py-12 min-[1025px]:max-[1535px]:max-w-5xl min-[1025px]:max-[1535px]:px-12 min-[1025px]:max-[1535px]:py-16 min-[1536px]:px-14 min-[1536px]:py-20">
            <p className="text-sm font-semibold text-blue-200">Thư ngỏ từ đội ngũ CLARA</p>
            <p className="mt-1 text-sm text-blue-200/80">Việt Nam, 2026</p>
            <div className="my-4 h-1 w-28 rounded bg-gradient-to-r from-cyan-400 to-blue-500" />
            <h2 className="text-2xl font-black uppercase leading-[1.02] text-white min-[641px]:max-[1024px]:text-4xl min-[1025px]:max-[1535px]:text-5xl min-[1536px]:text-6xl">
              Chúng ta không thiếu thông tin y tế. Chúng ta thiếu một hệ thống an toàn để quyết định.
            </h2>

            <div className="clara-copy-rhythm mt-6 space-y-5 text-slate-200">
              {OPEN_LETTER_PARAGRAPHS.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>

            <div className="mt-8 rounded-xl border border-cyan-300/35 bg-[#0a234a]/66 p-4 text-sm leading-7 text-cyan-100">
              <p className="font-bold uppercase tracking-[0.1em]">Tuyên ngôn vận hành CLARA</p>
              <ul className="mt-3 space-y-2">
                <li className="clara-medical-bullet">Không thay thế phán đoán chuyên môn của bác sĩ.</li>
                <li className="clara-medical-bullet">Không đưa khuyến nghị nguy cơ cao nếu không đủ bằng chứng.</li>
                <li className="clara-medical-bullet">Không bỏ qua bảo mật dữ liệu sức khỏe cá nhân.</li>
              </ul>
            </div>

            <p className="mt-6 text-base font-semibold text-slate-100">Thân mến,</p>
            <p className="text-base text-slate-300">Nhóm sáng lập CLARA</p>
          </article>
        </SectionContainer>
      </section>

      <SectionContainer className="clara-section relative z-10">
        <SectionLabel>Chúng tôi cung cấp</SectionLabel>
        <div className="mt-5 grid gap-5 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-3 min-[1536px]:grid-cols-3">
          {SERVICE_CARDS.map((card) => (
            <article key={card.title} className="clara-dark-card clara-card-equal flex h-full flex-col rounded-[1.75rem] p-6 lg:p-7">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-200">{card.tag}</p>
              <h3 className="mt-3 text-4xl font-black uppercase leading-none text-white min-[641px]:max-[1024px]:text-5xl min-[1025px]:max-[1535px]:text-5xl min-[1536px]:text-6xl">{card.title}</h3>
              <p className="mt-4 text-base leading-8 text-slate-300">{card.description}</p>
              <ul className="mt-4 flex-1 space-y-2 text-sm text-blue-100/95">
                {card.bullets.map((bullet) => (
                  <li key={bullet} className="rounded-lg border border-blue-200/20 bg-blue-500/10 px-3 py-2">
                    {bullet}
                  </li>
                ))}
              </ul>
              <div className="mt-auto pt-6">
                <NeonButton href={card.href}>{card.cta}</NeonButton>
              </div>
            </article>
          ))}
        </div>
      </SectionContainer>

      <section className="clara-section-strong relative z-10 bg-[#040916]">
        <SectionContainer>
          <SectionLabel>CLARA RUNTIME OPERATING MODEL</SectionLabel>
          <h2 className="clara-sub-display mx-auto mt-3 max-w-5xl text-center font-black uppercase text-white">
            Từ trải nghiệm người dùng đến vận hành admin đều nối thành một flow
          </h2>
          <p className="clara-copy-rhythm mx-auto mt-6 max-w-4xl text-center text-slate-300">
            Codebase hiện tại đã tách rõ luồng theo nhiệm vụ: intake, retrieve, verify, council workspace, DDI guard,
            và control tower để kiểm soát chất lượng khi scale.
          </p>

          <div className="mt-8 grid gap-4 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-4 min-[1536px]:grid-cols-4">
            {MODEL_STEPS.map((step) => (
              <article key={step.title} className="clara-model-card relative overflow-hidden rounded-[1.5rem] p-5">
                <p className="text-6xl font-black text-blue-200/25">{step.index}</p>
                <h3 className="mt-2 text-3xl font-black uppercase text-white">{step.title}</h3>
                <p className="mt-2 text-sm font-semibold uppercase tracking-[0.12em] text-cyan-300">{step.subtitle}</p>
                <ul className="mt-4 space-y-2 text-sm leading-7 text-slate-200">
                  {step.points.map((point) => (
                    <li key={point} className="clara-medical-bullet">{point}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </SectionContainer>
      </section>

      <section className="clara-section-strong relative z-10">
        <SectionContainer>
          <article className="rounded-[2rem] border border-blue-200/20 bg-[#050e24] p-6 text-center sm:p-10">
            <h2 className="clara-display-title font-black uppercase text-white">
              Một Nền Tảng
              <br />
              Nhiều Workflow Y Tế
            </h2>
            <p className="clara-copy-rhythm mx-auto mt-6 max-w-4xl text-slate-300">
              Từ đội lâm sàng đến đội triển khai AI, tất cả dùng chung một logic vận hành. Điều này giúp tăng tốc go-live,
              giảm rủi ro rollout và giữ được traceability khi hệ thống mở rộng.
            </p>

            <div className="mt-8 grid gap-3 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-4 min-[1536px]:grid-cols-4">
              <div className="clara-stat-card clara-glass-panel rounded-2xl border border-blue-200/20 bg-[#081833] p-4 text-left">
                <p className="text-sm text-blue-200">Research Workspace</p>
                <p className="mt-2 text-5xl font-black text-white">5 Tabs</p>
              </div>
              <div className="clara-stat-card clara-glass-panel rounded-2xl border border-blue-200/20 bg-[#081833] p-4 text-left">
                <p className="text-sm text-blue-200">Council Workspace</p>
                <p className="mt-2 text-5xl font-black text-white">5 Tabs</p>
              </div>
              <div className="clara-stat-card clara-glass-panel rounded-2xl border border-blue-200/20 bg-[#081833] p-4 text-left">
                <p className="text-sm text-blue-200">Control Tower</p>
                <p className="mt-2 text-5xl font-black text-white">6 Panels</p>
              </div>
              <div className="clara-stat-card clara-glass-panel rounded-2xl border border-blue-200/20 bg-[#081833] p-4 text-left">
                <p className="text-sm text-blue-200">Drug Safety</p>
                <p className="mt-2 text-5xl font-black text-white">DDI</p>
              </div>
            </div>
          </article>
        </SectionContainer>
      </section>

      <section className="clara-section-strong relative z-10 bg-[#02060f]">
        <SectionContainer>
          <article className="mx-auto max-w-4xl">
            <SectionLabel>Lời cam kết của CLARA</SectionLabel>
            <h2 className="clara-sub-display mt-3 text-center font-black uppercase text-white">
              Chấm dứt kiểu AI trả lời mơ hồ trong y tế
            </h2>
            <div className="clara-copy-rhythm mt-8 rounded-3xl border border-blue-300/20 bg-[#07142e]/85 p-6 text-left text-slate-200">
              <p>
                Nếu hệ thống không đủ bằng chứng để đưa ra khuyến nghị an toàn, CLARA phải nói rõ giới hạn, gắn cờ rủi ro
                và chuyển hướng người dùng đến lựa chọn chăm sóc phù hợp hơn.
              </p>
              <ul className="mt-4 space-y-2">
                <li className="clara-medical-bullet">Hoặc bạn nhận được khuyến nghị có citation, có mức tin cậy.</li>
                <li className="clara-medical-bullet">Hoặc bạn nhận được cảnh báo rõ vì dữ liệu chưa đủ.</li>
                <li className="clara-medical-bullet">Không có lựa chọn thứ ba kiểu khẳng định chắc chắn khi thiếu bằng chứng.</li>
              </ul>
              <div className="clara-cta-stack mt-6 text-center">
                <NeonButton href="/register">60 phút tư vấn chiến lược miễn phí</NeonButton>
                <RatingPill className="text-blue-200/90">4.8 sao từ vòng dùng thử</RatingPill>
              </div>
            </div>
          </article>
        </SectionContainer>
      </section>

      <SectionContainer className="clara-section relative z-10">
        <SectionLabel>Đối tác và người dùng nói gì về CLARA</SectionLabel>
        <div className="mt-6 grid gap-4 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-3 min-[1536px]:grid-cols-3">
          {TESTIMONIALS.map((testimonial) => (
            <article key={testimonial.name} className="clara-dark-card clara-card-equal flex h-full flex-col rounded-3xl p-5 md:p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-bold text-white">{testimonial.name}</p>
                  <p className="text-sm text-blue-200">{testimonial.role}</p>
                </div>
                <span className="rounded-full border border-blue-300/30 bg-blue-500/15 px-3 py-1 text-xs font-semibold text-blue-100">
                  {testimonial.channel}
                </span>
              </div>
              <p className="mt-4 flex-1 text-sm leading-7 text-slate-300">{testimonial.quote}</p>
            </article>
          ))}
        </div>
      </SectionContainer>

      <section className="clara-section clara-medical-band relative z-10">
        <SectionContainer>
          <article className="clara-medical-panel mx-auto max-w-5xl overflow-hidden rounded-[2rem] border border-cyan-200/40 px-6 py-9 sm:px-10 sm:py-12">
            <div className="grid items-center gap-8 min-[1025px]:grid-cols-[0.95fr_1.05fr]">
              <div className="clara-medical-visual order-2 mx-auto min-[1025px]:order-1" aria-hidden="true">
                <span className="clara-med-core" />
                <span className="clara-med-ring clara-med-ring-a" />
                <span className="clara-med-ring clara-med-ring-b" />
                <span className="clara-med-cross" />
                <span className="clara-med-node clara-med-node-a" />
                <span className="clara-med-node clara-med-node-b" />
                <span className="clara-med-node clara-med-node-c" />
                <span className="clara-med-node clara-med-node-d" />
              </div>

              <div className="order-1 text-center min-[1025px]:order-2 min-[1025px]:text-left">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">Clinical Safety System</p>
                <h2 className="clara-sub-display clara-med-heading mt-3 font-black">
                  Bạn đã quá mệt với những lời hứa suông trong health AI?
                </h2>
                <p className="clara-copy-rhythm clara-med-copy mt-6">
                  CLARA được xây cho bối cảnh thực hành: quản lý thuốc tại gia đình, truy xuất bằng chứng cho học thuật,
                  hỗ trợ ghi chép lâm sàng và giám sát vận hành theo chuẩn kiểm toán.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2 min-[1025px]:justify-start">
                  <span className="clara-med-tag">Drug Safety Graph</span>
                  <span className="clara-med-tag">Evidence Routing</span>
                  <span className="clara-med-tag">Policy Guardrails</span>
                </div>
              </div>
            </div>
          </article>
        </SectionContainer>
      </section>

      <section className="clara-section clara-medical-band-soft relative z-10">
        <SectionContainer>
          <article className="clara-medical-card mx-auto max-w-4xl rounded-[2rem] border border-cyan-200/40 px-6 py-10 shadow-[0_24px_60px_-40px_rgba(37,99,235,0.45)] sm:px-10">
            <div className="clara-data-orbit mx-auto" aria-hidden="true">
              <span className="clara-data-orbit-core" />
              <span className="clara-data-orbit-link clara-data-orbit-link-a" />
              <span className="clara-data-orbit-link clara-data-orbit-link-b" />
              <span className="clara-data-orbit-link clara-data-orbit-link-c" />
            </div>
            <h2 className="clara-sub-display clara-med-heading mt-5 text-center font-black">
              Trải nghiệm CLARA pilot,
              <br />
              đo hiệu quả, giảm rủi ro
            </h2>
            <div className="clara-copy-rhythm clara-med-copy mt-6 space-y-4">
              <p>
                CLARA triển khai theo nguyên tắc có kiểm soát: xác định mục tiêu, đo KPI, theo dõi alert và chỉ mở
                rộng khi chất lượng phản hồi ổn định.
              </p>
              <p>
                Nếu bạn đang quản lý nhóm bệnh mạn tính, chương trình đào tạo y khoa, hoặc phòng khám ngoại trú, CLARA
                giúp chuẩn hóa workflow bằng chứng ngay từ giai đoạn đầu.
              </p>
              <p className="font-semibold">
                Bạn không cần thay đổi toàn bộ hệ thống trong ngày một ngày hai. Bắt đầu từ một use-case quan trọng
                nhất, rồi mở rộng theo dữ liệu thực tế.
              </p>
            </div>
            <div className="mt-6 grid gap-2 text-center sm:grid-cols-3">
              <span className="clara-med-tag">PubMed x ClinicalTrials</span>
              <span className="clara-med-tag">WHO ICD-11 x Bộ Y tế</span>
              <span className="clara-med-tag">openFDA x DI & ADR</span>
            </div>
            <div className="clara-cta-stack mt-7 text-center">
              <NeonButton href="/register">60 phút tư vấn chiến lược miễn phí</NeonButton>
              <RatingPill className="text-cyan-100">4.8 sao từ cộng đồng dùng thử</RatingPill>
            </div>
          </article>
        </SectionContainer>
      </section>
      <section className="clara-section relative z-10">
        <SectionContainer>
          <article className="clara-dome-panel overflow-hidden rounded-[2rem] border border-blue-200/20 px-6 py-10 sm:px-10">
            <SectionLabel>Chia sẻ tri thức, nâng chuẩn thực hành</SectionLabel>
            <h2 className="clara-sub-display mt-3 text-center font-black uppercase text-white">
              CLARA Product Walkthrough
            </h2>
            <p className="clara-copy-rhythm mx-auto mt-5 max-w-4xl text-center text-slate-300">
              Chuỗi nội dung demo theo module thật trong sản phẩm: Research, Council, SelfMed, CareGuard, Scribe và
              Admin Control Tower. Tập trung vào workflow và giá trị triển khai thực tế.
            </p>

            <div className="mx-auto mt-8 max-w-4xl rounded-2xl border border-blue-200/25 bg-[#091431]/85 p-4">
              <div className="aspect-video rounded-xl border border-blue-300/20 bg-gradient-to-br from-[#102657] via-[#0c1530] to-[#060a18]" />
            </div>
          </article>
        </SectionContainer>
      </section>

      <section className="clara-section-strong relative z-10 bg-[#061231]">
        <SectionContainer>
          <SectionLabel>Giải đáp mọi thắc mắc của bạn</SectionLabel>
          <h2 className="clara-sub-display mx-auto mt-3 max-w-4xl text-center font-black uppercase text-white">
            FAQ triển khai CLARA
          </h2>
          <div className="mx-auto mt-8 max-w-5xl">
            <LandingFaqAccordion items={FAQ_ITEMS} />
          </div>
        </SectionContainer>
      </section>

      <section className="clara-section relative z-10">
        <SectionContainer>
          <SectionLabel>Our Offices</SectionLabel>
          <h2 className="clara-sub-display mx-auto mt-3 max-w-4xl text-center font-black uppercase text-white">
            Chúng tôi hoạt động đa điểm
          </h2>
          <div className="mt-8 grid gap-4 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-4 min-[1536px]:grid-cols-4">
            {OFFICES.map((office) => (
              <article key={office.city} className="clara-glass-panel flex h-full min-h-[180px] flex-col rounded-3xl border border-blue-300/20 bg-[#081833]/90 p-5 text-center min-[641px]:max-[1024px]:min-h-[210px] min-[1025px]:max-[1535px]:min-h-[240px] min-[1536px]:min-h-[260px]">
                <p className="text-3xl font-black text-blue-200">{office.city}</p>
                <p className="mt-3 flex-1 text-sm leading-7 text-slate-300">{office.detail}</p>
              </article>
            ))}
          </div>
        </SectionContainer>
      </section>

      <SectionContainer className="relative z-10 pb-14">
        <article className="clara-final-cta-panel rounded-[2rem] border border-blue-300/25 bg-[#07142e] p-7 sm:p-10">
          <h2 className="clara-sub-display text-center font-black uppercase text-white">{FINAL_CTA.heading}</h2>
          <p className="clara-copy-rhythm mx-auto mt-5 max-w-4xl text-center text-slate-300">{FINAL_CTA.subheading}</p>

          <div className="clara-cta-stack mt-7 text-center">
            <NeonButton href={FINAL_CTA.href}>{FINAL_CTA.button}</NeonButton>
            <p className="text-sm text-blue-100/80">Email: clara@thiennn.icu · Hotline: 0853374247</p>
          </div>

          <footer className="mt-10 grid gap-5 border-t border-blue-300/20 pt-6 text-sm text-slate-300 min-[641px]:max-[1024px]:grid-cols-2 min-[1025px]:max-[1535px]:grid-cols-4 min-[1536px]:grid-cols-4">
            <div className="min-[1025px]:max-[1535px]:col-span-2 min-[1536px]:col-span-2">
              <p className="text-2xl font-black text-white">CLARA.CARE</p>
              <p className="mt-3 leading-7">
                Hệ sinh thái AI y tế đa mô-đun cho Research, Council, Self-Med, CareGuard, Medical Scribe và Control Tower.
                Định hướng: hỗ trợ quyết định dựa trên bằng chứng, không thay thế chuyên môn lâm sàng.
              </p>
            </div>
            <div>
              <p className="font-semibold uppercase tracking-[0.12em] text-blue-200">Điều hướng</p>
              <ul className="mt-3 space-y-2">
                <li>
                  <Link href="/research" className="hover:text-white">CLARA Research</Link>
                </li>
                <li>
                  <Link href="/council/new" className="hover:text-white">Hội chẩn AI</Link>
                </li>
                <li>
                  <Link href="/selfmed" className="hover:text-white">CLARA Self-Med</Link>
                </li>
                <li>
                  <Link href="/careguard" className="hover:text-white">CareGuard DDI</Link>
                </li>
                <li>
                  <Link href="/scribe" className="hover:text-white">Medical Scribe</Link>
                </li>
                <li>
                  <Link href="/admin/overview" className="hover:text-white">Control Tower</Link>
                </li>
                <li>
                  <Link href="/huong-dan" className="hover:text-white">Hướng dẫn</Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="font-semibold uppercase tracking-[0.12em] text-blue-200">Liên hệ nhanh</p>
              <p className="mt-3 leading-7">Toà P3 Pavilion, Vinhomes Ocean Park 1, Gia Lâm, HN</p>
              <p className="mt-2 leading-7">Toà S2.18, phân khu Sapphire, Vinhomes Ocean Park 1, quận Gia Lâm, TP Hà Nội</p>
              <p className="mt-2 leading-7">Toà E5, Khu đô thị Ciputra, Phú Thượng, Hà Nội</p>
              <p className="mt-2 leading-7">Toà CT3, Chung cư Aranya, đường Dương Khuê, TP Huế</p>
            </div>
          </footer>
        </article>
      </SectionContainer>

      <div className="fixed bottom-5 right-5 z-40">
        <Link
          href="/register"
          className="inline-flex items-center rounded-full border border-cyan-300/45 bg-blue-600/92 px-4 py-2 text-sm font-bold text-white shadow-[0_16px_38px_-20px_rgba(37,99,235,0.9)] transition hover:-translate-y-0.5 hover:brightness-110"
        >
          Đặt lịch demo CLARA
        </Link>
      </div>
    </main>
  );
}
