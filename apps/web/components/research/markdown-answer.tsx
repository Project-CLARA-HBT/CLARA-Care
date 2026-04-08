"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toPng } from "html-to-image";
import { exportWorkspaceDocxFromMarkdown } from "@/lib/workspace";

export type MarkdownAnswerCitation = {
  title: string;
  url?: string;
};

export type MarkdownAnswerProps = {
  answer: string;
  citations: MarkdownAnswerCitation[];
};

type MermaidBlockProps = {
  code: string;
};

type CodeFenceProps = {
  code: string;
  language?: string;
  isChartSpec: boolean;
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
  if (key.includes("bang tong hop") || key.includes("nguon tham chieu") || key.includes("ma tran")) {
    return "evidence";
  }
  if (key.includes("khuyen nghi") || key.includes("ke hoach theo doi")) {
    return "safety";
  }
  if (key.includes("canh bao") || key.includes("phap ly") || key.includes("gioi han")) {
    return "warning";
  }
  if (key.includes("ket luan") || key.includes("tom tat") || key.includes("boi canh")) {
    return "brand";
  }
  return "neutral";
}

function sectionHeadingClasses(tone: SectionTone): string {
  switch (tone) {
    case "brand":
      return "mt-8 rounded-2xl border border-cyan-300/65 bg-cyan-500/10 px-4 py-2 text-lg font-semibold tracking-tight text-cyan-950 dark:border-cyan-700/70 dark:bg-cyan-950/30 dark:text-cyan-100";
    case "evidence":
      return "mt-8 rounded-2xl border border-indigo-300/65 bg-indigo-500/10 px-4 py-2 text-lg font-semibold tracking-tight text-indigo-950 dark:border-indigo-700/70 dark:bg-indigo-950/30 dark:text-indigo-100";
    case "safety":
      return "mt-8 rounded-2xl border border-emerald-300/65 bg-emerald-500/10 px-4 py-2 text-lg font-semibold tracking-tight text-emerald-950 dark:border-emerald-700/70 dark:bg-emerald-950/30 dark:text-emerald-100";
    case "warning":
      return "mt-8 rounded-2xl border border-amber-300/65 bg-amber-500/10 px-4 py-2 text-lg font-semibold tracking-tight text-amber-950 dark:border-amber-700/70 dark:bg-amber-950/30 dark:text-amber-100";
    default:
      return "mt-8 rounded-2xl border border-slate-300/70 bg-slate-100/75 px-4 py-2 text-lg font-semibold tracking-tight text-slate-900 dark:border-slate-700/70 dark:bg-slate-800/65 dark:text-slate-100";
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

    // Keep foreignObject because Mermaid may put labels there; removing it can erase all text.
    parsed.querySelectorAll("script, iframe, object, embed").forEach((node) => {
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
        node.setAttribute("fill", "#0f172a");
      }
      if (!node.getAttribute("font-family")) {
        node.setAttribute("font-family", "Inter, Segoe UI, Arial, sans-serif");
      }
    });

    parsed.querySelectorAll("foreignObject *").forEach((node) => {
      const currentStyle = node.getAttribute("style") ?? "";
      const nextStyle = `${currentStyle}${currentStyle ? ";" : ""}color:#0f172a !important;`;
      node.setAttribute("style", nextStyle);
    });

    const svgEl = parsed.documentElement;
    const styleEl = parsed.createElementNS("http://www.w3.org/2000/svg", "style");
    styleEl.textContent = `
      text, tspan, .label, .nodeLabel { fill: #0f172a !important; color: #0f172a !important; }
      foreignObject *, .label foreignObject * { color: #0f172a !important; fill: #0f172a !important; }
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

function formatChartValue(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (Math.abs(value) >= 1000) return value.toLocaleString("vi-VN");
  if (Math.abs(value) >= 1) return value.toFixed(2).replace(/\.00$/, "");
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function ChartSpecPreview({ spec }: { spec: ChartSpecData }) {
  const max = Math.max(...spec.values, 0.000001);
  const total = spec.values.reduce((sum, item) => sum + Math.max(item, 0), 0);

  return (
    <section className="rounded-xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-700 dark:bg-slate-900/60">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-300">
        Chart Preview · {spec.type.toUpperCase()}
      </p>
      <h4 className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{spec.title}</h4>
      {spec.type === "pie" ? (
        <div className="mt-3 space-y-2">
          {spec.labels.map((label, index) => {
            const value = spec.values[index] ?? 0;
            const pct = total > 0 ? (Math.max(value, 0) / total) * 100 : 0;
            return (
              <div key={`${label}-${index}`} className="space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-300">
                  <span>{label}</span>
                  <span>{formatChartValue(value)} ({pct.toFixed(1)}%)</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-full rounded-full bg-cyan-500"
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
                <span className="truncate text-slate-600 dark:text-slate-300" title={label}>{label}</span>
                <div className="h-2 overflow-hidden rounded bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-full rounded bg-indigo-500"
                    style={{ width: `${Math.min(Math.max(ratio * 100, 0), 100)}%` }}
                  />
                </div>
                <span className="font-medium text-slate-700 dark:text-slate-200">{formatChartValue(value)}</span>
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

function MermaidBlock({ code }: MermaidBlockProps) {
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
          setError(cause instanceof Error ? cause.message : "Không thể render Mermaid.");
        }
      }
    }

    void renderMermaid();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
        Lỗi Mermaid: {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300">
        Đang dựng sơ đồ Mermaid...
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300">
        <span>Mermaid Diagram</span>
        <span className="rounded-full border border-cyan-300/60 bg-cyan-500/15 px-2 py-0.5 text-[10px] text-cyan-700 dark:text-cyan-200">
          an toàn
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

function normalizeAnswer(answer: string): string {
  const base = answer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const bulletFixed = normalizeUnicodeBullets(base);
  const tableFixed = normalizeTableBlocks(bulletFixed);
  const fenced = autoFenceSpecialBlocks(tableFixed);
  return fenced.trim();
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

function CodeFence({ code, language, isChartSpec }: CodeFenceProps) {
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
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900 text-slate-100 dark:border-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/80 bg-slate-950/50 px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-300">
          <span className="font-semibold">{isChartSpec ? "chart spec" : "code block"}</span>
          <span className="rounded-full border border-slate-600 px-2 py-0.5">{label}</span>
        </div>
        <button
          type="button"
          onClick={() => void onCopy()}
          className="rounded-md border border-slate-600 px-2.5 py-1 text-[11px] font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
          aria-label="Sao chép code block"
        >
          {notice === "success" ? "Đã copy" : notice === "error" ? "Copy lỗi" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-6">
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      </pre>
      {chartSpec ? (
        <div className="border-t border-slate-700/80 bg-slate-950/40 p-3">
          <ChartSpecPreview spec={chartSpec} />
        </div>
      ) : null}
      {isChartSpec ? (
        <p className="border-t border-slate-700/80 bg-slate-950/40 px-3 py-2 text-[11px] text-slate-300">
          Block này là spec dữ liệu biểu đồ. CLARA đã render preview trực tiếp nếu parse được.
        </p>
      ) : null}
    </section>
  );
}

export default function MarkdownAnswer({ answer, citations }: MarkdownAnswerProps) {
  const normalized = useMemo(() => normalizeAnswer(answer), [answer]);
  const [exportNotice, setExportNotice] = useState<string>("");
  const contentId = useMemo(() => `markdown-answer-${Math.random().toString(36).slice(2, 10)}`, []);
  const exportBaseName = useMemo(() => buildExportBaseName(normalized), [normalized]);
  const citationMap = useMemo(
    () =>
      citations.reduce<Record<string, MarkdownAnswerCitation>>((acc, item, index) => {
        acc[String(index + 1)] = item;
        return acc;
      }, {}),
    [citations]
  );

  if (!normalized) {
    return null;
  }

  const onExportMarkdown = () => {
    const blob = new Blob([normalized], { type: "text/markdown;charset=utf-8" });
    downloadBlob(blob, `${exportBaseName}.md`);
    setExportNotice("Đã xuất file Markdown.");
    window.setTimeout(() => setExportNotice(""), 1400);
  };

  const onExportDocx = async () => {
    try {
      const blob = await exportWorkspaceDocxFromMarkdown({
        markdown: normalized,
        title: exportBaseName,
      });
      downloadBlob(blob, `${exportBaseName}.docx`);
      setExportNotice("Đã xuất file DOCX.");
    } catch (cause) {
      const reason =
        cause instanceof Error && cause.message
          ? cause.message
          : "Lỗi không xác định.";
      setExportNotice(`Xuất DOCX thất bại: ${reason}`);
    }
    window.setTimeout(() => setExportNotice(""), 1600);
  };

  const onCopyMarkdown = async () => {
    if (!navigator?.clipboard) {
      setExportNotice("Clipboard không khả dụng.");
      window.setTimeout(() => setExportNotice(""), 1400);
      return;
    }
    try {
      await navigator.clipboard.writeText(normalized);
      setExportNotice("Đã copy markdown.");
    } catch {
      setExportNotice("Không thể copy markdown.");
    }
    window.setTimeout(() => setExportNotice(""), 1400);
  };

  const onExportPng = async () => {
    const node = document.getElementById(contentId);
    if (!node) {
      setExportNotice("Không tìm thấy nội dung để xuất PNG.");
      window.setTimeout(() => setExportNotice(""), 1400);
      return;
    }
    try {
      const dataUrl = await toPng(node, {
        cacheBust: true,
        pixelRatio: Math.max(2, Math.min(window.devicePixelRatio || 1, 3)),
        backgroundColor: "#ffffff",
      });
      const response = await fetch(dataUrl);
      const blob = await response.blob();
      downloadBlob(blob, `${exportBaseName}.png`);
      setExportNotice("Đã xuất PNG.");
    } catch {
      setExportNotice("Xuất PNG thất bại.");
    }
    window.setTimeout(() => setExportNotice(""), 1600);
  };

  return (
    <div className="medical-markdown prose prose-slate max-w-none dark:prose-invert prose-p:leading-7 prose-li:leading-7 prose-headings:tracking-tight">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cyan-300/70 bg-cyan-500/10 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-cyan-900 dark:border-cyan-700/70 dark:bg-cyan-950/35 dark:text-cyan-100">
        <div className="flex flex-wrap items-center gap-2">
        <span>Báo cáo y khoa có cấu trúc</span>
        <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5 text-[10px] text-cyan-700 dark:border-cyan-600/70 dark:bg-cyan-900/45 dark:text-cyan-200">
          markdown + citation
        </span>
        <span className="rounded-full border border-cyan-300/70 bg-white/70 px-2 py-0.5 text-[10px] text-cyan-700 dark:border-cyan-600/70 dark:bg-cyan-900/45 dark:text-cyan-200">
          mermaid/table ready
        </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={onCopyMarkdown}
            className="rounded-md border border-cyan-300/70 bg-white/70 px-2 py-1 text-[10px] font-semibold text-cyan-800 transition hover:bg-white dark:border-cyan-600/70 dark:bg-cyan-900/50 dark:text-cyan-100"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={onExportMarkdown}
            className="rounded-md border border-cyan-300/70 bg-white/70 px-2 py-1 text-[10px] font-semibold text-cyan-800 transition hover:bg-white dark:border-cyan-600/70 dark:bg-cyan-900/50 dark:text-cyan-100"
          >
            Xuất .md
          </button>
          <button
            type="button"
            onClick={() => void onExportDocx()}
            className="rounded-md border border-cyan-300/70 bg-white/70 px-2 py-1 text-[10px] font-semibold text-cyan-800 transition hover:bg-white dark:border-cyan-600/70 dark:bg-cyan-900/50 dark:text-cyan-100"
          >
            Xuất .docx
          </button>
          <button
            type="button"
            onClick={() => void onExportPng()}
            className="rounded-md border border-cyan-300/70 bg-white/70 px-2 py-1 text-[10px] font-semibold text-cyan-800 transition hover:bg-white dark:border-cyan-600/70 dark:bg-cyan-900/50 dark:text-cyan-100"
          >
            Xuất .png
          </button>
        </div>
      </div>
      {exportNotice ? (
        <p className="mb-2 text-[11px] text-cyan-700 dark:text-cyan-300">{exportNotice}</p>
      ) : null}
      <div id={contentId}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          pre: ({ children }) => <>{children}</>,
          h2: ({ children }) => {
            const headingText = flattenMarkdownChildren(children).trim();
            const tone = resolveSectionTone(headingText);
            return <h2 className={sectionHeadingClasses(tone)}>{children}</h2>;
          },
          h3: ({ children }) => (
            <h3 className="mt-5 border-l-4 border-slate-300 pl-3 text-base font-semibold tracking-tight text-slate-900 dark:border-slate-600 dark:text-slate-100">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="mt-3 text-[15px] leading-7 text-slate-700 dark:text-slate-200">{children}</p>
          ),
          a: ({ href, children, ...props }) => {
            const text =
              Array.isArray(children) && typeof children[0] === "string" ? children[0] : "";
            const citationMatch = text.match(/^\[(\d+)\]$/);
            const citation = citationMatch ? citationMap[citationMatch[1]] : undefined;
            const resolvedHref = sanitizeHref(href) ?? sanitizeHref(citation?.url) ?? "#";
            const external = resolvedHref.startsWith("http://") || resolvedHref.startsWith("https://");
            return (
              <a
                {...props}
                href={resolvedHref}
                target={external ? "_blank" : undefined}
                rel={external ? "noreferrer noopener nofollow" : undefined}
                title={citation?.title}
                className="font-medium text-cyan-700 underline decoration-cyan-500/50 underline-offset-2 transition hover:text-cyan-900 dark:text-cyan-300 dark:hover:text-cyan-100"
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
              return <MermaidBlock code={code} />;
            }

            if (isInline) {
              return (
                <code
                  {...props}
                  className="rounded bg-slate-900/90 px-1.5 py-0.5 font-mono text-[0.82em] text-slate-100"
                >
                  {rawCode}
                </code>
              );
            }

            const isChartSpec = language ? CHART_SPEC_LANGUAGES.has(language) : false;
            return <CodeFence code={code} language={language} isChartSpec={isChartSpec} />;
          },
          table: ({ children }) => (
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900/40">
              <table className="w-full border-collapse text-sm leading-6">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 bg-slate-100 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-300 px-3 py-2 align-top text-sm text-slate-700 dark:border-slate-700 dark:text-slate-200">
              {children}
            </td>
          ),
          ul: ({ children }) => (
            <ul className="mt-3 space-y-2 rounded-xl border border-slate-200/80 bg-slate-50/70 px-4 py-3 dark:border-slate-700/70 dark:bg-slate-900/35">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mt-3 list-decimal space-y-2 rounded-xl border border-slate-200/80 bg-slate-50/70 px-5 py-3 dark:border-slate-700/70 dark:bg-slate-900/35">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="ml-2 text-[15px] leading-7 text-slate-700 marker:text-slate-400 dark:text-slate-200">
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mt-3 rounded-r-xl border-l-4 border-sky-400 bg-sky-50/70 px-3 py-2 text-[14px] leading-7 text-slate-700 dark:bg-sky-950/20 dark:text-slate-200">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-6 border-slate-200 dark:border-slate-700" />,
        }}
      >
        {normalized}
      </ReactMarkdown>
      </div>
    </div>
  );
}
