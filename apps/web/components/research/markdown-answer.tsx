"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toPng } from "html-to-image";
import type { UILanguage } from "@/lib/ui-language";
import { formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { exportWorkspaceDocxFromMarkdown } from "@/lib/workspace";
import { Icon } from "@/components/ui/icon";
import {
  citationRegistryAnchorId,
  injectTracedClaimAnchors,
  type ResearchTier2CitationRegistryEntry,
  type ResearchTier2TracedClaim
} from "@/lib/research";

export type MarkdownAnswerCitation = {
  title: string;
  url?: string;
};

export type MarkdownAnswerProps = {
  answer: string;
  citations: MarkdownAnswerCitation[];
  showInlineCitations?: boolean;
  enableMermaid?: boolean;
  stripReferenceSection?: boolean;
  stripSafetyMatrixSection?: boolean;
  stripMermaidBlocks?: boolean;
  stripChartSpecBlocks?: boolean;
  uiLanguage?: UILanguage;
  /**
   * Claim-to-study traceability (Requirement 11.1). When provided alongside a
   * non-empty `citationRegistry`, inline sentence-level anchors are rendered
   * after each matched claim (Requirement 11.3). Absent/empty preserves the
   * legacy answer rendering.
   */
  tracedClaims?: ResearchTier2TracedClaim[];
  /**
   * Citation Registry appendix entries (Requirement 11.4). Rendered as a
   * resolvable appendix below the answer so every inline anchor links to its
   * registry row. Absent/empty renders nothing extra.
   */
  citationRegistry?: ResearchTier2CitationRegistryEntry[];
};

type MermaidBlockProps = {
  code: string;
  uiLanguage: UILanguage;
};

type CodeFenceProps = {
  code: string;
  language?: string;
  isChartSpec: boolean;
  uiLanguage: UILanguage;
};

type ChartSpecData = {
  type: "bar" | "pie";
  title: string;
  labels: string[];
  values: number[];
};

type SectionTone = "brand" | "evidence" | "safety" | "warning" | "neutral";

const ALLOWED_EXTERNAL_PROTOCOLS = new Set(["http:", "https:"]);
const CHART_SPEC_LANGUAGES = new Set(["chart", "chart-spec", "vega-lite", "echarts-option", "json", "yaml", "yml"]);

function normalizeHeadingKey(input: string): string {
  return input
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function resolveSectionTone(title: string): SectionTone {
  const key = normalizeHeadingKey(title);
  if (
    key.includes("bang tong hop")
    || key.includes("nguon tham chieu")
    || key.includes("ma tran")
    || key.includes("evidence")
    || key.includes("sources")
  ) {
    return "evidence";
  }
  if (
    key.includes("khuyen nghi")
    || key.includes("ke hoach theo doi")
    || key.includes("practical application")
    || key.includes("next steps")
  ) {
    return "safety";
  }
  if (
    key.includes("canh bao")
    || key.includes("phap ly")
    || key.includes("gioi han")
    || key.includes("caveat")
    || key.includes("safety note")
  ) {
    return "warning";
  }
  if (
    key.includes("ket luan")
    || key.includes("tom tat")
    || key.includes("boi canh")
    || key.includes("quick conclusion")
    || key.includes("key points")
    || key.includes("bottom line")
  ) {
    return "brand";
  }
  return "neutral";
}

function sectionHeadingClasses(tone: SectionTone): string {
  switch (tone) {
    case "brand":
      return "mt-6 text-[1rem] font-semibold tracking-tight text-[var(--text-primary)] first:mt-0";
    case "evidence":
      return "mt-6 border-t border-[color:var(--shell-border)] pt-2.5 text-[0.96rem] font-semibold tracking-tight text-[var(--text-primary)] first:mt-0 first:border-t-0 first:pt-0";
    case "safety":
      return "mt-6 border-t border-[color:var(--status-ok-border)] pt-2.5 text-[0.96rem] font-semibold tracking-tight text-[var(--text-primary)] first:mt-0 first:border-t-0 first:pt-0";
    case "warning":
      return "mt-6 border-t border-[color:var(--status-warn-border)] pt-2.5 text-[0.96rem] font-semibold tracking-tight text-[var(--text-primary)] first:mt-0 first:border-t-0 first:pt-0";
    default:
      return "mt-6 border-t border-[color:var(--shell-border)] pt-2.5 text-[0.96rem] font-semibold tracking-tight text-[var(--text-primary)] first:mt-0 first:border-t-0 first:pt-0";
  }
}

function sanitizeHref(href: string | undefined): string | undefined {
  if (!href) return undefined;
  const trimmed = href.trim();
  if (!trimmed) return undefined;
  if (trimmed.startsWith("#") || trimmed.startsWith("/")) return trimmed;

  try {
    const parsed = new URL(trimmed, "https://clara.local");
    if (!ALLOWED_EXTERNAL_PROTOCOLS.has(parsed.protocol)) return undefined;
    return parsed.toString();
  } catch {
    return undefined;
  }
}

function sanitizeMermaidSvg(svg: string): string {
  if (typeof window === "undefined" || typeof window.DOMParser === "undefined") {
    return svg;
  }

  try {
    // Repair common XML-invalid tags sometimes emitted inside Mermaid SVG labels.
    const repaired = svg
      .replace(/<br(\s+[^/>]*)?>/gi, (_full, attrs = "") => `<br${attrs} />`)
      .replace(/<\/br>/gi, "")
      .replace(/<hr(\s+[^/>]*)?>/gi, (_full, attrs = "") => `<hr${attrs} />`)
      .replace(/<\/hr>/gi, "");

    const parser = new window.DOMParser();
    const parsed = parser.parseFromString(repaired, "image/svg+xml");
    if (
      parsed.documentElement?.nodeName?.toLowerCase() === "parsererror" ||
      parsed.querySelector("parsererror")
    ) {
      return "";
    }

    // Remove risky containers/tags before injecting into the DOM.
    parsed.querySelectorAll("script, iframe, object, embed, foreignObject").forEach((node) => {
      node.remove();
    });

    parsed.querySelectorAll("*").forEach((element) => {
      for (const attr of Array.from(element.attributes)) {
        const name = attr.name.toLowerCase();
        const value = attr.value.trim().toLowerCase();

        if (name.startsWith("on")) {
          element.removeAttribute(attr.name);
          continue;
        }

        if ((name === "href" || name === "xlink:href") && (value.startsWith("javascript:") || value.startsWith("data:"))) {
          element.removeAttribute(attr.name);
        }
      }
    });

    // Force readable text color for common Mermaid label nodes.
    parsed.querySelectorAll("text, tspan").forEach((node) => {
      const current = node.getAttribute("fill")?.trim().toLowerCase() ?? "";
      if (!current || current === "none" || current === "transparent") {
        node.setAttribute("fill", "#e1e2e9");
      }
      if (!node.getAttribute("font-family")) {
        node.setAttribute("font-family", "Inter, Segoe UI, Arial, sans-serif");
      }
    });

    const svgEl = parsed.documentElement;
    const styleEl = parsed.createElementNS("http://www.w3.org/2000/svg", "style");
    styleEl.textContent = `
      text, tspan, .label, .nodeLabel { fill: #e1e2e9 !important; color: #e1e2e9 !important; }
    `;
    svgEl.insertBefore(styleEl, svgEl.firstChild);

    return parsed.documentElement.outerHTML || "";
  } catch {
    return "";
  }
}

function parseInlineList(input: string): string[] {
  const trimmed = input.trim();
  if (!trimmed.startsWith("[") || !trimmed.endsWith("]")) return [];
  return trimmed
    .slice(1, -1)
    .split(",")
    .map((item) => item.trim().replace(/^["']|["']$/g, ""))
    .filter(Boolean);
}

function parseNumberLike(input: string): number | null {
  const normalized = input.trim().replace(/_/g, "");
  if (!normalized) return null;
  const value = Number(normalized);
  return Number.isFinite(value) ? value : null;
}

function parseChartSpec(code: string): ChartSpecData | null {
  const raw = code.trim();
  if (!raw) return null;

  // JSON-like chart spec support
  if (raw.startsWith("{") && raw.endsWith("}")) {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      const type = String(parsed.type || "").toLowerCase();
      const labels = Array.isArray(parsed.x) ? parsed.x.map(String) : [];
      const values = Array.isArray(parsed.y) ? parsed.y.map((item) => Number(item)) : [];
      if ((type === "bar" || type === "pie") && labels.length && labels.length === values.length) {
        return {
          type,
          title: String(parsed.title || "Biểu đồ dữ liệu"),
          labels,
          values: values.map((value) => (Number.isFinite(value) ? value : 0)),
        };
      }
    } catch {
      // Continue fallback parser
    }
  }

  // Simple YAML-like parser for current backend contract.
  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean);
  let type: "bar" | "pie" = "bar";
  let title = "Biểu đồ dữ liệu";
  let labels: string[] = [];
  const values: number[] = [];
  let inYBlock = false;

  for (const line of lines) {
    if (line.startsWith("type:")) {
      const value = line.slice("type:".length).trim().toLowerCase();
      if (value === "pie") type = "pie";
      if (value === "bar") type = "bar";
      inYBlock = false;
      continue;
    }
    if (line.startsWith("title:")) {
      title = line.slice("title:".length).trim().replace(/^["']|["']$/g, "") || title;
      inYBlock = false;
      continue;
    }
    if (line.startsWith("x:")) {
      labels = parseInlineList(line.slice("x:".length));
      inYBlock = false;
      continue;
    }
    if (line.startsWith("y:")) {
      const inline = line.slice("y:".length).trim();
      if (inline.startsWith("[")) {
        parseInlineList(inline).forEach((token) => {
          const num = parseNumberLike(token);
          if (num !== null) values.push(num);
        });
        inYBlock = false;
      } else {
        inYBlock = true;
      }
      continue;
    }
    if (inYBlock && line.startsWith("- ")) {
      const num = parseNumberLike(line.slice(2));
      if (num !== null) values.push(num);
      continue;
    }
    inYBlock = false;
  }

  if (!labels.length || !values.length || labels.length !== values.length) {
    return null;
  }
  return { type, title, labels, values };
}

function formatChartValue(uiLanguage: UILanguage, value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (Math.abs(value) >= 1000) return formatLocaleNumber(uiLanguage, value);
  if (Math.abs(value) >= 1) return value.toFixed(2).replace(/\.00$/, "");
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function ChartSpecPreview({ spec, uiLanguage }: { spec: ChartSpecData; uiLanguage: UILanguage }) {
  const max = Math.max(...spec.values, 0.000001);
  const total = spec.values.reduce((sum, item) => sum + Math.max(item, 0), 0);

  return (
    <section className="rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
        {t(uiLanguage, "markdownAnswer.chart.preview")} · {spec.type.toUpperCase()}
      </p>
      <h4 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{spec.title}</h4>
      {spec.type === "pie" ? (
        <div className="mt-3 space-y-2">
          {spec.labels.map((label, index) => {
            const value = spec.values[index] ?? 0;
            const pct = total > 0 ? (Math.max(value, 0) / total) * 100 : 0;
            return (
              <div key={`${label}-${index}`} className="space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--text-secondary)]">
                  <span>{label}</span>
                  <span>{formatChartValue(uiLanguage, value)} ({pct.toFixed(1)}%)</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-highest)]">
                  <div
                    className="h-full rounded-full bg-[var(--brand-primary)]"
                    style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          {spec.labels.map((label, index) => {
            const value = spec.values[index] ?? 0;
            const ratio = Math.max(0, value) / max;
            return (
              <div key={`${label}-${index}`} className="grid grid-cols-[minmax(120px,1fr)_4fr_auto] items-center gap-2 text-xs">
                <span className="truncate text-[var(--text-secondary)]" title={label}>{label}</span>
                <div className="h-2 overflow-hidden rounded bg-[var(--surface-highest)]">
                  <div
                    className="h-full rounded bg-[var(--brand-600)]"
                    style={{ width: `${Math.min(Math.max(ratio * 100, 0), 100)}%` }}
                  />
                </div>
                <span className="font-medium text-[var(--text-primary)]">{formatChartValue(uiLanguage, value)}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function normalizeMermaidCode(code: string): string {
  let normalized = code.replace(/\r\n/g, "\n").trim();
  if (!normalized) return normalized;

  normalized = normalized
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/&lt;br\s*\/?&gt;/gi, "\n")
    .replace(/<\/?p\b[^>]*>/gi, "")
    .replace(/<\/?div\b[^>]*>/gi, "")
    .replace(/&nbsp;/gi, " ");

  normalized = normalized
    .split("\n")
    .map((line) => line.trimEnd())
    .map((line) => line.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/gi, "$1"))
    .map((line) =>
      line.replace(
        /\[((?:pubmed|pmid|doi|source|ref|nih|fda|who|rxnav|openfda)[^\]\n]*)\]/gi,
        "($1)"
      )
    )
    .map((line) => line.replace(/\[(\d{1,3})\]/g, "($1)"))
    .map((line) => {
      let value = line;
      let guard = 0;
      const nestedPattern = /\[([^\[\]\n]*)\[([^\[\]\n]+)\]([^\[\]\n]*)\]/g;
      while (nestedPattern.test(value) && guard < 8) {
        value = value.replace(nestedPattern, "[$1($2)$3]");
        guard += 1;
      }
      return value;
    })
    .map((line) => {
      const opens = (line.match(/\[/g) ?? []).length;
      const closes = (line.match(/\]/g) ?? []).length;
      if (closes <= opens) return line;
      let diff = closes - opens;
      const chars = line.split("");
      for (let index = chars.length - 1; index >= 0 && diff > 0; index -= 1) {
        if (chars[index] === "]") {
          chars.splice(index, 1);
          diff -= 1;
        }
      }
      return chars.join("");
    })
    .filter((line, index, arr) => !(line.trim() === "" && arr[index - 1]?.trim() === ""))
    .join("\n")
    .trim();

  return normalized;
}

function buildMermaidRenderCandidates(rawCode: string): string[] {
  const base = normalizeMermaidCode(rawCode);
  if (!base) return [];

  const relaxed = base
    .replace(/\[(pubmed-\d+|pmid:?\s*\d+|doi:[^\]\n]+)\]/gi, "($1)")
    .replace(/\]\];/g, "];")
    .replace(/\]\]\s*-->/g, "] -->");

  return Array.from(new Set([base, relaxed].filter(Boolean)));
}

function MermaidBlock({ code, uiLanguage }: MermaidBlockProps) {
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function renderMermaid() {
      try {
        const mermaidModule = await import("mermaid");
        const mermaid = mermaidModule.default;
        const candidates = buildMermaidRenderCandidates(code);
        if (!candidates.length) {
          throw new Error("Mermaid code is empty.");
        }
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "default",
          flowchart: {
            htmlLabels: false,
            useMaxWidth: true,
          },
        });

        let renderedSvg = "";
        let lastError: unknown = null;
        for (const candidate of candidates) {
          try {
            const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;
            const renderResult = await mermaid.render(id, candidate);
            renderedSvg = renderResult.svg;
            lastError = null;
            break;
          } catch (error) {
            lastError = error;
          }
        }
        if (!renderedSvg) {
          throw (lastError instanceof Error ? lastError : new Error("Không thể parse Mermaid."));
        }
        if (!cancelled) {
          const sanitized = sanitizeMermaidSvg(renderedSvg);
          if (!sanitized) {
            throw new Error("Mermaid SVG output is empty after sanitization.");
          }
          setSvg(sanitized);
          setError("");
        }
      } catch (cause) {
        if (!cancelled) {
          setSvg("");
          setError(safeUserFacingError(cause, t(uiLanguage, "markdownAnswer.export.unknownError")));
        }
      }
    }

    void renderMermaid();
    return () => {
      cancelled = true;
    };
  }, [code, uiLanguage]);

  if (error) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]">
        {t(uiLanguage, "markdownAnswer.mermaid.error")}: {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        {t(uiLanguage, "markdownAnswer.mermaid.loading")}
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
      <div className="flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
        <span>{t(uiLanguage, "markdownAnswer.mermaid.diagram")}</span>
        <span className="rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2 py-0.5 text-[10px] text-[var(--text-brand)]">
          {t(uiLanguage, "markdownAnswer.mermaid.safe")}
        </span>
      </div>
      <div
        className="overflow-x-auto p-3"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </section>
  );
}

const UNICODE_BULLET_PATTERN = /^(\s*)[•●▪◦]\s+(.*)$/;
const MERMAID_START_PREFIXES = [
  "flowchart",
  "graph ",
  "sequencediagram",
  "classdiagram",
  "statediagram",
  "erdiagram",
  "journey",
  "gantt",
  "pie",
  "mindmap",
  "timeline",
];

function normalizeUnicodeBullets(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inFence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence) {
      out.push(line);
      continue;
    }
    const match = line.match(UNICODE_BULLET_PATTERN);
    if (match) {
      out.push(`${match[1]}- ${match[2]}`);
      continue;
    }
    out.push(line);
  }
  return out.join("\n");
}

function normalizeTableBlocks(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inFence = false;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence) {
      out.push(line);
      continue;
    }

    if (trimmed.startsWith("|")) {
      out.push(line);
      continue;
    }

    if (!trimmed) {
      const prev = out.length > 0 ? out[out.length - 1].trim() : "";
      let next = "";
      let cursor = i + 1;
      while (cursor < lines.length) {
        const candidate = lines[cursor].trim();
        if (candidate) {
          next = candidate;
          break;
        }
        cursor += 1;
      }
      if (prev.startsWith("|") && next.startsWith("|")) {
        continue;
      }
    }

    out.push(line);
  }

  return out.join("\n");
}

