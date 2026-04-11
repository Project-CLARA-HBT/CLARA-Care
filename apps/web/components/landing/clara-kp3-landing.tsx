import Image from "next/image";
import Link from "next/link";

import { SPONSORS } from "@/components/landing/clara-kp3-data";

const MODULES = [
  {
    title: "Council",
    description: "Hội chẩn đa chuyên khoa theo thời gian thực, có tổng hợp đồng thuận và điểm còn khác biệt.",
    icon: "groups",
    href: "/council/new",
    cta: "Mở Council",
  },
  {
    title: "Self-Med",
    description: "Theo dõi lịch dùng thuốc cá nhân, nhắc liều và phát hiện tương tác đáng lưu ý.",
    icon: "medication",
    href: "/selfmed",
    cta: "Mở Self-Med",
  },
  {
    title: "CareGuard",
    description: "Giám sát an toàn dùng thuốc, phân tầng rủi ro và cảnh báo sớm các tình huống cần chú ý.",
    icon: "shield",
    href: "/careguard",
    cta: "Mở CareGuard",
  },
  {
    title: "Scribe",
    description: "Chuẩn hóa ghi chú lâm sàng, tóm tắt ca và hỗ trợ bàn giao sau mỗi lượt khám.",
    icon: "fa fa-pencil-square-o",
    href: "/scribe",
    cta: "Mở Scribe",
  },
] as const;

const TESTIMONIALS = [
  {
    quote:
      "CLARA giúp tôi rút ngắn đáng kể thời gian tra cứu khi chuẩn bị hội chẩn cho các ca lâm sàng phức tạp.",
    name: "BS. Nguyễn Minh Tuấn",
    role: "Trưởng khoa Nội tiết",
  },
  {
    quote:
      "Là sinh viên, tôi dùng CLARA để tự học mỗi ngày. Cách hệ thống bóc tách dữ liệu giúp tôi hiểu sâu hơn về tương tác thuốc.",
    name: "Trần Lê Vy",
    role: "Sinh viên Y6",
  },
  {
    quote:
      "Research và Scribe phối hợp rất liền mạch, tôi vừa ghi chú vừa tra cứu mà không bị đứt mạch làm việc.",
    name: "Lê Hoàng Nam",
    role: "Trợ lý nghiên cứu",
  },
] as const;

const FAQS = [
  {
    q: "CLARA có thay thế quyết định bác sĩ không?",
    a: "Không. CLARA là hệ thống hỗ trợ tham khảo lâm sàng; quyết định điều trị cuối cùng luôn thuộc về đội ngũ chuyên môn.",
  },
  {
    q: "Dữ liệu bệnh nhân có được bảo mật không?",
    a: "Có. Hệ thống áp dụng guardrail vận hành, kiểm soát truy cập theo vai trò và ghi nhận audit log để bảo vệ dữ liệu.",
  },
  {
    q: "Làm sao để kiểm chứng thông tin AI đưa ra?",
    a: "Mỗi luận điểm đều đi kèm trích dẫn từ nguồn y khoa phù hợp để bạn đối chiếu nhanh trước khi áp dụng.",
  },
] as const;

