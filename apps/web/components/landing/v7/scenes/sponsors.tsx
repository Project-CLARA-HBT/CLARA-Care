"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LandingScene } from "../primitives/landing-scene";
import { Reveal } from "../primitives/reveal";

export function SponsorsScene() {
  const { language } = useMotionTier();
  const isVi = language !== "en";

  const partners = [
    {
      name: "Hitech Cloud",
      category: isVi ? "Tài trợ Hạ tầng Máy chủ & Cloud GPU AI" : "Cloud AI & GPU Infrastructure Sponsor",
      logo: "/partners/hitechcloud.svg",
      fallbackText: "HITECH CLOUD",
      href: "https://hitechcloud.vn",
      badge: isVi ? "Đơn vị Tài trợ Hạ tầng" : "Infrastructure Partner",
      highlight: true,
    },
    {
      name: "VNIX / BNIX",
      category: isVi ? "Kết nối Mạng & Internet Y tế Quốc gia" : "National Internet Exchange & Connectivity",
      logo: "/partners/bnix-local.png",
      fallbackText: "BNIX",
      href: "https://bnix.vn",
      badge: isVi ? "Hạ tầng Kết nối" : "Network Partner",
      highlight: true,
    },
    {
      name: "Bộ Y Tế Việt Nam (DAV)",
      category: isVi ? "Dược thư Quốc gia Việt Nam & Hướng dẫn Điều trị" : "Vietnam National Pharmacopoeia & MoH Guidelines",
      badge: isVi ? "Cơ sở Dữ liệu Chuẩn" : "National Standard",
      highlight: false,
    },
    {
      name: "Đại học Y Dược TP.HCM",
      category: isVi ? "Hội đồng Cố vấn Chuyên môn & Đào tạo Lâm sàng" : "Clinical Advisory & Academic Partner",
      badge: isVi ? "Cố vấn Học thuật" : "Academic Council",
      highlight: false,
    },
    {
      name: "DrugBank Academic",
      category: isVi ? "Cơ sở Dữ liệu Dược lý & Tương tác Thuốc Quốc tế" : "Global Pharmacology & DDI Knowledge Base",
      badge: isVi ? "Đối tác Dược lý" : "Pharmacology DB",
      highlight: false,
    },
    {
      name: "PubMed / NCBI / NLM",
      category: isVi ? "Kho Dữ liệu Nghiên cứu & Y văn Toàn cầu" : "Biomedical Literature & Clinical Evidence",
      badge: isVi ? "Nguồn Y văn" : "Evidence Base",
      highlight: false,
    },
    {
      name: "US FDA / DailyMed",
      category: isVi ? "Nhãn Dược phẩm & Cảnh báo An toàn Thuốc" : "Drug Labels & Safety Alerts",
      badge: isVi ? "Cảnh báo An toàn" : "Safety Alerts",
      highlight: false,
    },
  ];

  return (
    <LandingScene
      id="sponsors"
      scale="transition"
      tone="subtle"
      className="py-12 sm:py-16 border-y border-[#E3E8EF] bg-[#F8FAFD]/90 relative overflow-hidden"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8 relative z-10">
        {/* Section Header */}
        <Reveal delayMs={0} direction="up">
          <div className="space-y-2 max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-2 rounded-full bg-[#0B6FD8]/10 px-3.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
              <span>{isVi ? "ĐƠN VỊ ĐỒNG HÀNH & HẠ TẦNG Y TẾ" : "INSTITUTIONAL PARTNERS & INFRASTRUCTURE"}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#162033]">
              {isVi
                ? "Được tin cậy và đồng hành phát triển cùng các đơn vị hàng đầu"
                : "Trusted and powered by leading infrastructure & medical institutions"}
            </h2>
            <p className="text-xs sm:text-sm text-[#48566A]">
              {isVi
                ? "Hệ sinh thái kết nối máy chủ GPU hiệu năng cao, trạm trung chuyển Internet quốc gia và kho dữ liệu y văn chính thống."
                : "Connected ecosystem of high-performance AI compute, national network exchange, and authoritative medical databases."}
            </p>
          </div>
        </Reveal>

        {/* Primary Sponsors Showcase */}
        <Reveal delayMs={90} direction="up">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
            {partners.slice(0, 4).map((item) => {
              const cardContent = (
                <div
                  className={`flex flex-col justify-between p-5 rounded-2xl bg-white border transition-all duration-200 text-left h-full group ${
                    item.highlight
                      ? "border-[#0B6FD8]/30 shadow-xs hover:border-[#0B6FD8] hover:shadow-md hover:-translate-y-0.5"
                      : "border-[#E3E8EF] hover:border-[#CBD5E1] hover:shadow-xs"
                  }`}
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8] bg-[#EFF7FF] px-2.5 py-0.5 rounded-full border border-[#0B6FD8]/20">
                        {item.badge}
                      </span>
                      {item.href && (
                        <span className="text-xs text-[#6D7A8E] group-hover:text-[#0B6FD8] transition-colors" aria-hidden="true">
                          ↗
                        </span>
                      )}
                    </div>

                    <div className="h-10 flex items-center">
                      {item.logo ? (
                        <div className="relative h-8 w-36">
                          <Image
                            src={item.logo}
                            alt={item.name}
                            fill
                            className="object-contain object-left filter contrast-125"
                            sizes="150px"
                          />
                        </div>
                      ) : (
                        <h3 className="font-extrabold text-base text-[#162033] group-hover:text-[#0B6FD8] transition-colors">
                          {item.name}
                        </h3>
                      )}
                    </div>

                    <p className="text-xs text-[#6D7A8E] leading-relaxed line-clamp-2">
                      {item.category}
                    </p>
                  </div>
                </div>
              );

              if (item.href) {
                return (
                  <a
                    key={item.name}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block h-full focus:outline-none focus:ring-2 focus:ring-[#0B6FD8] rounded-2xl"
                  >
                    {cardContent}
                  </a>
                );
              }

              return <div key={item.name}>{cardContent}</div>;
            })}
          </div>
        </Reveal>

        {/* Secondary Evidence & Pharmacology Sources Ribbon */}
        <Reveal delayMs={180} direction="up">
          <div className="pt-2 flex flex-wrap items-center justify-center gap-3 max-w-4xl mx-auto">
            {partners.slice(4).map((source) => (
              <div
                key={source.name}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E3E8EF] shadow-2xs text-xs text-[#48566A]"
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="font-bold text-[#162033]">{source.name}</span>
                <span className="text-[11px] text-[#6D7A8E] hidden sm:inline">• {source.category}</span>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </LandingScene>
  );
}

export default SponsorsScene;
