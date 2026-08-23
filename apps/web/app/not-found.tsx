import Link from "next/link";
import Icon from "@/components/ui/icon";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
        <Icon name="warning" size={32} />
      </div>
      <h1 className="mt-4 text-3xl font-bold text-[var(--text-primary)]">
        404 - Không tìm thấy trang
      </h1>
      <p className="mt-2 max-w-md text-sm text-[var(--text-secondary)]">
        Trang bạn đang tìm kiếm không tồn tại hoặc đã được di chuyển.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link
          href="/dashboard"
          className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)]"
        >
          <Icon name="progress" size={16} />
          <span>Về trang điều khiển</span>
        </Link>
        <Link
          href="/chat"
          className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-panel)]"
        >
          <Icon name="clinical-notes" size={16} />
          <span>Hỏi CLARA</span>
        </Link>
      </div>
    </div>
  );
}
