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
    audience: "Dành cho bác sĩ",
  },
  {
    title: "Self-Med",
    description: "Quản lý lộ trình thuốc và phân tích tương tác phức hợp.",
    icon: "medication",
    href: "/selfmed",
    cta: "Vào Self-Med",
    audience: "Dành cho người dùng cá nhân",
  },
  {
    title: "CareGuard",
    description: "Giám sát an toàn bệnh nhân và cảnh báo theo mức độ rủi ro.",
    icon: "shield",
    href: "/careguard",
    cta: "Vào CareGuard",
    audience: "Dành cho an toàn lâm sàng",
  },
  {
    title: "Scribe",
    description: "Tự động hóa ghi chép và chuẩn hóa bàn giao sau ca.",
    icon: "fa fa-pencil-square-o",
    href: "/scribe",
    cta: "Vào Scribe",
    audience: "Dành cho ghi chú y khoa",
  },
] as const;

const USE_CASES = [
  {
    role: "Bác sĩ lâm sàng",
    icon: "stethoscope",
    scenario:
      "Trước khi kê đơn cho bệnh nhân đa thuốc, bác sĩ tra DDI giữa Amlodipine và Simvastatin ngay trong CLARA Chat.",
    benefit: "Kết quả có trích dẫn PubMed & openFDA trong < 20 giây — không cần rời workflow.",
    tag: "Kiểm tra DDI",
  },
  {
    role: "Sinh viên y khoa",
    icon: "school",
    scenario:
      "Ôn thi lâm sàng bằng cách hỏi CLARA về phác đồ điều trị, mỗi luận điểm đều được truy ngược về guideline chuẩn.",
    benefit: "Học theo bằng chứng thay vì ghi nhớ máy móc — mỗi câu trả lời đều kiểm chứng được.",
    tag: "Ôn theo bằng chứng",
  },
  {
    role: "Nhà nghiên cứu",
    icon: "biotech",
    scenario:
      "Tổng hợp y văn từ PubMed, ClinicalTrials và WHO ICD-11 về một chủ đề trong vài phút thay vì vài giờ.",
    benefit: "Có danh sách citation có thể kiểm toán — sẵn sàng đưa vào báo cáo ngay.",
    tag: "Tổng hợp đa nguồn",
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
  {
    q: "Nguồn y khoa của CLARA đến từ đâu?",
    a: "CLARA tích hợp PubMed, ClinicalTrials.gov, WHO ICD-11, openFDA, RxNorm và Dược thư Việt Nam — tất cả đều được trích dẫn rõ ràng trong từng câu trả lời.",
  },
  {
    q: "CLARA có hỗ trợ tiếng Việt không?",
    a: "Có. CLARA hỗ trợ cả tiếng Việt và tiếng Anh. Bạn có thể đặt câu hỏi bằng tiếng Việt và nhận câu trả lời theo ngôn ngữ bạn chọn.",
  },
  {
    q: "Có thể triển khai cho phòng khám hoặc bệnh viện không?",
    a: "Có. CLARA được thiết kế để triển khai theo pilot — bắt đầu từ 1 use-case nhỏ có KPI rõ, mở rộng theo dữ liệu thật. Liên hệ để được tư vấn cụ thể.",
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
          border: 1px solid rgba(96, 165, 250, 0.24);
        }

        .cyber-grid {
          background-image: linear-gradient(rgba(96, 165, 250, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(96, 165, 250, 0.05) 1px, transparent 1px);
          background-size: 40px 40px;
        }

        .data-stream {
          position: absolute;
          background: linear-gradient(to bottom, transparent, #60a5fa, transparent);
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
        <nav className="glass-panel fixed top-0 z-[100] flex w-full items-center justify-between border-b border-slate-200/45 px-4 py-4 min-[1024px]:px-8 dark:border-slate-700/45">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-slate-900 text-lg font-bold text-white dark:bg-cyan-400 dark:text-slate-950">
              C
            </div>
            <div className="text-xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
              The <span className="text-cyan-600 dark:text-cyan-300">Clara Care</span>
            </div>
          </div>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="glow-cyan inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300" href="#engine">
              <span className="material-symbols-outlined text-sm">play_circle</span>
              Cách hoạt động
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#modules">
              <span className="material-symbols-outlined text-sm">widgets</span>
              Tính năng
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#workflow">
              <span className="material-symbols-outlined text-sm">account_tree</span>
              Quy trình
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white" href="#faq">
              <span className="material-symbols-outlined text-sm">help</span>
              Hỏi đáp
            </a>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-bold text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
            >
              Đăng nhập
            </Link>
            <Link
              href="/register"
              className="rounded-md border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-bold text-white transition-all hover:bg-slate-800 dark:border-cyan-500 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
            >
              Đăng ký
            </Link>
          </div>
        </nav>

        <section className="relative mx-auto max-w-7xl px-4 pb-14 pt-28 min-[1024px]:px-8 min-[1024px]:pb-20 min-[1024px]:pt-36">
          <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-30">
            <div className="data-stream left-1/4" style={{ animationDelay: "0s" }} />
            <div className="data-stream left-1/3" style={{ animationDelay: "1.5s" }} />
            <div className="data-stream left-2/3" style={{ animationDelay: "0.7s" }} />
            <div className="data-stream left-3/4" style={{ animationDelay: "2.2s" }} />
          </div>

          <div className="relative z-10 flex flex-col gap-10 min-[1120px]:flex-row min-[1120px]:items-center min-[1120px]:gap-12">
            <div className="w-full space-y-6 min-[1120px]:w-[54%] min-[1280px]:w-[56%]">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-100/65 px-3 py-1 text-[11px] font-black uppercase tracking-[0.2em] text-cyan-800 dark:border-cyan-700/50 dark:bg-cyan-900/35 dark:text-cyan-200">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                AI lâm sàng có trích dẫn nguồn
              </div>

              <h1
                className="font-black leading-[1.08] tracking-tight text-slate-900 [text-wrap:balance] min-[640px]:leading-[0.98] dark:text-slate-100"
                style={{ fontSize: "clamp(1.4rem, 6.4vw, 4.25rem)" }}
              >
                Hỏi đúng trọng tâm.{" "}
                <span className="text-cyan-600 dark:text-cyan-300">Có nguồn minh bạch.</span>{" "}
                Quyết định tự tin.
              </h1>

              <p className="max-w-[56ch] text-[0.95rem] font-medium leading-relaxed text-slate-600 min-[640px]:text-base min-[1280px]:text-lg dark:text-slate-300">
                CLARA là trợ lý y khoa cho <strong className="font-black text-slate-800 dark:text-slate-200">bác sĩ, sinh viên y khoa và nhà nghiên cứu</strong>: tra cứu nhanh, mọi kết luận <strong className="font-black text-slate-800 dark:text-slate-200">truy ngược được nguồn</strong> và <strong className="font-black text-slate-800 dark:text-slate-200">kiểm chứng từng luận điểm</strong> — hỗ trợ quyết định an toàn hơn, không phải chatbot trả lời chung chung.
              </p>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/chat"
                  className="group inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-slate-900 px-6 py-4 text-base font-black text-white transition-all hover:bg-slate-800 min-[480px]:flex-none min-[480px]:px-8 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
                >
                  Dùng thử CLARA Chat
                  <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">arrow_forward</span>
                </Link>
                <a
                  href="#engine"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-4 text-base font-black text-slate-900 transition-colors hover:bg-slate-100 min-[480px]:flex-none min-[480px]:px-8 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="material-symbols-outlined text-base">play_circle</span>
                  Xem cách hoạt động
                </a>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t border-slate-300/45 pt-8 dark:border-slate-700/45">
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">verified</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">Có trích dẫn nguồn</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">timer</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">&lt;20s phản hồi</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">fact_check</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">Kiểm chứng từng luận điểm</span>
                </div>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-xl self-center min-[1120px]:mx-0 min-[1120px]:w-[46%] min-[1280px]:w-[44%]">
              <div className="absolute -inset-10 rounded-full bg-cyan-300/15 blur-[100px] dark:bg-cyan-700/20" />

              <div className="glass-panel relative overflow-hidden rounded-2xl border border-white/40 p-5 shadow-[0_32px_64px_-12px_rgba(0,218,243,0.15)] dark:border-cyan-500/30">
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
                    <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-300">Phiên đang hoạt động</span>
                    <span className="h-2 w-2 rounded-full bg-cyan-500 dark:bg-cyan-300" />
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="flex justify-between">
                    <div>
                      <div className="text-sm font-black text-slate-900 dark:text-slate-100">CLARA Chat Engine</div>
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
                      <div className="max-w-[82%] rounded-xl rounded-tr-none border border-slate-300/45 bg-slate-100 px-4 py-3 text-base font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
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
                          <p className="relative z-10 text-base leading-relaxed">
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
                            Độ tin cậy 98%
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

              <div className="glass-panel absolute -right-6 -top-6 hidden w-36 flex-col items-center justify-center rounded-2xl border border-cyan-300/35 p-4 shadow-2xl shadow-cyan-900/20 min-[1200px]:flex">
                <span className="material-symbols-outlined mb-2 text-3xl text-cyan-600 dark:text-cyan-400">verified</span>
                <div className="text-center text-xs font-black uppercase text-slate-800 dark:text-slate-200">Có trích dẫn nguồn</div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white/75 py-8 dark:border-slate-800/50 dark:bg-slate-900/55">
          <div className="mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-2 text-center text-xs font-black uppercase tracking-[0.28em] text-slate-600 dark:text-slate-400">
              <span className="material-symbols-outlined mr-1 align-[-3px] text-sm">handshake</span>
              Các đối tác và nhà tài trợ
            </div>
            <div className="mb-8 text-center text-sm font-medium text-slate-600 dark:text-slate-300">
              Hạ tầng và hệ sinh thái đồng hành cùng The Clara Care.
            </div>
            <div className="flex flex-wrap justify-center gap-4">
              {SPONSORS.map((sponsor) => (
                <a
                  key={sponsor.name}
                  href={sponsor.href}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-h-[120px] w-full max-w-xs items-center justify-center rounded-2xl border border-slate-700/50 bg-slate-900 p-6 shadow-lg shadow-slate-900/10 transition-all hover:-translate-y-0.5 dark:bg-slate-950"
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
            <p className="mt-6 text-center text-base font-medium text-slate-500 dark:text-slate-400">
              Đối tác hạ tầng & triển khai thử nghiệm — đang mở rộng mạng lưới y khoa.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8" id="engine">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 font-black tracking-tight text-slate-900 dark:text-slate-100"
              style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
            >
              CLARA xử lý một câu hỏi y khoa như thế nào?
            </h2>
            <p className="mx-auto max-w-3xl text-base font-medium text-slate-600 dark:text-slate-300">
              Bốn bước rõ ràng — từ câu hỏi của bạn đến câu trả lời có nguồn kiểm chứng.
            </p>
          </div>

          <div className="flex flex-col gap-3 min-[900px]:flex-row min-[900px]:items-stretch">
            {(
              [
                {
                  layer: "Bước 01",
                  title: "Đầu vào",
                  desc: "Người dùng nhập triệu chứng, thuốc hoặc câu hỏi lâm sàng.",
                  icon: "edit_note",
                  tone: "text-cyan-700 dark:text-cyan-300",
                  solid: false,
                },
                {
                  layer: "Bước 02",
                  title: "Tìm nguồn liên quan",
                  desc: "CLARA tìm nguồn y khoa liên quan (PubMed, openFDA, nội bộ) — không chỉ khớp từ khóa.",
                  icon: "neurology",
                  tone: "text-cyan-200",
                  solid: true,
                },
                {
                  layer: "Bước 03",
                  title: "Kiểm tra an toàn",
                  desc: "Lọc cảnh báo, chống trả lời quá mức và yêu cầu kiểm chứng trước khi hiển thị.",
                  icon: "security",
                  tone: "text-red-400",
                  solid: false,
                },
                {
                  layer: "Bước 04",
                  title: "Kết quả",
                  desc: "Trả lời có nguồn, kèm độ tin cậy và gợi ý bước tiếp theo.",
                  icon: "task_alt",
                  tone: "text-cyan-700 dark:text-cyan-300",
                  solid: false,
                },
              ] satisfies { layer: string; title: string; desc: string; icon: string; tone: string; solid: boolean }[]
            ).flatMap((step, idx, arr) => [
              <article
                key={step.title}
                className={
                  step.solid
                    ? "relative z-10 flex-1 rounded-2xl bg-slate-900 p-7 text-white shadow-2xl dark:bg-cyan-800"
                    : "glass-panel relative z-10 flex-1 rounded-2xl p-7"
                }
              >
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800/60">
                  <span className={`material-symbols-outlined text-2xl ${step.tone}`}>{step.icon}</span>
                </div>
                <p className={`mb-1 text-xs font-black uppercase tracking-[0.15em] ${step.tone}`}>{step.layer}</p>
                <h3 className="mb-3 text-xl font-black">{step.title}</h3>
                <p className={`text-base leading-relaxed ${step.solid ? "text-slate-200" : "text-slate-600 dark:text-slate-300"}`}>{step.desc}</p>
              </article>,
              idx < arr.length - 1 ? (
                <div key={`arrow-${idx}`} className="hidden shrink-0 items-center justify-center text-cyan-400/50 min-[900px]:flex">
                  <span className="material-symbols-outlined text-2xl">arrow_forward</span>
                </div>
              ) : null,
            ])}
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white py-20 dark:border-slate-800/50 dark:bg-slate-900/55" id="modules">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 min-[1120px]:grid-cols-12 min-[1024px]:px-8">
            <div className="space-y-8 min-[1120px]:col-span-5">
              <div className="inline-flex rounded-full bg-slate-900 px-4 py-1.5 text-xs font-black uppercase tracking-[0.16em] text-white dark:bg-cyan-400 dark:text-slate-950">
                Phân hệ hệ thống
              </div>
              <h2
                className="font-black leading-tight tracking-tight text-slate-900 dark:text-slate-100"
                style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
              >
                CLARA Chat
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">Core Engine</span>
              </h2>
              <p className="text-lg font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                Công cụ cốt lõi cho bác sĩ và sinh viên y khoa. Truy tìm bằng chứng lâm sàng chính xác trong vài giây.
              </p>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">95%+</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
                    Độ bao phủ citation
                  </p>
                </div>
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">&lt;20s</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
                    Tốc độ phản hồi
                  </p>
                </div>
              </div>
              <Link
                href="/chat"
                className="inline-flex rounded-xl bg-slate-900 px-8 py-4 text-base font-black text-white transition-colors hover:bg-slate-800 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
              >
                Dùng thử CLARA Chat
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
                    <span className="rounded-full border border-cyan-300/40 bg-cyan-100/50 px-2.5 py-1 text-xs font-bold text-cyan-800 dark:border-cyan-700/40 dark:bg-cyan-900/30 dark:text-cyan-300">
                      {module.audience}
                    </span>
                  </div>
                  <h3 className="mb-2 text-xl font-black text-slate-900 dark:text-slate-100">{module.title}</h3>
                  <p className="mb-6 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-300">
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

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8" id="workflow">
          <h2
            className="mb-16 text-center font-black leading-tight tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            Quy trình 3 bước từ
            <br />
            <span className="text-cyan-600 dark:text-cyan-300">câu hỏi đến quyết định có căn cứ</span>
          </h2>

          <div className="grid grid-cols-1 gap-12 min-[900px]:grid-cols-3">
            {[
              {
                no: "01",
                title: "Nhập yêu cầu lâm sàng",
                desc: "Dùng ngôn ngữ tự nhiên để hỏi về DDI, phác đồ, triệu chứng hay tổng hợp y văn.",
                icon: "clinical_notes",
                outcome: "CLARA tiếp nhận và phân tích ý định",
              },
              {
                no: "02",
                title: "CLARA truy xuất & kiểm chứng",
                desc: "Hệ thống tra PubMed, openFDA, RxNorm và kiểm chứng từng luận điểm theo fact-check matrix.",
                icon: "fact_check",
                outcome: "Kết quả có citation rõ nguồn",
              },
              {
                no: "03",
                title: "Bạn duyệt nguồn & quyết định",
                desc: "Review citation, chuyển sang Council / CareGuard / Scribe hoặc xuất báo cáo — bạn quyết định cuối cùng.",
                icon: "monitoring",
                outcome: "Quyết định có kiểm toán, an toàn hơn",
              },
            ].map((step) => (
              <article key={step.no} className="space-y-4">
                <div className="text-7xl font-black text-cyan-600/60 dark:text-cyan-400/50">{step.no}</div>
                <h3 className="flex items-center gap-2 text-2xl font-black text-slate-900 dark:text-slate-100">
                  <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">{step.icon}</span>
                  {step.title}
                </h3>
                <p className="text-base font-medium leading-relaxed text-slate-600 dark:text-slate-300">{step.desc}</p>
                <p className="text-xs font-black uppercase tracking-widest text-cyan-700 dark:text-cyan-400">
                  → {step.outcome}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="relative overflow-hidden bg-slate-900 py-20 text-white dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-10" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-14 flex flex-col gap-6 min-[1024px]:flex-row min-[1024px]:items-end min-[1024px]:justify-between">
              <h2
                className="font-black leading-tight tracking-tight"
                style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
              >
                Nguyên tắc thiết kế hệ thống
                <br />
                <span className="text-cyan-300">y tế chuẩn mực</span>
              </h2>
              <p className="max-w-sm text-base font-bold text-slate-200">
                Không chỉ là AI, đây là workflow có kiểm soát để đội ngũ dùng được mỗi ngày.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-3">
              {[
                {
                  title: "Trích dẫn trước tiên",
                  icon: "fact_check",
                  desc: "Mỗi câu trả lời đều gắn nguồn PubMed, WHO, openFDA hoặc tài liệu nội bộ.",
                  outcome: "Bạn kiểm chứng được trước khi ra quyết định.",
                },
                {
                  title: "An toàn trước tiên",
                  icon: "health_and_safety",
                  desc: "CLARA không thay thế bác sĩ, luôn giới hạn ở vai trò hỗ trợ; chặn không trả lời các trường hợp rủi ro cao.",
                  outcome: "Giảm rủi ro trả lời quá mức.",
                },
                {
                  title: "Triển khai thí điểm",
                  icon: "flight_takeoff",
                  desc: "Bắt đầu nhỏ với KPI rõ, đo hiệu quả rồi mở rộng có kiểm soát.",
                  outcome: "Đưa vào vận hành an toàn theo dữ liệu thật.",
                },
              ].map((item) => (
                <article key={item.title} className="rounded-2xl border border-white/25 bg-white/10 p-8">
                  <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-cyan-400/15">
                    <span className="material-symbols-outlined text-3xl text-cyan-300">{item.icon}</span>
                  </div>
                  <h3 className="mb-3 text-2xl font-black text-white">{item.title}</h3>
                  <p className="mb-4 text-base font-medium leading-relaxed text-slate-200">{item.desc}</p>
                  <div className="flex items-start gap-2 border-t border-white/15 pt-3">
                    <span className="material-symbols-outlined mt-0.5 text-sm text-cyan-400">check_circle</span>
                    <p className="text-sm font-bold leading-snug text-slate-300">Kết quả: {item.outcome}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8">
          <h2
            className="mb-4 text-center font-black tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            Kịch bản sử dụng thực tế
          </h2>
          <p className="mb-14 text-center text-base font-medium text-slate-600 dark:text-slate-300">
            CLARA phục vụ các vai trò khác nhau trong hệ sinh thái y tế.
          </p>
          <div className="grid grid-cols-1 gap-6 min-[1000px]:grid-cols-3">
            {USE_CASES.map((item) => (
              <article key={item.role} className="glass-panel rounded-2xl border-l-4 border-cyan-500 p-8">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-100/60 dark:bg-cyan-900/35">
                    <span className="material-symbols-outlined text-xl text-cyan-700 dark:text-cyan-300">{item.icon}</span>
                  </div>
                  <span className="rounded-full border border-cyan-300/40 bg-cyan-100/50 px-2.5 py-0.5 text-xs font-black text-cyan-800 dark:border-cyan-700/50 dark:bg-cyan-900/35 dark:text-cyan-200">
                    {item.tag}
                  </span>
                </div>
                <p className="mb-1 text-xs font-black uppercase tracking-[0.14em] text-slate-600 dark:text-slate-400">{item.role}</p>
                <p className="mb-4 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-200">
                  {item.scenario}
                </p>
                <p className="border-t border-slate-300/35 pt-4 text-sm font-bold text-slate-600 dark:border-slate-700/45 dark:text-slate-300">
                  ✓ {item.benefit}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* CTA giữa trang */}
        <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 py-16">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-1/4 top-0 h-64 w-64 -translate-y-1/2 rounded-full bg-cyan-500/10 blur-3xl" />
            <div className="absolute right-1/4 bottom-0 h-64 w-64 translate-y-1/2 rounded-full bg-cyan-400/8 blur-3xl" />
          </div>
          <div className="relative z-10 mx-auto max-w-3xl px-4 text-center min-[1024px]:px-8">
            <p className="mb-3 text-xs font-black uppercase tracking-[0.24em] text-cyan-400">Thử ngay</p>
            <h2
              className="mb-4 font-black leading-tight tracking-tight text-white"
              style={{ fontSize: "clamp(1.7rem, 5vw, 2.6rem)" }}
            >
              Sẵn sàng thử CLARA với câu hỏi y khoa của bạn?
            </h2>
            <p className="mb-8 text-base font-medium leading-relaxed text-slate-300">
              Không cần cài đặt. Mở trình duyệt, đặt câu hỏi, nhận kết quả có trích dẫn nguồn.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link
                href="/chat"
                className="group inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-8 py-4 text-base font-black text-slate-950 transition-all hover:bg-cyan-300"
              >
                Dùng thử CLARA Chat
                <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">arrow_forward</span>
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-600 bg-white/5 px-8 py-4 text-base font-black text-slate-200 transition-all hover:border-slate-400 hover:bg-white/10"
              >
                <span className="material-symbols-outlined text-base">fact_check</span>
                Xem quy trình kiểm chứng
              </a>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-4 py-20 min-[1024px]:px-8" id="faq">
          <h2
            className="mb-10 text-center font-black tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            Hỏi đáp
          </h2>
          <div className="space-y-4">
            {FAQS.map((faq) => (
              <details key={faq.q} className="glass-panel overflow-hidden rounded-2xl border border-slate-300/35 dark:border-slate-700/45">
                <summary className="flex cursor-pointer list-none items-center justify-between p-5 text-left">
                  <span className="font-black text-slate-900 dark:text-slate-100">{faq.q}</span>
                  <span className="material-symbols-outlined text-slate-400">expand_more</span>
                </summary>
                <div className="px-5 pb-5 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-300">{faq.a}</div>
              </details>
            ))}
          </div>
        </section>

        <footer className="relative overflow-hidden bg-slate-900 py-14 dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-5" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 text-slate-300 min-[1024px]:px-8">

            {/* CTA đầu footer */}
            <div className="mb-10 flex flex-col items-center justify-between gap-6 rounded-2xl border border-cyan-500/20 bg-slate-800/80 px-8 py-8 shadow-2xl shadow-cyan-900/20 min-[900px]:flex-row">
              <div>
                <p className="mb-1 text-lg font-black text-white">Bắt đầu dùng CLARA cho học tập, tra cứu và kiểm chứng lâm sàng.</p>
                <p className="text-sm font-medium text-slate-400">Miễn phí — không cần thẻ tín dụng.</p>
              </div>
              <Link
                href="/register"
                className="shrink-0 inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-6 py-3 text-sm font-black text-slate-950 transition-all hover:bg-cyan-300"
              >
                <span className="material-symbols-outlined text-base">person_add</span>
                Đăng ký dùng thử
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-10 border-b border-slate-800/80 pb-10 md:grid-cols-12 md:gap-8">
              <div className="space-y-4 md:col-span-5">
                <p className="text-2xl font-black text-white">
                  The <span className="text-cyan-300">Clara Care</span>
                </p>
                <p className="max-w-md text-base font-medium leading-relaxed text-slate-300">
                  Hệ thống AI lâm sàng có trích dẫn nguồn cho bác sĩ, sinh viên y khoa và nhà nghiên cứu.
                </p>
                <p className="text-xs font-black uppercase tracking-[0.15em] text-cyan-300">© 2026 The Clara Care</p>
              </div>

              <div className="grid grid-cols-1 gap-8 sm:grid-cols-3 md:col-span-7">
                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">category</span>
                    Sản phẩm
                  </p>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#engine">
                    Cách hoạt động
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#modules">
                    Tính năng
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
                    Privacy Policy
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/terms">
                    Terms of Service
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/consent">
                    Medical Consent
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

            <div className="flex flex-col items-start justify-between gap-2 pt-4 text-xs text-slate-300 sm:flex-row sm:items-center">
              <p>Xây dựng cho quy trình lâm sàng Việt Nam.</p>
              <p className="text-xs uppercase tracking-[0.12em] text-slate-400">Chat • Council • Safety • Scribe • Quản trị</p>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
