"use client";

import React from "react";

export interface WaveformVisualizerProps {
  /** Array of 32 bar heights (0-100) */
  bars: number[];
  /** Whether recording is currently active */
  isRecording?: boolean;
  /** Custom height for the waveform container */
  className?: string;
}

export const DEFAULT_WAVE_BARS = Array.from({ length: 32 }, () => 8);

export function WaveformVisualizer({
  bars = DEFAULT_WAVE_BARS,
  isRecording = false,
  className = "",
}: WaveformVisualizerProps) {
  // Ensure exactly 32 bars are rendered
  const displayBars = bars.length === 32 ? bars : Array.from({ length: 32 }, (_, i) => bars[i % bars.length] ?? 8);

  return (
    <div
      role="img"
      aria-label={isRecording ? "Live audio recording waveform visualizer" : "Audio waveform visualizer idle"}
      className={`flex items-center justify-center gap-1 sm:gap-1.5 h-20 px-4 select-none ${className}`}
      data-testid="scribe-waveform-visualizer"
    >
      {displayBars.map((bar, index) => {
        const heightPercent = Math.max(8, Math.min(100, bar));
        return (
          <div
            key={index}
            style={{ height: `${heightPercent}%` }}
            className={`w-1.5 sm:w-2 rounded-full transition-all duration-75 ease-out ${
              isRecording
                ? "bg-rose-500 shadow-sm shadow-rose-500/50"
                : "bg-[var(--text-muted)] opacity-30"
            }`}
          />
        );
      })}
    </div>
  );
}

export default WaveformVisualizer;