export default function ClaraKp3Landing() {
  return (
    <>
      <style>{`
        .material-symbols-outlined {
          font-variation-settings: 'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 24;
        }

        .glass-panel {
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          background: rgba(255, 255, 255, 0.62);
          border: 1px solid rgba(148, 163, 184, 0.28);
          box-shadow: 0 8px 32px rgba(2, 6, 23, 0.08);
        }

        .dark .glass-panel {
          background: rgba(15, 23, 42, 0.45);
          border: 1px solid rgba(56, 189, 248, 0.24);
        }

        .cyber-grid {
          background-image: linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px);
          background-size: 40px 40px;
        }

        .data-stream {
          position: absolute;
          background: linear-gradient(to bottom, transparent, #22d3ee, transparent);
          width: 1px;
          height: 100px;
          animation: flow 3s linear infinite;
        }

        @keyframes flow {
          from {
            top: -100px;
            opacity: 0;
          }
          50% {
            opacity: 1;
          }
          to {
            top: 100%;
            opacity: 0;
          }
        }

        .neural-pulse {
          animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        .glow-cyan {
          filter: drop-shadow(0 0 8px rgba(0, 218, 243, 0.42));
        }

        .module-blade {
          position: relative;
          overflow: hidden;
          transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .module-blade::after {
          content: "";
          position: absolute;
          top: 0;
          left: 0;
          width: 2px;
          height: 100%;
          background: #00daf3;
          transform: scaleY(0);
          transition: transform 0.3s ease;
        }

        .module-blade:hover::after {
          transform: scaleY(1);
        }

        @keyframes pulse {
          0%,
          100% {
            opacity: 0.3;
            transform: scale(1);
          }
          50% {
            opacity: 0.7;
            transform: scale(1.05);
          }
        }
      `}</style>

      <main className="cyber-grid overflow-x-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <nav className="glass-panel fixed top-0 z-[100] flex w-full items-center justify-between border-b border-slate-200/45 px-4 py-3 min-[1024px]:px-8 dark:border-slate-700/45">
          <div className="flex items-center gap-3">
            <div className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-lg bg-slate-900 text-base font-bold text-white dark:bg-cyan-400 dark:text-slate-950">
              C
            </div>
            <div className="text-xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
              The <span className="text-cyan-600 dark:text-cyan-300">Clara Care</span>
            </div>
          </div>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="glow-cyan inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300" href="#engine">
              <span className="material-symbols-outlined text-sm">memory</span>
              Lõi AI
            </a>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#modules">
              <span className="material-symbols-outlined text-sm">widgets</span>
              Mô-đun
            </a>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#workflow">
              <span className="material-symbols-outlined text-sm">account_tree</span>
              Quy trình
            </a>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#faq">
              <span className="material-symbols-outlined text-sm">help</span>
              FAQ
            </a>
          </div>

          <Link
            href="/research"
            className="rounded-md border border-slate-900/20 bg-slate-900 px-5 py-2 text-sm font-bold text-white transition-all hover:bg-slate-800 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
          >
            <span className="material-symbols-outlined mr-1 align-[-3px] text-base">rocket_launch</span>
            Mở Workspace CLARA
          </Link>
        </nav>

        <section className="relative mx-auto max-w-7xl px-4 pb-14 pt-28 min-[1024px]:px-8 min-[1024px]:pb-20 min-[1024px]:pt-36">
          <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-30">
            <div className="data-stream left-1/4" style={{ animationDelay: "0s" }} />
            <div className="data-stream left-1/3" style={{ animationDelay: "1.5s" }} />
            <div className="data-stream left-2/3" style={{ animationDelay: "0.7s" }} />
            <div className="data-stream left-3/4" style={{ animationDelay: "2.2s" }} />
          </div>

          <div className="relative z-10 flex flex-col gap-10 min-[1120px]:flex-row min-[1120px]:items-stretch min-[1120px]:gap-12">
            <div className="w-full space-y-6 min-[1120px]:w-[44%] min-[1280px]:w-[41%]">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-100/65 px-3 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-cyan-800 dark:border-cyan-700/50 dark:bg-cyan-900/35 dark:text-cyan-200">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                AI y khoa thế hệ mới
              </div>

              <h1 className="max-w-[19ch] text-[2.6rem] font-black leading-[0.95] tracking-tight text-slate-900 min-[640px]:text-[3.6rem] min-[1280px]:text-[4.5rem] dark:text-slate-100">
                Đặt câu hỏi đúng trọng tâm.
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">Luôn có nguồn dẫn minh bạch.</span>
                <br />
                Ra quyết định tự tin hơn.
              </h1>

              <p className="max-w-[62ch] text-base font-medium leading-relaxed text-slate-600 min-[1280px]:text-lg dark:text-slate-300">
                Bắt đầu từ Research để thu thập bằng chứng kèm trích dẫn rõ ràng, rồi chuyển mượt sang Council, Self-Med,
                CareGuard, Scribe và Control Tower trong một hành trình lâm sàng thống nhất.
              </p>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/research"
                  className="group inline-flex items-center gap-2 rounded-xl bg-slate-900 px-8 py-4 text-base font-black text-white transition-all hover:bg-slate-800 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
                >
                  Bắt đầu với Research
                  <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">arrow_forward</span>
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-8 py-4 text-base font-black text-slate-900 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="material-symbols-outlined text-base">person_add</span>
                  Đăng ký dùng thử
                </Link>
              </div>

              <div className="grid grid-cols-2 gap-6 border-t border-slate-300/45 pt-8 dark:border-slate-700/45">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-cyan-700 dark:text-cyan-300">
                    <span className="material-symbols-outlined text-xs">analytics</span>
                    Truy vết trích dẫn
                  </div>
                  <div className="text-sm font-bold text-slate-700 dark:text-slate-200">Theo từng luận điểm</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-cyan-700 dark:text-cyan-300">
                    <span className="material-symbols-outlined text-xs">timer</span>
                    Độ trễ
                  </div>
                  <div className="text-sm font-bold text-slate-700 dark:text-slate-200">&lt;20 giây phản hồi</div>
                </div>
              </div>
            </div>

            <div className="relative w-full self-start min-[1120px]:w-[56%] min-[1280px]:w-[59%]">
              <div className="absolute -inset-10 rounded-full bg-cyan-300/15 blur-[100px] dark:bg-cyan-700/20" />

              <div className="glass-panel relative overflow-hidden rounded-2xl border border-white/40 p-5 shadow-[0_32px_64px_-12px_rgba(0,31,61,0.2)] dark:border-slate-700/60">
                <div className="mb-4 flex items-center justify-between border-b border-slate-300/35 pb-3 dark:border-slate-700/45">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full bg-red-300/70" />
                      <div className="h-2.5 w-2.5 rounded-full bg-amber-300/70" />
                      <div className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" />
                    </div>
                    <div className="h-4 w-px bg-slate-300 dark:bg-slate-700" />
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                      Hệ lõi v4.2
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-300">PHIÊN ĐANG CHẠY</span>
                    <span className="h-2 w-2 rounded-full bg-cyan-500 dark:bg-cyan-300" />
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="flex justify-between">
                    <div>
                      <div className="text-sm font-black text-slate-900 dark:text-slate-100">CLARA Research</div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                        Ngữ cảnh lâm sàng đang bật
                      </div>
                    </div>
                    <div className="flex h-8 items-end gap-1">
                      <div className="h-4 w-1 rounded-full bg-cyan-300" />
                      <div className="h-6 w-1 animate-bounce rounded-full bg-cyan-500" style={{ animationDelay: "0.1s" }} />
                      <div className="h-8 w-1 rounded-full bg-slate-900 dark:bg-cyan-200" />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[82%] rounded-xl rounded-tr-none border border-slate-300/45 bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                        Amlodipine và Simvastatin có tương tác gì cần lưu ý?
                      </div>
                    </div>

                    <div className="flex justify-start gap-3">
                      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white dark:bg-cyan-400 dark:text-slate-950">
                        <div className="neural-pulse absolute inset-0 rounded-full bg-cyan-300/20 dark:bg-cyan-700/30" />
                        <span className="material-symbols-outlined relative z-10 text-lg">psychology</span>
                      </div>

                      <div className="max-w-[86%] space-y-3">
                        <div className="relative overflow-hidden rounded-2xl rounded-tl-none bg-slate-900 p-4 text-white dark:bg-cyan-700">
                          <div className="absolute right-2 top-1 opacity-20">
                            <span className="material-symbols-outlined text-4xl">neurology</span>
                          </div>
                          <p className="relative z-10 text-sm leading-relaxed">
                            Phối hợp này có thể làm tăng nồng độ Simvastatin trong máu, từ đó làm tăng nguy cơ tiêu cơ vân.
                          </p>
                          <div className="relative z-10 mt-3 flex flex-wrap gap-2 border-t border-white/15 pt-3">
                            <span className="rounded border border-white/20 bg-white/10 px-2 py-1 text-[10px] font-bold">PubMed #28442</span>
                            <span className="rounded border border-white/20 bg-white/10 px-2 py-1 text-[10px] font-bold">openFDA Alert</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <div className="h-1 flex-1 overflow-hidden rounded-full bg-slate-300/40 dark:bg-slate-700/60">
                            <div className="h-full w-[98%] bg-cyan-500 dark:bg-cyan-300" />
                          </div>
                          <span className="text-[10px] font-black uppercase tracking-wider text-cyan-700 dark:text-cyan-300">
                            Độ tin cậy 98%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 rounded-xl border border-slate-300/45 bg-slate-100 p-3 dark:border-slate-700 dark:bg-slate-900">
                    <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">barcode_scanner</span>
                    <div className="flex-1 text-xs font-bold italic text-slate-500 dark:text-slate-400">
                      Đang tổng hợp và kiểm chứng dữ liệu lâm sàng...
                    </div>
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" style={{ animationDelay: "0.2s" }} />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass-panel absolute -right-6 -top-6 hidden w-32 flex-col items-center justify-center rounded-full border border-cyan-300/35 p-4 min-[1200px]:flex">
                <div className="mb-1 text-[10px] font-black uppercase text-cyan-700 dark:text-cyan-300">THỜI GIAN THỰC</div>
                <div className="text-xl font-black text-slate-900 dark:text-slate-100">2.4k</div>
                <div className="text-[9px] font-bold text-slate-500 dark:text-slate-400">Lượt truy vấn/phút</div>
                <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-cyan-200/40 dark:bg-cyan-900/35">
                  <div className="h-full w-3/4 animate-pulse bg-cyan-500 dark:bg-cyan-300" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white/75 py-10 dark:border-slate-800/50 dark:bg-slate-900/55">
          <div className="mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-2 text-center text-[10px] font-black uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
              <span className="material-symbols-outlined mr-1 align-[-3px] text-sm">handshake</span>
              Các đối tác và nhà tài trợ
            </div>
            <div className="mb-8 text-center text-sm font-medium text-slate-600 dark:text-slate-300">
              Hạ tầng và hệ sinh thái đồng hành cùng The Clara Care trong quá trình phát triển.
            </div>
            <div className="grid grid-cols-1 gap-4 min-[900px]:grid-cols-2">
              {SPONSORS.map((sponsor) => (
                <a
                  key={sponsor.name}
                  href={sponsor.href}
                  target="_blank"
                  rel="noreferrer"
                  className="glass-panel flex min-h-[120px] items-center justify-center rounded-2xl border border-slate-200/40 p-4 transition-all hover:-translate-y-0.5 dark:border-slate-700/50"
                >
                  <Image
                    src={sponsor.logo}
                    alt={`${sponsor.name} logo`}
                    width={sponsor.name === "BNIX" ? 260 : 560}
                    height={sponsor.name === "BNIX" ? 78 : 180}
                    className={sponsor.name === "BNIX" ? "h-12 w-auto object-contain" : "h-16 w-auto object-contain"}
                  />
                </a>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-24 min-[1024px]:px-8" id="engine">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-4xl font-black tracking-tight text-slate-900 min-[1024px]:text-5xl dark:text-slate-100">
              Luồng dữ liệu và định tuyến suy luận của CLARA
            </h2>
            <p className="mx-auto max-w-3xl text-base font-medium text-slate-600 dark:text-slate-300">
              Mọi tín hiệu được xử lý qua từng lớp rõ ràng để bạn nắm ngay hệ thống đang phân tích và kiểm chứng như thế nào.
            </p>
          </div>

          <div className="relative grid grid-cols-1 gap-6 min-[900px]:grid-cols-4">
            <div className="pointer-events-none absolute left-0 top-1/2 hidden h-px w-full -translate-y-1/2 bg-gradient-to-r from-transparent via-cyan-300/45 to-transparent min-[900px]:block" />
            {[
              {
                layer: "Tầng 01",
                title: "Đầu vào",
                desc: "Tiếp nhận truy vấn văn bản hoặc dữ liệu cận lâm sàng thô qua kênh được mã hóa.",
                icon: "fa fa-sign-in",
                tone: "text-cyan-700 dark:text-cyan-300",
              },
              {
                layer: "Tầng 02",
                title: "Truy xuất ngữ nghĩa",
                desc: "Phân tích ý định và truy xuất nguồn tin từ các cơ sở dữ liệu y khoa phù hợp.",
                icon: "neurology",
                tone: "text-cyan-200",
                solid: true,
              },
              {
                layer: "Tầng 03",
                title: "Lớp an toàn",
                desc: "Kiểm chứng chéo với chính sách nội bộ và điểm tin cậy trước khi hiển thị.",
                icon: "security",
                tone: "text-red-500",
              },
              {
                layer: "Tầng 04",
                title: "Đầu ra",
                desc: "Trả lời kèm trích dẫn và gợi ý bước tiếp theo theo đúng quy trình thực tế.",
                icon: "output",
                tone: "text-cyan-700 dark:text-cyan-300",
              },
            ].map((step) => (
              <article
                key={step.title}
                className={
                  step.solid
                    ? "relative z-10 rounded-2xl bg-slate-900 p-7 text-white shadow-2xl dark:bg-cyan-800"
                    : "glass-panel relative z-10 rounded-2xl p-7"
                }
              >
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800/60">
                  {step.icon.startsWith("fa ") ? (
                    <i className={`${step.icon} text-2xl ${step.tone}`} aria-hidden="true" />
                  ) : (
                    <span className={`material-symbols-outlined text-2xl ${step.tone}`}>{step.icon}</span>
                  )}
                </div>
                <p className={`mb-1 text-[10px] font-black uppercase tracking-[0.15em] ${step.tone}`}>{step.layer}</p>
                <h3 className="mb-3 text-xl font-black">{step.title}</h3>
                <p className="text-sm leading-relaxed text-slate-300 dark:text-slate-200">{step.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white py-24 dark:border-slate-800/50 dark:bg-slate-900/55" id="modules">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 min-[1120px]:grid-cols-12 min-[1024px]:px-8">
            <div className="space-y-8 min-[1120px]:col-span-5">
              <div className="inline-flex rounded-full bg-slate-900 px-4 py-1.5 text-[10px] font-black uppercase tracking-[0.16em] text-white dark:bg-cyan-400 dark:text-slate-950">
                Hệ mô-đun
              </div>
              <h2 className="text-4xl font-black leading-tight tracking-tight text-slate-900 min-[1024px]:text-5xl dark:text-slate-100">
                Research là lõi vận hành
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">của CLARA</span>
              </h2>
              <p className="text-lg font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                Công cụ cốt lõi cho bác sĩ và sinh viên y khoa, giúp truy tìm bằng chứng lâm sàng đáng tin cậy chỉ trong vài giây.
              </p>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">95%+</p>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Tỷ lệ phản hồi có trích dẫn
                  </p>
                </div>
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">&lt;20s</p>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Thời gian phản hồi
                  </p>
                </div>
              </div>
              <Link
                href="/research"
                className="inline-flex rounded-xl bg-slate-900 px-8 py-4 text-base font-black text-white transition-colors hover:bg-slate-800 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
              >
                Bắt đầu dùng Research
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-4 min-[760px]:grid-cols-2 min-[1120px]:col-span-7">
              {MODULES.map((module) => (
                <article
                  key={module.title}
                  className="glass-panel module-blade rounded-2xl p-7 transition-all hover:-translate-y-1 hover:shadow-2xl"
                >
                  <div className="mb-6 flex items-center justify-between">
                    <div className="rounded-xl bg-cyan-100/60 p-3 dark:bg-cyan-900/35">
                      {module.icon.startsWith("fa ") ? (
                        <i className={`${module.icon} text-2xl text-cyan-700 dark:text-cyan-300`} aria-hidden="true" />
                      ) : (
                        <span className="material-symbols-outlined text-2xl text-cyan-700 dark:text-cyan-300">{module.icon}</span>
                      )}
                    </div>
                  </div>
                  <h3 className="mb-2 text-xl font-black text-slate-900 dark:text-slate-100">{module.title}</h3>
                  <p className="mb-6 text-sm font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                    {module.description}
                  </p>
                  <Link
                    href={module.href}
                    className="inline-flex items-center gap-1 text-xs font-black uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300"
                  >
                    {module.cta}
                    <i className="fa fa-chevron-right text-base" aria-hidden="true" />
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-24 min-[1024px]:px-8" id="workflow">
          <h2 className="mb-16 text-center text-4xl font-black leading-tight tracking-tight text-slate-900 min-[1024px]:text-5xl dark:text-slate-100">
            Quy trình gọn để đi từ
            <br />
            <span className="text-cyan-600 dark:text-cyan-300">câu hỏi đến quyết định</span>
          </h2>

          <div className="grid grid-cols-1 gap-12 min-[900px]:grid-cols-3">
            {[
              {
                no: "01",
                title: "Nhập câu hỏi lâm sàng",
                desc: "Đặt câu hỏi bằng ngôn ngữ tự nhiên về triệu chứng, phác đồ hoặc tương tác thuốc.",
                icon: "clinical_notes",
              },
              {
                no: "02",
                title: "Đối chiếu kết quả và nguồn",
                desc: "Câu trả lời luôn đi kèm trích dẫn để bạn kiểm chứng nhanh trước khi áp dụng.",
                icon: "fact_check",
              },
              {
                no: "03",
                title: "Chuyển tiếp và theo dõi",
                desc: "Đưa kết quả sang module phù hợp như Council, CareGuard hoặc Scribe để tiếp tục xử lý.",
                icon: "monitoring",
              },
            ].map((step) => (
              <article key={step.no} className="space-y-4">
                <div className="text-7xl font-black text-cyan-200/40 dark:text-cyan-900/60">{step.no}</div>
                <h3 className="flex items-center gap-2 text-2xl font-black text-slate-900 dark:text-slate-100">
                  <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">{step.icon}</span>
                  {step.title}
                </h3>
                <p className="text-base font-medium leading-relaxed text-slate-600 dark:text-slate-300">{step.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="relative overflow-hidden bg-slate-900 py-24 text-white dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-10" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-14 flex flex-col gap-6 min-[1024px]:flex-row min-[1024px]:items-end min-[1024px]:justify-between">
              <h2 className="text-4xl font-black leading-tight tracking-tight min-[1024px]:text-5xl">
                Nguyên tắc thiết kế
                <br />
                <span className="text-cyan-300">hệ thống y khoa</span>
              </h2>
              <p className="max-w-sm text-sm font-bold text-slate-300">
                Không chỉ là AI trả lời câu hỏi, đây là quy trình có kiểm soát để đội ngũ có thể dùng ổn định mỗi ngày.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-3">
              {[
                {
                  title: "Citation-first",
                  icon: "fact_check",
                  desc: "Mọi luận điểm đều có nguồn rõ ràng, hạn chế tối đa nội dung không thể kiểm chứng.",
                },
                {
                  title: "Safety-first",
                  icon: "health_and_safety",
                  desc: "Bộ lọc an toàn đa lớp giúp ngăn các khuyến nghị có mức rủi ro cao.",
                },
                {
                  title: "Pilot-first",
                  icon: "flight_takeoff",
                  desc: "Triển khai từ use-case nhỏ có KPI rõ ràng, rồi mở rộng dựa trên dữ liệu vận hành thực tế.",
                },
              ].map((item) => (
                <article key={item.title} className="glass-panel rounded-2xl border border-white/15 bg-white/5 p-8">
                  <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-cyan-400/10">
                    <span className="material-symbols-outlined text-3xl text-cyan-300">{item.icon}</span>
                  </div>
                  <h3 className="mb-3 text-2xl font-black text-white">{item.title}</h3>
                  <p className="text-sm font-medium leading-relaxed text-slate-300">{item.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-24 min-[1024px]:px-8">
          <h2 className="mb-14 text-center text-4xl font-black tracking-tight text-slate-900 min-[1024px]:text-5xl dark:text-slate-100">
            Người dùng nhận xét gì về <span className="text-cyan-600 dark:text-cyan-300">CLARA</span>
          </h2>
          <div className="grid grid-cols-1 gap-6 min-[1000px]:grid-cols-3">
            {TESTIMONIALS.map((item) => (
              <article key={item.name} className="glass-panel rounded-2xl border-l-4 border-cyan-500 p-8">
                <p className="mb-8 text-lg font-medium italic leading-relaxed text-slate-700 dark:text-slate-200">
                  &ldquo;{item.quote}&rdquo;
                </p>
                <div className="border-t border-slate-300/35 pt-5 dark:border-slate-700/45">
                  <p className="font-black text-slate-900 dark:text-slate-100">{item.name}</p>
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-cyan-700 dark:text-cyan-300">{item.role}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-4 py-24 min-[1024px]:px-8" id="faq">
          <h2 className="mb-10 text-center text-4xl font-black tracking-tight text-slate-900 dark:text-slate-100">Câu hỏi thường gặp</h2>
          <div className="space-y-4">
            {FAQS.map((faq) => (
              <details key={faq.q} className="glass-panel overflow-hidden rounded-2xl border border-slate-300/35 dark:border-slate-700/45">
                <summary className="flex cursor-pointer list-none items-center justify-between p-5 text-left">
                  <span className="font-black text-slate-900 dark:text-slate-100">{faq.q}</span>
                  <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">expand_more</span>
                </summary>
                <div className="px-5 pb-5 text-sm font-medium leading-relaxed text-slate-600 dark:text-slate-300">{faq.a}</div>
              </details>
            ))}
          </div>
        </section>

        <footer className="relative overflow-hidden bg-slate-900 py-14 dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-5" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 text-slate-300 min-[1024px]:px-8">
            <div className="grid grid-cols-1 gap-10 border-b border-slate-800/80 pb-10 md:grid-cols-12 md:gap-8">
              <div className="space-y-4 md:col-span-5">
                <p className="text-2xl font-black text-white">
                  The <span className="text-cyan-300">Clara Care</span>
                </p>
                <p className="max-w-md text-sm font-medium leading-relaxed">Nền tảng AI y khoa chính xác cho quy trình lâm sàng hiện đại.</p>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-cyan-300">© 2026 The Clara Care</p>
              </div>

              <div className="grid grid-cols-1 gap-8 sm:grid-cols-3 md:col-span-7">
                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">category</span>
                    Sản phẩm
                  </p>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#engine">
                    Lõi AI
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#modules">
                    Mô-đun
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#workflow">
                    Quy trình
                  </a>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">gavel</span>
                    Pháp lý
                  </p>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/privacy">
                    Chính sách quyền riêng tư
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/terms">
                    Điều khoản dịch vụ
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/consent">
                    Cam kết y khoa
                  </Link>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">contact_support</span>
                    Liên hệ
                  </p>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="mailto:clara@thiennn.icu">
                    clara@thiennn.icu
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="tel:0853374247">
                    0853374247
                  </a>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-start justify-between gap-2 pt-4 text-[11px] text-slate-400 sm:flex-row sm:items-center">
              <p>Xây dựng cho quy trình lâm sàng ưu tiên bối cảnh Việt Nam.</p>
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Research • Council • Self-Med • CareGuard • Scribe • Control Tower</p>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
