import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CLARA Control Plane Admin",
  description: "Separate administrative control plane for healthcare tenant governance",
};

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-slate-900 text-slate-100 antialiased">
        <header className="border-b border-slate-800 bg-slate-950 px-6 py-4">
          <div className="flex items-center justify-between">
            <span className="text-lg font-bold text-sky-400">CLARA Control Plane</span>
            <span className="rounded bg-sky-950 px-2 py-0.5 text-xs text-sky-300">Port 8200 Isolated</span>
          </div>
        </header>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
