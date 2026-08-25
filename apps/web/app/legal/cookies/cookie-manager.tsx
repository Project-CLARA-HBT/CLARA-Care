"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function CookieManagerControl() {
  const [theme, setTheme] = useState<string>("system");
  const [lang, setLang] = useState<string>("vi");
  const [motion, setMotion] = useState<string>("normal");
  const [clearedNotice, setClearedNotice] = useState<string | null>(null);

  useEffect(() => {
    try {
      if (typeof window !== "undefined") {
        const storedTheme = localStorage.getItem("clara-theme") || "dark";
        const storedLang = localStorage.getItem("clara-ui-language") || "vi";
        const storedMotion = localStorage.getItem("clara-reduced-motion") || "normal";
        setTheme(storedTheme);
        setLang(storedLang);
        setMotion(storedMotion);
      }
    } catch {
      // Safe fallback in restricted iframe/browser storage
    }
  }, []);

  const handleClearPreferences = () => {
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem("clara-theme");
        localStorage.removeItem("clara-ui-language");
        localStorage.removeItem("clara-reduced-motion");
        setTheme("default");
        setLang("vi");
        setMotion("normal");
        setClearedNotice("Đã đặt lại các tùy chọn giao diện về mặc định hệ thống.");
        setTimeout(() => setClearedNotice(null), 4000);
      }
    } catch {
      setClearedNotice("Không thể thao tác bộ nhớ trình duyệt.");
    }
  };

  return (
    <div
      className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-5 space-y-4"
      data-testid="cookie-manager-controls"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="settings" size="1.1rem" />
          <h3 className="text-sm font-bold text-[var(--text-primary)]">
            Bảng điều khiển tùy chọn lưu trữ cục bộ
          </h3>
        </div>
        <Badge tone="ok">Không có Cookie theo dõi / Quảng cáo</Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 text-xs">
        <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 space-y-1">
          <span className="text-[var(--text-muted)] font-medium">Giao diện (Theme):</span>
          <p className="font-bold text-[var(--text-primary)] capitalize">{theme}</p>
        </div>
        <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 space-y-1">
          <span className="text-[var(--text-muted)] font-medium">Ngôn ngữ hiển thị:</span>
          <p className="font-bold text-[var(--text-primary)]">{lang === "vi" ? "Tiếng Việt (vi)" : "English (en)"}</p>
        </div>
        <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 space-y-1">
          <span className="text-[var(--text-muted)] font-medium">Hiệu ứng chuyển động:</span>
          <p className="font-bold text-[var(--text-primary)]">{motion === "reduce" ? "Giảm chuyển động" : "Mặc định (Standard)"}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <p className="text-[11px] text-[var(--text-secondary)]">
          Bạn có thể xóa các tùy chọn hiển thị đã lưu mà không ảnh hưởng đến phiên đăng nhập hiện tại.
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleClearPreferences}
          data-testid="clear-preferences-btn"
        >
          <Icon name="refresh" size="0.85rem" />
          <span>Đặt lại tùy chọn cục bộ</span>
        </Button>
      </div>

      {clearedNotice ? (
        <div
          role="status"
          className="rounded-lg border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-2.5 text-xs text-[var(--status-ok-text)] font-semibold"
        >
          {clearedNotice}
        </div>
      ) : null}
    </div>
  );
}
