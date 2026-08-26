"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { AmbientField } from "../primitives/ambient-field";
import { RevealGroup } from "../primitives/reveal-group";
import { Reveal } from "../primitives/reveal";
import { ContextConstellation } from "../artwork/context-constellation";
import { ClaraOrb } from "../artwork/clara-orb";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

/**
 * ManifestoScene (Spatial Longitudinal Context Constellation)
 *
 * Demonstrates how 5 independent clinical context streams converge:
 * - Active Medications (Thuốc đang dùng)
 * - Recent Changes (Thay đổi gần đây)
 * - Health Record (Hồ sơ sức khỏe)
 * - Prior Questions (Câu hỏi trước đây)
 * - Evidence Sources (Nguồn y văn đối chiếu)
 *
 * Connected via animated vector energy splines to the central ClaraOrb Core hub.
 */
export function ManifestoScene() {
  const { language, isReducedMotion } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.manifesto ?? LANDING_COPY_V7.vi.manifesto;
  const [activeNode, setActiveNode] = useState<string>("clara-core");

  const nodesNav =
    lang === "vi"
      ? [
          { id: "clara-core", label: "CLARA Core", icon: "✦" },
          { id: "medications", label: "Thuốc đang dùng", icon: "💊" },
          { id: "recent-changes", label: "Thay đổi gần đây", icon: "⏱" },
          { id: "health-record", label: "Hồ sơ sức khỏe", icon: "🛡" },
          { id: "prior-questions", label: "Câu hỏi trước đây", icon: "💬" },
          { id: "evidence-sources", label: "Y văn đối chiếu", icon: "📖" },
        ]
      : [
          { id: "clara-core", label: "CLARA Core", icon: "✦" },
          { id: "medications", label: "Medications", icon: "💊" },
          { id: "recent-changes", label: "Recent Changes", icon: "⏱" },
          { id: "health-record", label: "Health Record", icon: "🛡" },
          { id: "prior-questions", label: "Prior Questions", icon: "💬" },
          { id: "evidence-sources", label: "Evidence Sources", icon: "📖" },
        ];

  return (
    <LandingScene
      id="manifesto"
      scale="signature"
      tone="azure"
      className="overflow-hidden relative py-20 md:py-28 clara-transition-trust-manifesto"
    >
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Top Transition Ribbon from Trust Scene */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-14 opacity-35"
      >
        <EvidenceRibbon variant="curved" tone="iris" active={!isReducedMotion} className="w-full max-w-6xl" />
      </div>

      {/* Editorial Header Section */}
      <div className="text-center max-w-4xl mx-auto mb-10 px-4 relative z-10">
        <RevealGroup staggerMs={80}>
          <Reveal delayMs={0} direction="up">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#EFF7FF] px-3.5 py-1 text-xs font-bold uppercase tracking-widest text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
              {copy.eyebrow}
            </span>
          </Reveal>

          <Reveal delayMs={80} direction="up">
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#162033] leading-tight mt-3 whitespace-pre-line">
              {copy.headline}
            </h2>
          </Reveal>

          <Reveal delayMs={160} direction="up">
            <p className="text-base sm:text-lg text-[#48566A] mt-4 max-w-2xl mx-auto leading-relaxed">
              {copy.subheadline}
            </p>
          </Reveal>
        </RevealGroup>
      </div>

      {/* Quick Stream Inspector Navigation Filter */}
      <div className="flex justify-center mb-6 px-4 relative z-10">
        <div
          role="tablist"
          aria-label={lang === "vi" ? "Bộ chọn bối cảnh hội tụ" : "Context Stream Selector"}
          className="inline-flex flex-wrap items-center justify-center gap-1.5 rounded-2xl bg-white/90 backdrop-blur-md p-1.5 border border-[#E3E8EF] shadow-sm max-w-3xl"
        >
          {nodesNav.map((node) => {
            const isSelected = activeNode === node.id;
            return (
              <button
                key={node.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                onClick={() => setActiveNode(node.id)}
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all clara-focus-ring cursor-pointer ${
                  isSelected
                    ? "bg-[#0B6FD8] text-white shadow-xs scale-102"
                    : "text-[#48566A] hover:text-[#162033] hover:bg-[#F8FAFD]"
                }`}
              >
                <span>{node.icon}</span>
                <span>{node.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Spatial Constellation Canvas with Central ClaraOrb and Animated Energy Connectors */}
      <Reveal delayMs={120} direction="scale">
        <div className="relative mx-auto max-w-5xl px-2 sm:px-4 z-10">
          <ContextConstellation
            language={lang}
            activeNodeId={activeNode}
            onNodeClick={(id) => setActiveNode(id)}
          />
        </div>
      </Reveal>

      {/* Resolving Statement with Glowing ClaraOrb Anchor */}
      <Reveal delayMs={240} direction="up">
        <div className="text-center mt-12 px-4 relative z-10">
          <div className="inline-flex flex-wrap items-center justify-center gap-3 rounded-2xl bg-[#EFF7FF] px-6 py-3.5 border border-[#0B6FD8]/20 shadow-md backdrop-blur-xs hover:border-[#0B6FD8]/35 transition-all">
            <ClaraOrb size="sm" tone="azure" pulse={!isReducedMotion} />
            <span className="text-sm sm:text-base font-bold text-[#0B6FD8]">
              ➔ {copy.resolveStatement}
            </span>
          </div>
        </div>
      </Reveal>

      {/* Downward Transition Ribbon Towards How-it-Works Pipeline */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/3 w-80 opacity-45 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={!isReducedMotion} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default ManifestoScene;