function collectNonEmptyBlock(lines: string[], start: number): [string[], number] {
  const block: string[] = [];
  let cursor = start;
  while (cursor < lines.length) {
    const value = lines[cursor];
    const trimmed = value.trim();
    if (!trimmed) break;
    if (trimmed.startsWith("```")) break;
    if (cursor > start && trimmed.startsWith("#")) break;
    block.push(value);
    cursor += 1;
  }
  return [block, cursor];
}

function autoFenceSpecialBlocks(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inFence = false;
  let prevNonEmpty = "";
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    const lowered = trimmed.toLowerCase();

    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      if (trimmed) prevNonEmpty = trimmed;
      index += 1;
      continue;
    }

    if (inFence) {
      out.push(line);
      if (trimmed) prevNonEmpty = trimmed;
      index += 1;
      continue;
    }

    if (MERMAID_START_PREFIXES.some((prefix) => lowered.startsWith(prefix))) {
      const [block, next] = collectNonEmptyBlock(lines, index);
      out.push("```mermaid");
      out.push(...block);
      out.push("```");
      if (next < lines.length && lines[next].trim() === "") {
        out.push(lines[next]);
        index = next + 1;
      } else {
        index = next;
      }
      prevNonEmpty = "```mermaid";
      continue;
    }

    if (lowered.startsWith("type:") && /chart[- ]spec/i.test(prevNonEmpty)) {
      const [block, next] = collectNonEmptyBlock(lines, index);
      out.push("```chart-spec");
      out.push(...block);
      out.push("```");
      if (next < lines.length && lines[next].trim() === "") {
        out.push(lines[next]);
        index = next + 1;
      } else {
        index = next;
      }
      prevNonEmpty = "```chart-spec";
      continue;
    }

    out.push(line);
    if (trimmed) prevNonEmpty = trimmed;
    index += 1;
  }

  return out.join("\n");
}

