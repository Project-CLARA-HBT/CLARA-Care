"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/lifemap/lifemap-primitives";
import {
  acceptFamilyInvitation,
  createFamilyInvitation,
  listFamilyAccessLog,
  listFamilyGrants,
  listFamilyRelationships,
  revokeFamilyGrant,
  type FamilyAccessLog,
  type FamilyGrant,
  listVisits,
} from "@/lib/visit-family";
import { getLifeMapToday } from "@/lib/lifemap";

const fieldClass =
  "mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25";

export default function FamilyPage() {
  const [grants, setGrants] = useState<FamilyGrant[]>([]);
  const [relationships, setRelationships] = useState<FamilyGrant[]>([]);
  const [logs, setLogs] = useState<FamilyAccessLog[]>([]);
  const [email, setEmail] = useState("");
  const [objectType, setObjectType] = useState<"episode" | "visit">("episode");
  const [objectId, setObjectId] = useState("");
  const [shareable, setShareable] = useState<{
    episode: Array<{ id: string; label: string }>;
    visit: Array<{ id: string; label: string }>;
  }>({ episode: [], visit: [] });
  const [purpose, setPurpose] = useState<"care_coordination" | "visit_support">(
    "care_coordination",
  );
  const [inviteToken, setInviteToken] = useState("");
  const [createdToken, setCreatedToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [owned, received, history, today, visits] = await Promise.all([
        listFamilyGrants(),
        listFamilyRelationships(),
        listFamilyAccessLog(),
        getLifeMapToday(),
        listVisits(),
      ]);
      setGrants(owned);
      setRelationships(received);
      setLogs(history);
      const nextShareable = {
        episode: today.episodes.map((episode) => ({ id: episode.id, label: episode.title })),
        visit: visits.map((visit) => ({ id: visit.id, label: visit.title })),
      };
      setShareable(nextShareable);
      setObjectId((current) => current || nextShareable.episode[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải Family Circle.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => void load(), [load]);

  const invite = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setCreatedToken("");
    try {
      const actions = objectType === "episode" ? ["view", "add_observation"] : ["view"];
      const result = await createFamilyInvitation({
        recipient_email: email.trim(),
        scope: { object_type: objectType, object_id: Number(objectId), allowed_actions: actions },
        purpose,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      });
      setCreatedToken(result.token);
      setEmail("");
      setObjectId("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo lời mời.");
    } finally {
      setSaving(false);
    }
  };

  const accept = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await acceptFamilyInvitation(inviteToken.trim());
      setInviteToken("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Lời mời không hợp lệ hoặc đã hết hạn.");
    } finally {
      setSaving(false);
    }
  };

  const revoke = async (grantId: string) => {
    setSaving(true);
    setError("");
    try {
      await revokeFamilyGrant(grantId);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể thu hồi quyền.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title="Family Circle"
      description="Chia sẻ đúng một hành trình hoặc buổi khám cho đúng người, đúng mục đích — không mở toàn bộ hồ sơ."
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
          {loading ? (
            <LoadingCards count={2} />
          ) : (
            <>
              <SurfaceCard className="overflow-hidden">
                <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                  <h2 className="font-semibold text-[var(--text-primary)]">Quyền bạn đã cấp</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Thu hồi có hiệu lực ở lần truy cập tiếp theo.
                  </p>
                </div>
                {grants.length ? (
                  <ul className="divide-y divide-[color:var(--shell-border)]">
                    {grants.map((grant) => (
                      <li key={grant.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-[var(--text-primary)]">
                            {grant.object_type} #{grant.object_id}
                          </p>
                          <p className="mt-1 text-sm text-[var(--text-secondary)]">
                            {grant.allowed_actions.join(", ")} · {grant.purpose}
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            Hết hạn {new Date(grant.expires_at).toLocaleString("vi-VN")}
                          </p>
                        </div>
                        <button
                          type="button"
                          disabled={saving || grant.status === "revoked"}
                          onClick={() => void revoke(grant.id)}
                          className="rounded-lg border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50 dark:border-rose-500/50 dark:text-rose-200"
                        >
                          {grant.status === "revoked" ? "Đã thu hồi" : "Thu hồi"}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    icon="family_restroom"
                    title="Bạn chưa chia sẻ dữ liệu nào"
                    description="Khi cần, hãy cấp quyền tối thiểu cho một người có tài khoản CLARA."
                  />
                )}
              </SurfaceCard>

              <SurfaceCard className="overflow-hidden">
                <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                  <h2 className="font-semibold text-[var(--text-primary)]">Bạn đang hỗ trợ</h2>
                </div>
                {relationships.length ? (
                  <div className="grid gap-3 p-4 sm:grid-cols-2">
                    {relationships.map((relationship) => (
                      <div key={relationship.id} className="rounded-xl bg-[var(--surface-muted)] p-4">
                        <p className="font-medium text-[var(--text-primary)]">
                          {relationship.object_type} #{relationship.object_id}
                        </p>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {relationship.allowed_actions.join(", ")}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    icon="diversity_1"
                    title="Chưa nhận lời mời nào"
                    description="Dán mã mời ở cột bên phải để chấp nhận đúng phạm vi được chia sẻ."
                  />
                )}
              </SurfaceCard>

              <SurfaceCard className="p-5">
                <h2 className="font-semibold text-[var(--text-primary)]">Nhật ký truy cập</h2>
                <div className="mt-4 space-y-2">
                  {logs.slice(0, 20).map((log) => (
                    <div key={log.id} className="flex items-start gap-3 rounded-xl bg-[var(--surface-muted)] p-3">
                      <span
                        className={`material-symbols-outlined text-base ${
                          log.outcome === "allowed"
                            ? "text-emerald-700 dark:text-emerald-200"
                            : "text-rose-700 dark:text-rose-200"
                        }`}
                      >
                        {log.outcome === "allowed" ? "verified_user" : "gpp_bad"}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                          {log.action} · {log.outcome}
                        </p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {log.object_type} #{log.object_id} ·{" "}
                          {new Date(log.created_at).toLocaleString("vi-VN")}
                        </p>
                      </div>
                    </div>
                  ))}
                  {!logs.length ? (
                    <p className="text-sm text-[var(--text-secondary)]">Chưa có lượt truy cập.</p>
                  ) : null}
                </div>
              </SurfaceCard>
            </>
          )}
        </div>

        <aside className="space-y-5">
          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Mời người hỗ trợ</h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              Người nhận phải dùng đúng email tài khoản CLARA. Mã hết hạn sau 7 ngày.
            </p>
            <form className="mt-4 space-y-3" onSubmit={(event) => void invite(event)}>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Email người nhận
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className={fieldClass}
                />
              </label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Chỉ chia sẻ
                <select
                  value={objectType}
                  onChange={(event) => {
                    const nextType = event.target.value as "episode" | "visit";
                    setObjectType(nextType);
                    setObjectId(shareable[nextType][0]?.id || "");
                  }}
                  className={fieldClass}
                >
                  <option value="episode">Một hành trình</option>
                  <option value="visit">Một buổi khám</option>
                </select>
              </label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Mục được chia sẻ
                <select
                  required
                  value={objectId}
                  onChange={(event) => setObjectId(event.target.value)}
                  className={fieldClass}
                >
                  <option value="">Chọn {objectType === "episode" ? "hành trình" : "buổi khám"}</option>
                  {shareable[objectType].map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Mục đích
                <select
                  value={purpose}
                  onChange={(event) =>
                    setPurpose(event.target.value as "care_coordination" | "visit_support")
                  }
                  className={fieldClass}
                >
                  <option value="care_coordination">Phối hợp chăm sóc</option>
                  <option value="visit_support">Hỗ trợ đi khám</option>
                </select>
              </label>
              <button
                disabled={saving}
                className="w-full rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
              >
                Tạo mã mời
              </button>
            </form>
            {createdToken ? (
              <div className="mt-4 rounded-xl bg-amber-50 p-3 dark:bg-amber-500/10">
                <p className="text-xs text-amber-900 dark:text-amber-100">
                  Mã chỉ hiển thị lần này; CLARA chưa tự gửi email.
                </p>
                <code className="mt-2 block break-all text-xs text-amber-950 dark:text-amber-50">
                  {createdToken}
                </code>
              </div>
            ) : null}
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Chấp nhận lời mời</h2>
            <form className="mt-4 space-y-3" onSubmit={(event) => void accept(event)}>
              <label className="block text-sm font-medium text-[var(--text-primary)]">
                Mã mời
                <input
                  required
                  value={inviteToken}
                  onChange={(event) => setInviteToken(event.target.value)}
                  className={fieldClass}
                />
              </label>
              <button
                disabled={saving}
                className="w-full rounded-xl border border-[var(--brand-500)] px-4 py-2.5 text-sm font-semibold text-[var(--brand-700)] disabled:opacity-60 dark:text-sky-200"
              >
                Xem phạm vi và chấp nhận
              </button>
            </form>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
