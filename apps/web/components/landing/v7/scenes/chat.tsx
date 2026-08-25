"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { ChatDemo } from "../demo/chat-demo";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";
import { AmbientField } from "../primitives/ambient-field";

export function ChatScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.chat ?? LANDING_COPY_V7.vi.chat;

  return (
    <LandingScene id="chat" scale="signature" tone="azure" className="relative overflow-hidden clara-transition-how-chat">
      {/* Ambient Lighting Field */}
      <AmbientField tone="azure" />

      {/* Top Transition Ribbon from How */}
      <div
        aria-hidden="true"
        className="clara-ribbon-handoff-bridge top-0 h-14 opacity-35"
      >
        <EvidenceRibbon variant="horizontal" tone="azure" active={true} className="w-full max-w-5xl" />
      </div>

      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="center"
        tone="azure"
      />
      <div className="mx-auto max-w-5xl w-full relative z-10">
        <ChatDemo />
      </div>

      {/* Downward Transition Ribbon Towards LifeMap Continuum (Peak 3) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-8 left-1/4 w-80 opacity-40 hidden md:block"
      >
        <EvidenceRibbon variant="curved" tone="azure" active={true} className="h-16 w-full" />
      </div>
    </LandingScene>
  );
}

export default ChatScene;