function removeH2Sections(
  text: string,
  shouldRemoveHeading: (headingKey: string) => boolean
): string {
  const lines = text.split("\n");
  const output: string[] = [];
  let skipping = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("## ")) {
      const headingKey = normalizeHeadingKey(trimmed.slice(3));
      skipping = shouldRemoveHeading(headingKey);
      if (skipping) continue;
    }
    if (!skipping) output.push(line);
  }

  return output.join("\n");
}

function stripFencedBlocks(text: string, languages: Set<string>): string {
  const pattern = /```([a-zA-Z0-9_-]+)?\s*\n[\s\S]*?```/g;
  return text.replace(pattern, (match, languageRaw?: string) => {
    const language = String(languageRaw || "").trim().toLowerCase();
    if (languages.has(language)) return "";
    return match;
  });
}

function normalizeAnswer(
  answer: string,
  {
    stripReferenceSection,
    stripSafetyMatrixSection,
    stripMermaidBlocks,
    stripChartSpecBlocks,
  }: {
    stripReferenceSection: boolean;
    stripSafetyMatrixSection: boolean;
    stripMermaidBlocks: boolean;
    stripChartSpecBlocks: boolean;
  }
): string {
  const base = answer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const bulletFixed = normalizeUnicodeBullets(base);
  const tableFixed = normalizeTableBlocks(bulletFixed);
  const fenced = autoFenceSpecialBlocks(tableFixed);

  let cleaned = fenced;
  if (stripReferenceSection) {
    cleaned = removeH2Sections(cleaned, (headingKey) =>
      headingKey.includes("nguon tham chieu") ||
      headingKey.includes("tai lieu tham khao") ||
      headingKey.includes("references")
    );
  }
  if (stripSafetyMatrixSection) {
    cleaned = removeH2Sections(cleaned, (headingKey) =>
      headingKey.includes("ma tran quyet dinh an toan")
    );
  }
  if (stripMermaidBlocks) {
    cleaned = stripFencedBlocks(cleaned, new Set(["mermaid"]));
  }
  if (stripChartSpecBlocks) {
    cleaned = stripFencedBlocks(
      cleaned,
      new Set(["chart", "chart-spec", "vega-lite", "echarts-option", "json", "yaml", "yml"])
    );
  }

  return cleaned.replace(/\n{3,}/g, "\n\n").trim();
}

