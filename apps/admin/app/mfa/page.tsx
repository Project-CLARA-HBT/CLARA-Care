"use client";

import React, { useState } from "react";

export default function AdminMfaPage() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/control/v1/sessions/step-up", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: "active-browser-session",
          mfa_totp_code: code,
          target_level: "PRIVILEGED",
        }),
      });
      if (!res.ok) {
        throw new Error("Invalid MFA authentication code");
      }
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-slate-800 bg-slate-950 p-8 shadow-xl">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">MFA Step-Up Verification</h1>
          <p className="mt-1 text-sm text-slate-400">Enter the 6-digit TOTP code from your authenticator device</p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300">Security Code</label>
            <input
              type="text"
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-center font-mono text-xl tracking-widest text-slate-100 outline-none focus:border-sky-500"
              placeholder="000000"
            />
          </div>
          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="w-full rounded-lg bg-sky-600 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:opacity-50"
          >
            {loading ? "Verifying..." : "Verify & Authorize Session"}
          </button>
        </form>
      </div>
    </div>
  );
}
