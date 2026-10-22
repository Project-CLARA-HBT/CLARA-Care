import React, { useState } from "react";

export interface SignedInviteModalProps {
  tenantSlug: string;
  onGenerateInvite: (email: string, role: string) => Promise<string>;
  onClose: () => void;
}

export function SignedInviteModal({
  tenantSlug,
  onGenerateInvite,
  onClose,
}: SignedInviteModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("doctor");
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const token = await onGenerateInvite(email, role);
      setGeneratedLink(`https://${tenantSlug}.theclaracare.com/invite/accept?token=${token}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <h2 className="text-lg font-bold text-slate-100">Generate Signed Member Invite</h2>
        <p className="text-sm text-slate-400">
          Create a cryptographically signed, single-use membership invitation for clinic staff.
        </p>

        {!generatedLink ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300">Staff Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                placeholder="doctor@hospital.vn"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300">Role Assignment</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
              >
                <option value="doctor">Doctor / Clinician</option>
                <option value="researcher">Researcher</option>
                <option value="tenant_admin">Clinic Administrator</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg px-4 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
              >
                {loading ? "Generating..." : "Generate Signed Token"}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 p-3">
              <p className="text-xs font-semibold text-emerald-400">Invitation Ready (Valid 24 Hours)</p>
              <p className="mt-1 break-all font-mono text-xs text-slate-300">{generatedLink}</p>
            </div>
            <button
              onClick={onClose}
              className="w-full rounded-lg bg-slate-800 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