function materializeInlineCitations(
  markdownText: string,
  citations: MarkdownAnswerCitation[]
): string {
  if (!markdownText.trim() || !citations.length) return markdownText;

  const hrefByIndex = citations.reduce<Record<string, string>>((acc, citation, index) => {
    const href = sanitizeHref(citation.url);
    if (href) acc[String(index + 1)] = href;
    return acc;
  }, {});

  if (!Object.keys(hrefByIndex).length) return markdownText;

  const lines = markdownText.split("\n");
  const out: string[] = [];
  let inFence = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      continue;
    }
    if (inFence) {
      out.push(line);
      continue;
    }
    out.push(
      line.replace(/(?<!\[)\[(\d{1,3})\](?!\()/g, (match, index: string) => {
        const href = hrefByIndex[index];
        if (!href) return match;
        return `[[${index}]](${href})`;
      })
    );
  }

  return out.join("\n");
}

function sanitizeFileName(value: string): string {
  return value
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
}

function buildExportBaseName(answer: string): string {
  const firstHeading = answer
    .split("\n")
    .find((line) => line.trim().startsWith("## "))
    ?.replace(/^##\s+/, "")
    .trim();
  const date = new Date().toISOString().replace(/[:.]/g, "-");
  const title = sanitizeFileName(firstHeading || "clara-research-answer");
  return `${title}-${date}`;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function getFenceLanguageLabel(language?: string): string {
  if (!language) return "text";
  if (language === "ts" || language === "tsx") return "typescript";
  if (language === "js" || language === "jsx") return "javascript";
  return language;
}

function flattenMarkdownChildren(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => flattenMarkdownChildren(item)).join("");
  }
  if (value && typeof value === "object" && "props" in value) {
    const props = (value as { props?: { children?: unknown } }).props;
    return flattenMarkdownChildren(props?.children);
  }
  return "";
}

