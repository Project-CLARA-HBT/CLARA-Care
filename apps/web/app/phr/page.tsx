"use client";

import PageShell from "@/components/ui/page-shell";

export default function PhrPage() {
  return (
    <PageShell
      variant="plain"
      title="PHR"
      description="Không gian quản lý hồ sơ sức khỏe cá nhân."
    >
      <section className="chrome-panel rounded-2xl p-5 sm:p-6">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Hồ sơ sức khỏe cá nhân</h2>
        <p className="mt-2 max-w-3xl text-sm text-[var(--text-secondary)]">
          Trang PHR đã được bật ở sidebar. Phần workflow chi tiết sẽ được triển khai tiếp theo
          theo luồng LLM - PHR.
        </p>
      </section>
    </PageShell>
  );
}
