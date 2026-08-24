"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { ChatDemo } from "../demo/chat-demo";

export function ChatScene() {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.chat ?? LANDING_COPY_V7.vi.chat;

  return (
    <LandingScene id="chat" scale="signature" tone="azure">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="center"
        tone="azure"
      />
      <div className="mx-auto max-w-5xl w-full">
        <ChatDemo />
      </div>
    </LandingScene>
  );
}

export default ChatScene;
