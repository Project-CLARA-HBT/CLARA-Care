"use client";

import React from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";
import { ChatDemo } from "../demo/chat-demo";

export function ChatScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language];

  return (
    <LandingScene id="chat" scale="signature" tone="azure">
      <SceneHeader
        eyebrow={copy.chat.eyebrow}
        title={copy.chat.title}
        description={copy.chat.description}
        align="center"
        tone="azure"
      />
      <div className="mx-auto max-w-5xl w-full">
        <ChatDemo />
      </div>
    </LandingScene>
  );
}