function CodeFence({ code, language, isChartSpec, uiLanguage }: CodeFenceProps) {
  const [notice, setNotice] = useState<"" | "success" | "error">("");
  const label = getFenceLanguageLabel(language);
  const chartSpec = useMemo(
    () => (isChartSpec ? parseChartSpec(code) : null),
    [code, isChartSpec]
  );

  const onCopy = async () => {
    if (!navigator?.clipboard) {
      setNotice("error");
      window.setTimeout(() => setNotice(""), 1500);
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      setNotice("success");
    } catch {
      setNotice("error");
    }
    window.setTimeout(() => setNotice(""), 1500);
  };

  return (
    <section className="overflow-hidden rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-lowest)] text-[var(--text-primary)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-[var(--text-secondary)]">
          <span className="font-semibold">
            {isChartSpec
              ? t(uiLanguage, "markdownAnswer.code.chartSpec")
              : t(uiLanguage, "markdownAnswer.code.block")}
          </span>
          <span className="rounded-full border border-[color:var(--shell-border)] px-2 py-0.5">{label}</span>
        </div>
        <button
          type="button"
          onClick={() => void onCopy()}
          className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-primary)]/30 hover:bg-[var(--surface-highest)]"
          aria-label={t(uiLanguage, "markdownAnswer.code.copyAria")}
        >
          {notice === "success"
            ? t(uiLanguage, "markdownAnswer.code.copied")
            : notice === "error"
              ? t(uiLanguage, "markdownAnswer.code.copyFailed")
              : t(uiLanguage, "markdownAnswer.code.copy")}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-6">
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      </pre>
      {chartSpec ? (
        <div className="border-t border-[color:var(--shell-border)] bg-[var(--surface-low)] p-3">
          <ChartSpecPreview spec={chartSpec} uiLanguage={uiLanguage} />
        </div>
      ) : null}
      {isChartSpec ? (
        <p className="border-t border-[color:var(--shell-border)] bg-[var(--surface-low)] px-3 py-2 text-[11px] text-[var(--text-secondary)]">
          {t(uiLanguage, "markdownAnswer.chartSpec.notice")}
        </p>
      ) : null}
    </section>
  );
}

