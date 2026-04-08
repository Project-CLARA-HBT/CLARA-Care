"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import {
  CouncilCaseRecord,
  createCouncilCase,
  listCouncilCases,
  setActiveCouncilCaseId,
} from "@/lib/council";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function CouncilNewPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CouncilCaseRecord[]>([]);
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await listCouncilCases(10, 0);
        setCases(response.items);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải danh sách case.");
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, []);

  const onCreateCase = async () => {
    setIsCreating(true);
    setError("");
    try {
      const created = await createCouncilCase({ title: `Case ${new Date().toLocaleString("vi-VN")}` });
      setActiveCouncilCaseId(created.id);
      router.push(`/council/new/intake?caseId=${created.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo case mới.");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <PageShell
      title="New Council Case"
      description="Flow chuẩn: tạo case mới, intake dữ liệu thật, rồi mới chạy phân tích/synthesis."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Wizard Flow</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">Tạo case trước khi phân tích</h2>
          <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
            Council sẽ không hiển thị phân tích giả. Bạn cần tạo case mới, hoàn thành intake, chọn specialist rồi chạy hội chẩn.
          </p>

          <button
            type="button"
            onClick={() => void onCreateCase()}
            disabled={isCreating}
            className="mt-5 inline-flex min-h-[46px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isCreating ? "Đang tạo case..." : "Tạo case mới"}
          </button>
        </section>

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Recent Cases</h3>
            <Link href="/council" className="text-xs font-semibold text-cyan-300">
              Mở Council Landing
            </Link>
          </div>

          {isLoading ? <p className="text-sm text-[var(--text-secondary)]">Đang tải dữ liệu...</p> : null}
          {!isLoading && cases.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">Chưa có case nào.</p>
          ) : null}

          <div className="space-y-2">
            {cases.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActiveCouncilCaseId(item.id);
                  router.push(`/council/new/intake?caseId=${item.id}`);
                }}
                className="flex w-full items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-left transition hover:border-cyan-400/40"
              >
                <span>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{item.title || `Case #${item.id}`}</p>
                  <p className="text-xs text-[var(--text-secondary)]">
                    #{item.id} · {item.status} · {formatTime(item.updated_at)}
                  </p>
                </span>
                <span className="material-symbols-outlined text-[var(--text-secondary)]">chevron_right</span>
              </button>
            ))}
          </div>
        </section>

        {error ? <p className="text-sm text-red-400">{error}</p> : null}
      </div>
    </PageShell>
  );
}
