"use client";

import React from "react";
import Image from "next/image";
import { useMotionTier } from "../runtime/motion-provider";
import { LandingScene } from "../primitives/landing-scene";
import { Reveal } from "../primitives/reveal";
import { ClaraOrb } from "../artwork/clara-orb";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

export function SponsorsScene() {
  const { language, isReducedMotion } = useMotionTier();
  const isVi = language !== "en";

  const primarySponsors = [
    {
      name: "Hitech Cloud",
      category: isVi
        ? "Tài trợ Hạ tầng Máy chủ & GPU AI Hiệu năng cao"
        : "High-Performance Cloud GPU & Server Infrastructure",
      logo: "/partners/hitechcloudvntrang.png",
      href: "https://hitechcloud.vn",
      badge: isVi ? "Tài trợ Điện toán Đám mây & AI" : "Cloud & AI Infrastructure Sponsor",
      domain: "hitechcloud.vn",
    },
    {
      name: "VNIX / BNIX",
      category: isVi
        ? "Hạ tầng Kết nối Mạng & Băng thông Internet Y tế"
        : "National Internet Exchange & High-Speed Healthcare Network",
      logo: "/partners/bnix-local.png",
      href: "https://bnix.vn",
      badge: isVi ? "Hạ tầng Kết nối Mạng" : "Network Exchange Partner",
      domain: "bnix.vn",
    },
  ];

  const knowledgeSources = [
    {
      name: "Bộ Y Tế Việt Nam (DAV)",
      category: isVi ? "Dược thư Quốc gia Việt Nam & Phác đồ Điều trị" : "Vietnam National Pharmacopoeia & MoH Guidelines",
      badge: isVi ? "Dược thư Quốc gia" : "National Standard",
    },
    {
      name: "DrugBank Academic",
      category: isVi ? "Cơ sở Dữ liệu Dược lý & Tương tác Thuốc Toàn cầu" : "Global Pharmacology & DDI Knowledge Base",
      badge: isVi ? "Dược lý Chuẩn" : "Pharmacology DB",
    },
    {
      name: "PubMed / NCBI / NLM",
      category: isVi ? "Kho Dữ liệu Nghiên cứu Y học Quốc tế" : "Biomedical Literature & Clinical Evidence",
      badge: isVi ? "Y văn Lâm sàng" : "Evidence Base",
    },
    {
      name: "US FDA / DailyMed",
      category: isVi ? "Nhãn Dược phẩm & Cảnh báo An toàn Thuốc" : "Drug Labels & Safety Alerts",
      badge: isVi ? "Cảnh báo An toàn" : "Safety Alerts",
    },
  ];

  return (
    <LandingScene
      id="sponsors"
      scale="transition"
      tone="neutral"
      className="py-14 sm:py-20 border-y border-[#E3E8EF] clara-transition-hero-sponsors relative overflow-hidden"
    >
      {/* Ambient background transition ribbons connecting from Hero */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge -top-8 opacity-45"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={!isReducedMotion} className="w-full max-w-6xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-10 relative z-10">
        {/* Section Header with integrated mini Orb */}
        <Reveal delayMs={0} direction="up">
          <div className="space-y-3 max-w-3xl mx-auto flex flex-col items-center">
            <div className="inline-flex items-center gap-2 rounded-full bg-[#0B6FD8]/10 px-4 py-1.5 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs backdrop-blur-xs">
              <span className="w-2 h-2 rounded-full bg-[#0B6FD8] animate-pulse" />
              <span>{isVi ? "ĐƠN VỊ ĐỒNG HÀNH & HẠ TẦNG Y TẾ" : "INSTITUTIONAL PARTNERS & INFRASTRUCTURE"}</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#162033]">
              {isVi
                ? "Được tin cậy và đồng hành phát triển cùng các đơn vị hàng đầu"
                : "Trusted and powered by leading infrastructure & medical institutions"}
            </h2>
            <p className="text-xs sm:text-sm text-[#48566A] max-w-2xl leading-relaxed">
              {isVi
                ? "Hệ sinh thái hạ tầng máy chủ GPU chuyên dụng, trạm kết nối Internet quốc gia và kho dữ liệu y văn chính thống."
                : "Connected ecosystem of dedicated AI compute, national network exchange, and authoritative biomedical databases."}
            </p>
          </div>
        </Reveal>

        {/* 2 Primary Sponsors on Sleek Dark Slate Cards */}
        <Reveal delayMs={100} direction="up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {primarySponsors.map((item) => (
              <a
                key={item.name}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                className="group relative flex flex-col justify-between p-7 sm:p-8 rounded-3xl bg-gradient-to-br from-[#0B1120] via-[#0F172A] to-[#1E293B] border border-[#1E293B] text-left transition-all duration-300 shadow-xl hover:shadow-2xl hover:border-[#38BDF8]/60 hover:-translate-y-1 hover:scale-[1.01] focus:outline-none focus:ring-2 focus:ring-[#38BDF8] overflow-hidden"
              >
                {/* Ambient Card Glow */}
                <div
                  aria-hidden="true"
                  className="absolute -top-12 -right-12 w-44 h-44 rounded-full bg-[#0B6FD8]/15 blur-2xl group-hover:bg-[#38BDF8]/25 transition-all duration-500 pointer-events-none"
                />

                <div className="space-y-5 relative z-10">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-[#38BDF8] bg-[#38BDF8]/10 px-3 py-1 rounded-full border border-[#38BDF8]/30">
                      {item.badge}
                    </span>
                    <span className="text-xs font-semibold text-slate-400 group-hover:text-[#38BDF8] transition-colors flex items-center gap-1">
                      {item.domain}
                      <span aria-hidden="true">↗</span>
                    </span>
                  </div>

                  {/* High-contrast dark logo presentation */}
                  <div className="h-14 flex items-center bg-[#020617]/50 rounded-2xl px-5 border border-slate-800/80 group-hover:border-slate-700/80 transition-colors">
                    <div className="relative h-10 w-44">
                      <Image
                        src={item.logo}
                        alt={item.name}
                        fill
                        className="object-contain object-left filter brightness-110 drop-shadow-md"
                        sizes="200px"
                      />
                    </div>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed group-hover:text-white transition-colors">
                    {item.category}
                  </p>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 relative z-10">
                  <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    {isVi ? "Hạ tầng Đang hoạt động" : "Operational & Verified"}
                  </span>
                  <span className="group-hover:translate-x-0.5 transition-transform text-[#38BDF8] font-bold">
                    {isVi ? "Khám phá" : "Explore"} →
                  </span>
                </div>
              </a>
            ))}
          </div>
        </Reveal>

        {/* Verified Knowledge Bases & Pharmacology Sources */}
        <Reveal delayMs={180} direction="up">
          <div className="pt-4 space-y-3 max-w-4xl mx-auto">
            <div className="text-[11px] font-bold uppercase tracking-widest text-[#6D7A8E]">
              {isVi ? "Nguồn Y văn & Cơ sở Dữ liệu Dược thư Tham chiếu" : "Authoritative Biomedical & Pharmacology Databases"}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {knowledgeSources.map((source) => (
                <div
                  key={source.name}
                  className="flex flex-col justify-between p-4 rounded-2xl bg-white border border-[#E3E8EF] shadow-2xs hover:shadow-xs hover:border-[#0B6FD8]/30 transition-all text-left group"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                      <span className="font-bold text-xs text-[#162033] group-hover:text-[#0B6FD8] transition-colors truncate">
                        {source.name}
                      </span>
                    </div>
                    <p className="text-[10px] text-[#6D7A8E] line-clamp-2 leading-relaxed">
                      {source.category}
                    </p>
                  </div>
                  <span className="text-[9px] font-bold uppercase text-[#0B6FD8] bg-[#EFF7FF] px-2 py-0.5 rounded-md border border-[#0B6FD8]/15 mt-3 self-start">
                    {source.badge}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>

      {/* Downward transition ribbon */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 right-1/4 w-80 opacity-50 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="mint" active={!isReducedMotion} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default SponsorsScene;