function formatTrustTier(uiLanguage: UILanguage, trustTier?: number): string | null {
  return typeof trustTier === "number" && Number.isFinite(trustTier)
    ? t(uiLanguage, "markdownAnswer.citationRegistry.trustTier", { tier: trustTier })
    : null;
}

/**
 * Citation Registry appendix (Requirement 11.4, design §11). Lists every
 * citation referenced by the report with its study identifier, source type,
 * trust tier, and date. Each row carries a stable DOM id so the inline
 * sentence-level anchors (Requirement 11.3) resolve here. Renders nothing when
 * the registry is empty, preserving the legacy answer layout.
 */
function CitationRegistryAppendix({
  entries,
  uiLanguage,
}: {
  entries: ResearchTier2CitationRegistryEntry[];
  uiLanguage: UILanguage;
}) {
  if (!entries.length) return null;

  return (
    <section className="mt-6 border-t border-[color:var(--shell-border)] pt-3">
      <h2 className="text-[0.96rem] font-semibold tracking-tight text-[var(--text-primary)]">
        {t(uiLanguage, "markdownAnswer.citationRegistry.title")}
      </h2>
      <ol className="mt-2.5 space-y-2">
        {entries.map((entry, index) => {
          const anchorId = citationRegistryAnchorId(entry.citationId);
          const trustTier = formatTrustTier(uiLanguage, entry.trustTier);
          const meta = [entry.sourceType, trustTier, entry.publishedAt].filter(Boolean);
          const href = sanitizeHref(entry.url);
          return (
            <li
              key={`${entry.citationId}-${index}`}
              id={anchorId}
              className="scroll-mt-24 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-[13px] leading-6 text-[var(--text-primary)]"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-[var(--surface-brand-soft)] px-1.5 text-[10px] font-semibold text-[var(--text-brand)]">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  {entry.title ? (
                    <p className="font-medium text-[var(--text-primary)]">{entry.title}</p>
                  ) : null}
                  {entry.studyId ? (
                    <p className="font-mono text-[12px] text-[var(--text-secondary)]">
                      {entry.studyId}
                    </p>
                  ) : null}
                  {meta.length ? (
                    <p className="text-[11px] uppercase tracking-[0.08em] text-[var(--text-muted)]">
                      {meta.join(" · ")}
                    </p>
                  ) : null}
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer noopener nofollow"
                      className="break-all text-[12px] font-medium text-[var(--text-brand)] underline decoration-[color:var(--brand-primary)]/50 underline-offset-2 transition hover:text-[var(--text-primary)]"
                    >
                      {href}
                    </a>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default function MarkdownAnswer({
  answer,
  citations,
  showInlineCitations = false,
  enableMermaid = false,
  stripReferenceSection = true,
  stripSafetyMatrixSection = false,
  stripMermaidBlocks = true,
  stripChartSpecBlocks = true,
  uiLanguage = "vi",
  tracedClaims,
  citationRegistry,
}: MarkdownAnswerProps) {
  const normalized = useMemo(
    () =>
      normalizeAnswer(answer, {
        stripReferenceSection,
        stripSafetyMatrixSection,
        stripMermaidBlocks,
        stripChartSpecBlocks,
      }),
    [answer, stripReferenceSection, stripSafetyMatrixSection, stripMermaidBlocks, stripChartSpecBlocks]
  );
  const renderedMarkdown = useMemo(() => {
    const base = showInlineCitations ? materializeInlineCitations(normalized, citations) : normalized;
    // Render inline sentence-level citation anchors that resolve into the
    // Citation Registry appendix (Requirement 11.3, 11.4). Surfaced only when
    // both traced claims and a registry are present, so legacy answers are
    // unchanged.
    if (tracedClaims?.length && citationRegistry?.length) {
      return injectTracedClaimAnchors(base, tracedClaims, citationRegistry);
    }
    return base;
  }, [citations, normalized, showInlineCitations, tracedClaims, citationRegistry]);
  const [exportNotice, setExportNotice] = useState<string>("");
  const contentId = useMemo(() => `markdown-answer-${Math.random().toString(36).slice(2, 10)}`, []);
  const exportBaseName = useMemo(() => buildExportBaseName(normalized), [normalized]);
  const citationMap = useMemo(
    () =>
      showInlineCitations
        ? citations.reduce<Record<string, MarkdownAnswerCitation>>((acc, item, index) => {
            acc[String(index + 1)] = item;
            return acc;
          }, {})
        : {},
    [citations, showInlineCitations]
  );
  // Anchor-id -> registry entry, for resolving inline citation-anchor tooltips
  // and verifying that anchors point into the appendix (Requirement 11.4).
  const registryByAnchor = useMemo(
    () =>
      (citationRegistry ?? []).reduce<Record<string, ResearchTier2CitationRegistryEntry>>(
        (acc, entry) => {
          acc[citationRegistryAnchorId(entry.citationId)] = entry;
          return acc;
        },
        {}
      ),
    [citationRegistry]
  );
  if (!renderedMarkdown) {
    return null;
  }

  const onExportMarkdown = () => {
    const blob = new Blob([renderedMarkdown], { type: "text/markdown;charset=utf-8" });
    downloadBlob(blob, `${exportBaseName}.md`);
    setExportNotice(t(uiLanguage, "markdownAnswer.export.markdownSuccess"));
    window.setTimeout(() => setExportNotice(""), 1400);
  };

  const onExportDocx = async () => {
    try {
      const blob = await exportWorkspaceDocxFromMarkdown({
        markdown: renderedMarkdown,
        title: exportBaseName,
      });
      downloadBlob(blob, `${exportBaseName}.docx`);
      setExportNotice(t(uiLanguage, "markdownAnswer.export.docxSuccess"));
    } catch (cause) {
      const reason = safeUserFacingError(
        cause,
        t(uiLanguage, "markdownAnswer.export.unknownError"),
      );
      setExportNotice(
        t(uiLanguage, "markdownAnswer.export.docxFailed", { reason })
      );
    }
    window.setTimeout(() => setExportNotice(""), 1600);
  };

  const onCopyMarkdown = async () => {
    if (!navigator?.clipboard) {
      setExportNotice(t(uiLanguage, "markdownAnswer.export.clipboardUnavailable"));
      window.setTimeout(() => setExportNotice(""), 1400);
      return;
    }
    try {
      await navigator.clipboard.writeText(renderedMarkdown);
      setExportNotice(t(uiLanguage, "markdownAnswer.export.copySuccess"));
    } catch {
      setExportNotice(t(uiLanguage, "markdownAnswer.export.copyFailed"));
    }
    window.setTimeout(() => setExportNotice(""), 1400);
  };

  const onExportPng = async () => {
    const node = document.getElementById(contentId);
    if (!node) {
      setExportNotice(t(uiLanguage, "markdownAnswer.export.pngNoContent"));
      window.setTimeout(() => setExportNotice(""), 1400);
      return;
    }
    try {
      const dataUrl = await toPng(node, {
        cacheBust: true,
        pixelRatio: Math.max(2, Math.min(window.devicePixelRatio || 1, 3)),
        backgroundColor: "#101419",
      });
      const response = await fetch(dataUrl);
      const blob = await response.blob();
      downloadBlob(blob, `${exportBaseName}.png`);
      setExportNotice(t(uiLanguage, "markdownAnswer.export.pngSuccess"));
    } catch {
      setExportNotice(t(uiLanguage, "markdownAnswer.export.pngFailed"));
    }
    window.setTimeout(() => setExportNotice(""), 1600);
  };

  let sectionIndex = 0;
  let pendingLeadTone: SectionTone | null = null;
  let pendingLeadSummary = false;

  return (
    <div className="medical-markdown prose max-w-none text-[var(--text-primary)] prose-p:my-2 prose-p:leading-[1.75] prose-li:leading-[1.68] prose-headings:tracking-tight">
      <div className="mb-1 flex items-center justify-end gap-1">
        <details className="group relative">
          <summary
            aria-label={t(uiLanguage, "markdownAnswer.actions.more")}
            className="list-none rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1 text-[var(--text-secondary)] transition hover:border-[color:var(--brand-primary)]/30 hover:text-[var(--text-brand)]"
          >
            <Icon name="more" size="14px" />
          </summary>
          <div className="absolute right-0 z-10 mt-2 w-40 space-y-1 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-2 shadow-xl">
            <button
              type="button"
              onClick={onCopyMarkdown}
              className="block w-full rounded-xl px-3 py-2 text-left text-[11px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              {t(uiLanguage, "markdownAnswer.action.copyMarkdown")}
            </button>
            <button
              type="button"
              onClick={onExportMarkdown}
              className="block w-full rounded-xl px-3 py-2 text-left text-[11px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              {t(uiLanguage, "markdownAnswer.action.exportMarkdown")}
            </button>
            <button
              type="button"
              onClick={() => void onExportDocx()}
              className="block w-full rounded-xl px-3 py-2 text-left text-[11px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              {t(uiLanguage, "markdownAnswer.action.exportDocx")}
            </button>
            <button
              type="button"
              onClick={() => void onExportPng()}
              className="block w-full rounded-xl px-3 py-2 text-left text-[11px] font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
            >
              {t(uiLanguage, "markdownAnswer.action.exportPng")}
            </button>
          </div>
        </details>
      </div>
      {exportNotice ? <p className="mb-2 text-[10px] text-[var(--text-brand)]">{exportNotice}</p> : null}
      <div id={contentId}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          pre: ({ children }) => <>{children}</>,
          h2: ({ children }) => {
            const headingText = flattenMarkdownChildren(children).trim();
            const tone = resolveSectionTone(headingText);
            sectionIndex += 1;
            pendingLeadTone = tone;
            pendingLeadSummary = sectionIndex === 1 && tone === "brand";
            return <h2 className={sectionHeadingClasses(tone)}>{children}</h2>;
          },
          h3: ({ children }) => (
            <h3 className="mt-5 text-[0.97rem] font-semibold tracking-tight text-[var(--text-primary)]">
              {children}
            </h3>
          ),
          p: ({ children }) => {
            const tone = pendingLeadTone;
            const isLeadSummary = pendingLeadSummary;
            pendingLeadTone = null;
            pendingLeadSummary = false;
            if (isLeadSummary) {
              return (
                <p className="mt-2.5 rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-[15px] font-semibold leading-7 text-[var(--text-primary)]">
                  {children}
                </p>
              );
            }
            return (
              <p
                className={[
                  "mt-2.5 text-[14.5px] leading-7 text-[var(--text-primary)]",
                  tone === "safety" ? "text-[var(--status-ok-text)]" : "",
                  tone === "warning" ? "text-[var(--status-warn-text)]" : "",
                ].join(" ").trim()}
              >
                {children}
              </p>
            );
          },
          a: ({ href, children, ...props }) => {
            const text =
              Array.isArray(children) && typeof children[0] === "string" ? children[0] : "";
            const registryAnchorId =
              typeof href === "string" && href.startsWith("#citation-")
                ? href.slice(1)
                : undefined;
            const registryEntry = registryAnchorId ? registryByAnchor[registryAnchorId] : undefined;
            const citationMatch = text.match(/^\[(\d+)\]$/);
            const citation = citationMatch && !registryEntry ? citationMap[citationMatch[1]] : undefined;
            // Inline registry anchors resolve to the in-page Citation Registry
            // appendix (Requirement 11.3, 11.4); never treat them as external.
            const resolvedHref = registryAnchorId
              ? `#${registryAnchorId}`
              : sanitizeHref(href) ?? sanitizeHref(citation?.url) ?? "#";
            const external = resolvedHref.startsWith("http://") || resolvedHref.startsWith("https://");
            const isCitationLink = Boolean(citationMatch) || Boolean(registryEntry);
            const registryTitle = registryEntry
              ? [registryEntry.studyId, registryEntry.title].filter(Boolean).join(" · ") || undefined
              : undefined;
            return (
              <a
                {...props}
                href={resolvedHref}
                target={external ? "_blank" : undefined}
                rel={external ? "noreferrer noopener nofollow" : undefined}
                title={registryTitle ?? citation?.title}
                className={
                  isCitationLink
                    ? "ml-0.5 inline-flex min-w-[1rem] -translate-y-[0.28rem] items-center justify-center rounded-full bg-[var(--surface-brand-soft)] px-1.5 text-[9px] font-semibold text-[var(--text-brand)] no-underline transition hover:bg-[var(--surface-highest)] hover:text-[var(--text-primary)]"
                    : "font-medium text-[var(--text-brand)] underline decoration-[color:var(--brand-primary)]/50 underline-offset-2 transition hover:text-[var(--text-primary)]"
                }
              >
                {children}
              </a>
            );
          },
          code: ({ className, children, node, ...props }) => {
            const rawCode = flattenMarkdownChildren(children);
            const code = rawCode.replace(/\n$/, "");
            const language = className?.replace("language-", "").trim().toLowerCase();
            const startLine =
              typeof node?.position?.start?.line === "number" ? node.position.start.line : undefined;
            const endLine =
              typeof node?.position?.end?.line === "number" ? node.position.end.line : undefined;
            const spansMultipleLines =
              typeof startLine === "number" && typeof endLine === "number" && endLine > startLine;
            const isInline = !className && !spansMultipleLines && !rawCode.includes("\n");

            if (!isInline && language === "mermaid") {
              if (!enableMermaid) {
                return (
                  <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                    {t(uiLanguage, "markdownAnswer.mermaid.hidden")}
                  </div>
                );
              }
              return <MermaidBlock code={code} uiLanguage={uiLanguage} />;
            }

            if (isInline) {
              return (
                <code
                  {...props}
                  className="rounded-[var(--radius-sm)] bg-[var(--surface-lowest)] px-1.5 py-0.5 font-mono text-[0.82em] text-[var(--text-primary)]"
                >
                  {rawCode}
                </code>
              );
            }

            const isChartSpec = language ? CHART_SPEC_LANGUAGES.has(language) : false;
            return <CodeFence code={code} language={language} isChartSpec={isChartSpec} uiLanguage={uiLanguage} />;
          },
          table: ({ children }) => (
            <div className="mt-3 overflow-x-auto rounded-[14px] border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              <table className="w-full border-collapse text-sm leading-6">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-primary)]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[color:var(--shell-border)] px-3 py-2 align-top text-sm text-[var(--text-primary)]">
              {children}
            </td>
          ),
          ul: ({ children }) => (
            <ul className="mt-2.5 list-disc space-y-1.5 pl-5 text-[14.4px] text-[var(--text-primary)]">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mt-2.5 list-decimal space-y-1.5 pl-5 text-[14.4px] text-[var(--text-primary)]">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="ml-2 text-[14.4px] leading-7 text-[var(--text-primary)] marker:text-[var(--text-muted)]">
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mt-3 rounded-r-[var(--radius-lg)] border-l-4 border-[color:var(--brand-primary)] bg-[var(--surface-brand-soft)] px-3 py-2 text-[14px] leading-7 text-[var(--text-primary)]">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-6 border-[color:var(--shell-border)]" />,
        }}
      >
        {renderedMarkdown}
      </ReactMarkdown>
      <CitationRegistryAppendix entries={citationRegistry ?? []} uiLanguage={uiLanguage} />
      </div>
    </div>
  );
}
