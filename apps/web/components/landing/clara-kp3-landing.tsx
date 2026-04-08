import Image from "next/image";
import Link from "next/link";

import { SPONSORS } from "@/components/landing/clara-kp3-data";

const MODULES = [
  {
    title: "Council",
    description: "Hỗ trợ hội chẩn đa chuyên khoa bằng AI theo thời gian thực.",
    icon: "groups",
    href: "/council/new",
    cta: "Vào Council",
  },
  {
    title: "Self-Med",
    description: "Quản lý lộ trình thuốc và phân tích tương tác phức hợp.",
    icon: "medication",
    href: "/selfmed",
    cta: "Vào Self-Med",
  },
  {
    title: "CareGuard",
    description: "Giám sát an toàn bệnh nhân và cảnh báo theo mức độ rủi ro.",
    icon: "shield",
    href: "/careguard",
    cta: "Vào CareGuard",
  },
  {
    title: "Scribe",
    description: "Tự động hóa ghi chép và chuẩn hóa bàn giao sau ca.",
    icon: "fa fa-pencil-square-o",
    href: "/scribe",
    cta: "Vào Scribe",
  },
] as const;

const TESTIMONIALS = [
  {
    quote:
      "CLARA giúp tôi tiết kiệm hàng giờ tra cứu tài liệu khi chuẩn bị hội chẩn các ca lâm sàng phức tạp.",
    name: "BS. Nguyễn Minh Tuấn",
    role: "Trưởng khoa Nội tiết",
  },
  {
    quote:
      "Là sinh viên, tôi dùng CLARA để tự học. Cách hệ thống bóc tách dữ liệu giúp tôi hiểu sâu hơn về tương tác thuốc.",
    name: "Trần Lê Vy",
    role: "Sinh viên Y6",
  },
  {
    quote:
      "Scribe và Research kết hợp rất mượt, tôi vừa ghi chú vừa tra cứu mà không đứt luồng công việc.",
    name: "Lê Hoàng Nam",
    role: "Trợ lý nghiên cứu",
  },
] as const;

