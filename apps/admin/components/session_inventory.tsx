import React, { useState } from "react";

export interface AdminDeviceSession {
  sessionId: string;
  deviceId: string;
  deviceLabel: string;
  ipAddress: string;
  stepUpLevel: "STANDARD" | "PRIVILEGED";
  isCurrent: boolean;
  lastActive: string;
}

export interface SessionInventoryProps {
  sessions: AdminDeviceSession[];
  onRevokeSession: (sessionId: string) => Promise<void>;
  onRevokeOtherDevices: () => Promise<void>;
}

export function SessionInventoryPanel({
  sessions,
  onRevokeSession,
  onRevokeOtherDevices,
}: SessionInventoryProps) {
  const [loading, setLoading] = useState(false);

  const handleRevokeOther = async () => {
    setLoading(true);
    try {
      await onRevokeOtherDevices();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-950 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100">Active Administrative Sessions</h2>
          <p className="text-sm text-slate-400">Manage device authorizations and terminate unauthorized sessions</p>
        </div>
        <button
          onClick={handleRevokeOther}
          disabled={loading}
          className="rounded-lg bg-red-600/20 border border-red-500/50 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:bg-red-600/30 disabled:opacity-50"
        >
          Revoke All Other Devices
        </button>
      </div>

      <div className="divide-y divide-slate-800">
        {sessions.map((sess) => (
          <div key={sess.sessionId} className="flex items-center justify-between py-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-200">{sess.deviceLabel}</span>
                {sess.isCurrent && (
                  <span className="rounded bg-sky-950 px-2 py-0.5 text-xs text-sky-400 font-semibold border border-sky-800">
                    This Device
                  </span>
                )}
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                    sess.stepUpLevel === "PRIVILEGED"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                      : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {sess.stepUpLevel}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                IP: {sess.ipAddress} • Last Active: {sess.lastActive}
              </p>
            </div>

            {!sess.isCurrent && (
              <button
                onClick={() => onRevokeSession(sess.sessionId)}
                className="rounded px-2.5 py-1 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-red-300"
              >
                Revoke
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
