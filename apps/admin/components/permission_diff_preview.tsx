import React from "react";

export interface PermissionDiff {
  roleName: string;
  addedPermissions: string[];
  removedPermissions: string[];
  requiresMfaApproval: boolean;
}

export interface PermissionDiffPreviewProps {
  diff: PermissionDiff;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

export function PermissionDiffPreviewModal({
  diff,
  onConfirm,
  onCancel,
}: PermissionDiffPreviewProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <h2 className="text-lg font-bold text-slate-100">Permission Change Preview</h2>
        <p className="text-sm text-slate-400">
          Review the requested authorization modifications for role <span className="font-mono text-sky-400">{diff.roleName}</span>.
        </p>

        {/* Added Permissions */}
        {diff.addedPermissions.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase text-emerald-400">Granted Permissions (+{diff.addedPermissions.length})</h3>
            <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-2 text-xs font-mono text-emerald-300">
              {diff.addedPermissions.map((p) => (
                <div key={p}>+ {p}</div>
              ))}
            </div>
          </div>
        )}

        {/* Removed Permissions */}
        {diff.removedPermissions.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold uppercase text-red-400">Revoked Permissions (-{diff.removedPermissions.length})</h3>
            <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-2 text-xs font-mono text-red-300">
              {diff.removedPermissions.map((p) => (
                <div key={p}>- {p}</div>
              ))}
            </div>
          </div>
        )}

        {diff.requiresMfaApproval && (
          <div className="rounded-lg border border-amber-800 bg-amber-950/40 p-3 text-xs text-amber-300">
            MFA Step-Up Required: These modifications touch privileged administrative actions.
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500"
          >
            Submit with Approval
          </button>
        </div>
      </div>
    </div>
  );
}