const FAQS = [
  {
    q: "CLARA có thay thế quyết định bác sĩ không?",
    a: "Không. CLARA là hệ thống hỗ trợ tham khảo lâm sàng; quyết định điều trị cuối cùng luôn thuộc đội ngũ chuyên môn.",
  },
  {
    q: "Dữ liệu bệnh nhân có được bảo mật không?",
    a: "Có. Hệ thống áp dụng guardrail vận hành, kiểm soát truy cập theo vai trò và theo dõi audit để đảm bảo an toàn dữ liệu.",
  },
  {
    q: "Làm sao để kiểm chứng thông tin AI đưa ra?",
    a: "Mỗi luận điểm đều đi kèm citation từ nguồn y khoa phù hợp để bạn đối chiếu nhanh trước khi áp dụng.",
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
              Project <span className="text-cyan-600 dark:text-cyan-300">CLARA</span>
            </div>
          </div>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="glow-cyan inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300" href="#engine">
              <span className="material-symbols-outlined text-sm">memory</span>
              AI Engine
            </a>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#modules">
              <span className="material-symbols-outlined text-sm">widgets</span>
              Modules
            </a>
            <a className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#workflow">
              <span className="material-symbols-outlined text-sm">account_tree</span>
              Workflow
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
            Vào Workspace CLARA
          </Link>
        </nav>

        <section className="relative mx-auto max-w-7xl px-4 pb-14 pt-28 min-[1024px]:px-8 min-[1024px]:pb-20 min-[1024px]:pt-36">
          <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-30">
            <div className="data-stream left-1/4" style={{ animationDelay: "0s" }} />
            <div className="data-stream left-1/3" style={{ animationDelay: "1.5s" }} />
            <div className="data-stream left-2/3" style={{ animationDelay: "0.7s" }} />
            <div className="data-stream left-3/4" style={{ animationDelay: "2.2s" }} />
          </div>

          <div className="relative z-10 flex flex-col items-center gap-12 min-[1120px]:flex-row min-[1120px]:items-start min-[1120px]:gap-16">
            <div className="w-full space-y-8 min-[1120px]:w-5/12">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-100/65 px-3 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-cyan-800 dark:border-cyan-700/50 dark:bg-cyan-900/35 dark:text-cyan-200">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                Next-Gen Medical AI
              </div>

              <h1 className="text-[2.8rem] font-black leading-[0.92] tracking-tight text-slate-900 min-[640px]:text-[4.2rem] min-[1280px]:text-[5.3rem] dark:text-slate-100">
                Hỏi nhanh.
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">Có nguồn rõ.</span>
                <br />
                Quyết định chắc.
              </h1>

              <p className="text-lg font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                Bắt đầu từ chatbot Research để truy xuất bằng chứng nhanh, sau đó mở rộng mượt sang Council, Self-Med,
                CareGuard, Scribe và Control Tower.
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
                    Citation Trace
                  </div>
                  <div className="text-sm font-bold text-slate-700 dark:text-slate-200">Theo từng luận điểm</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-cyan-700 dark:text-cyan-300">
                    <span className="material-symbols-outlined text-xs">timer</span>
                    Latency
                  </div>
                  <div className="text-sm font-bold text-slate-700 dark:text-slate-200">&lt;20s Response</div>
                </div>
              </div>
            </div>

            <div className="relative w-full min-[1120px]:w-7/12">
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
                      System Core v4.2
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-300">ACTIVE SESSION</span>
                    <span className="h-2 w-2 rounded-full bg-cyan-500 dark:bg-cyan-300" />
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="flex justify-between">
                    <div>
                      <div className="text-sm font-black text-slate-900 dark:text-slate-100">CLARA Research Engine</div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                        Clinical Context Active
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
                        Tương tác thuốc giữa Amlodipine và Simvastatin?
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
                            Kết hợp có thể làm tăng nồng độ Simvastatin trong máu, dẫn đến nguy cơ tiêu cơ vân.
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
                            98% Confidence
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 rounded-xl border border-slate-300/45 bg-slate-100 p-3 dark:border-slate-700 dark:bg-slate-900">
                    <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">barcode_scanner</span>
                    <div className="flex-1 text-xs font-bold italic text-slate-500 dark:text-slate-400">
                      Đang phân tích dữ liệu lâm sàng...
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
                <div className="mb-1 text-[10px] font-black uppercase text-cyan-700 dark:text-cyan-300">REAL-TIME</div>
                <div className="text-xl font-black text-slate-900 dark:text-slate-100">2.4k</div>
                <div className="text-[9px] font-bold text-slate-500 dark:text-slate-400">Queries/min</div>
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
              Hạ tầng và hệ sinh thái đồng hành cùng Project CLARA.
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
              Luồng dữ liệu và neural routing của CLARA
            </h2>
            <p className="mx-auto max-w-3xl text-base font-medium text-slate-600 dark:text-slate-300">
              Mọi tín hiệu được xử lý theo từng lớp rõ ràng, để bạn nhìn một lần là hiểu hệ thống đang hoạt động ra sao.
            </p>
          </div>

          <div className="relative grid grid-cols-1 gap-6 min-[900px]:grid-cols-4">
            <div className="pointer-events-none absolute left-0 top-1/2 hidden h-px w-full -translate-y-1/2 bg-gradient-to-r from-transparent via-cyan-300/45 to-transparent min-[900px]:block" />
            {[
              {
                layer: "Layer 01",
                title: "Input",
                desc: "Tiếp nhận truy vấn văn bản hoặc dữ liệu cận lâm sàng thô qua cổng mã hóa.",
                icon: "fa fa-sign-in",
                tone: "text-cyan-700 dark:text-cyan-300",
              },
              {
                layer: "Layer 02",
                title: "Neural Retrieval",
                desc: "Phân tích ý định và truy xuất nguồn tin từ các cơ sở dữ liệu y khoa phù hợp.",
                icon: "neurology",
                tone: "text-cyan-200",
                solid: true,
              },
              {
                layer: "Layer 03",
                title: "Safety Layer",
                desc: "Kiểm chứng chéo với policy nội bộ và confidence score trước khi hiển thị.",
                icon: "security",
                tone: "text-red-500",
              },
              {
                layer: "Layer 04",
                title: "Output",
                desc: "Trả lời có citation và gợi ý bước tiếp theo theo workflow thực tế.",
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
                System Modules
              </div>
              <h2 className="text-4xl font-black leading-tight tracking-tight text-slate-900 min-[1024px]:text-5xl dark:text-slate-100">
                CLARA Research
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">Core Engine</span>
              </h2>
              <p className="text-lg font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                Công cụ cốt lõi cho bác sĩ và sinh viên y khoa. Truy tìm bằng chứng lâm sàng chính xác trong vài giây.
              </p>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">95%+</p>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Độ bao phủ citation
                  </p>
                </div>
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">&lt;20s</p>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                    Tốc độ phản hồi
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
            Quy trình ngắn gọn để đi từ
            <br />
            <span className="text-cyan-600 dark:text-cyan-300">câu hỏi đến hành động</span>
          </h2>

          <div className="grid grid-cols-1 gap-12 min-[900px]:grid-cols-3">
            {[
              {
                no: "01",
                title: "Nhập yêu cầu y khoa",
                desc: "Dùng ngôn ngữ tự nhiên để hỏi về triệu chứng, phác đồ hoặc tương tác thuốc.",
                icon: "clinical_notes",
              },
              {
                no: "02",
                title: "Duyệt kết quả và nguồn",
                desc: "Hệ thống trả lời kèm citation để kiểm chứng nhanh trước khi áp dụng.",
                icon: "fact_check",
              },
              {
                no: "03",
                title: "Triển khai và theo dõi",
                desc: "Chuyển kết quả sang module phù hợp như Council, CareGuard hoặc Scribe.",
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
                Nguyên tắc thiết kế hệ thống
                <br />
                <span className="text-cyan-300">y tế chuẩn mực</span>
              </h2>
              <p className="max-w-sm text-sm font-bold text-slate-300">
                Không chỉ là AI, đây là workflow có kiểm soát để đội ngũ dùng được mỗi ngày.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-3">
              {[
                {
                  title: "Citation-first",
                  icon: "fact_check",
                  desc: "Mọi dữ liệu đều có nguồn rõ ràng, không tạo nội dung không kiểm chứng.",
                },
                {
                  title: "Safety-first",
                  icon: "health_and_safety",
                  desc: "Bộ lọc an toàn đa lớp giúp chặn khuyến nghị rủi ro cao.",
                },
                {
                  title: "Pilot-first",
                  icon: "flight_takeoff",
                  desc: "Triển khai từ use-case nhỏ có KPI, rồi mở rộng theo dữ liệu thật.",
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
            Người dùng nói gì về <span className="text-cyan-600 dark:text-cyan-300">CLARA</span>
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

        <footer className="relative overflow-hidden bg-slate-900 py-16 dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-5" />
          <div className="relative z-10 mx-auto grid max-w-7xl grid-cols-1 gap-10 px-4 text-slate-300 min-[900px]:grid-cols-4 min-[1024px]:px-8">
            <div className="space-y-4">
              <p className="text-2xl font-black text-white">
                Project <span className="text-cyan-300">CLARA</span>
              </p>
              <p className="text-sm font-medium leading-relaxed">Precision AI Systems for modern clinical intelligence.</p>
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-cyan-300">© 2026 Project CLARA</p>
            </div>

            <div className="space-y-3">
              <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                <span className="material-symbols-outlined text-sm">category</span>
                Sản phẩm
              </p>
              <a className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="#engine">
                <span className="material-symbols-outlined text-base">memory</span>
                AI Engine
              </a>
              <a className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="#modules">
                <span className="material-symbols-outlined text-base">widgets</span>
                Modules
              </a>
              <a className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="#workflow">
                <span className="material-symbols-outlined text-base">account_tree</span>
                Workflow
              </a>
            </div>

            <div className="space-y-3">
              <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                <span className="material-symbols-outlined text-sm">gavel</span>
                Pháp lý
              </p>
              <Link className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="/legal/privacy">
                <span className="material-symbols-outlined text-base">privacy_tip</span>
                Privacy Policy
              </Link>
              <Link className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="/legal/terms">
                <span className="material-symbols-outlined text-base">description</span>
                Terms of Service
              </Link>
              <Link className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="/legal/consent">
                <span className="material-symbols-outlined text-base">verified_user</span>
                Medical Consent
              </Link>
            </div>

            <div className="space-y-3">
              <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                <span className="material-symbols-outlined text-sm">contact_support</span>
                Liên hệ
              </p>
              <a className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="mailto:clara@thiennn.icu">
                <span className="material-symbols-outlined text-base">mail</span>
                clara@thiennn.icu
              </a>
              <a className="inline-flex items-center gap-2 text-sm font-bold hover:text-cyan-300" href="tel:0853374247">
                <span className="material-symbols-outlined text-base">call</span>
                0853374247
              </a>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
