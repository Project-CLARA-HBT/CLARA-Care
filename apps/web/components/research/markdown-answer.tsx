"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

const ALLOWED_EXTERNAL_PROTOCOLS = new Set(["http:", "https:"]);
const CHART_SPEC_LANGUAGES = new Set(["chart", "chart-spec", "vega-lite", "echarts-option", "json", "yaml", "yml"]);

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
    });

    parsed.querySelectorAll("foreignObject *").forEach((node) => {
      const currentStyle = node.getAttribute("style") ?? "";
      if (!/color\s*:/i.test(currentStyle)) {
        node.setAttribute("style", `${currentStyle}${currentStyle ? ";" : ""}color:#0f172a;`);
      }
    });

    return parsed.documentElement.outerHTML || "";
  } catch {
    return "";
  }
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

function normalizeAnswer(answer: string): string {
  return answer.replace(/\r\n/g, "\n").trim();
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
      {isChartSpec ? (
        <p className="border-t border-slate-700/80 bg-slate-950/40 px-3 py-2 text-[11px] text-slate-300">
          Block này là spec dữ liệu biểu đồ. Nếu UI có chart-engine, có thể dựng chart trực tiếp từ nội dung này.
        </p>
      ) : null}
    </section>
  );
}

export default function MarkdownAnswer({ answer, citations }: MarkdownAnswerProps) {
  const normalized = useMemo(() => normalizeAnswer(answer), [answer]);
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

  return (
    <div className="prose prose-slate max-w-none dark:prose-invert prose-p:leading-7 prose-li:leading-7 prose-headings:tracking-tight">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          pre: ({ children }) => <>{children}</>,
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
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 bg-slate-100 px-2 py-1.5 text-left font-semibold dark:border-slate-600 dark:bg-slate-800">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-300 px-2 py-1.5 align-top dark:border-slate-700">{children}</td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-sky-400 bg-sky-50/60 px-3 py-2 text-slate-700 dark:bg-sky-950/20 dark:text-slate-200">
              {children}
            </blockquote>
          ),
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
