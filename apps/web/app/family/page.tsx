"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/ui/surface";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import {
  acceptFamilyInvitation,
  createFamilyInvitation,
  getFamilyShareOptions,
  listFamilyAccessLog,
  listFamilyGrants,
  listFamilyRelationships,
  revokeFamilyGrant,
  renewFamilyGrant,
  type FamilyAccessLog,
  type FamilyGrant,
} from "@/lib/visit-family";

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
      const [owned, received, history, options] = await Promise.all([
        listFamilyGrants(),
        listFamilyRelationships(),
        listFamilyAccessLog(),
        getFamilyShareOptions(),
      ]);
      setGrants(owned);
      setRelationships(received);
      setLogs(history);
      const nextShareable = {
        episode: options.episodes,
        visit: options.visits,
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
        scope: { object_type: objectType, object_id: objectId, allowed_actions: actions },
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

  const renew = async (grantId: string) => {
    setSaving(true);
    setError("");
    setCreatedToken("");
    try {
      const result = await renewFamilyGrant(
        grantId,
        new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      );
      setCreatedToken(result.token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo lời mời gia hạn.");
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
                            {grant.supporter_label || "Người hỗ trợ"} · {grant.object_type}
                          </p>
                          <p className="mt-1 text-sm text-[var(--text-secondary)]">
                            {grant.allowed_actions.join(", ")} · {grant.purpose}
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            Hết hạn {new Date(grant.expires_at).toLocaleString("vi-VN")}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          {grant.status !== "revoked" ? <Button type="button" variant="secondary" size="sm" disabled={saving} onClick={() => void renew(grant.id)}>Gia hạn</Button> : null}
                          <Button type="button" variant="danger" size="sm" disabled={saving || grant.status === "revoked"} onClick={() => void revoke(grant.id)}>
                            {grant.status === "revoked" ? "Đã thu hồi" : "Thu hồi"}
                          </Button>
                        </div>
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
                      <div key={relationship.id} className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4">
                        <p className="font-medium text-[var(--text-primary)]">
                          {relationship.supporter_label || "Phạm vi được chia sẻ"} · {relationship.object_type}
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
                    <div key={log.id} className="flex items-start gap-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3">
                      <span
                        className={`material-symbols-outlined text-base ${
                          log.outcome === "allowed"
                            ? "text-[var(--status-ok-text)]"
                            : "text-[var(--status-danger-text)]"
                        }`}
                      >
                        {log.outcome === "allowed" ? "verified_user" : "gpp_bad"}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                          {log.actor_label} · {log.action} · {log.outcome}
                        </p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {log.object_type} ·{" "}
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
              <Field
                label="Email người nhận"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <Select
                label="Chỉ chia sẻ"
                value={objectType}
                onChange={(event) => {
                  const nextType = event.target.value as "episode" | "visit";
                  setObjectType(nextType);
                  setObjectId(shareable[nextType][0]?.id || "");
                }}
              >
                <option value="episode">Một hành trình</option>
                <option value="visit">Một buổi khám</option>
              </Select>
              <Select
                label="Mục được chia sẻ"
                required
                value={objectId}
                onChange={(event) => setObjectId(event.target.value)}
              >
                <option value="">Chọn {objectType === "episode" ? "hành trình" : "buổi khám"}</option>
                {shareable[objectType].map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </Select>
              <Select
                label="Mục đích"
                value={purpose}
                onChange={(event) =>
                  setPurpose(event.target.value as "care_coordination" | "visit_support")
                }
              >
                <option value="care_coordination">Phối hợp chăm sóc</option>
                <option value="visit_support">Hỗ trợ đi khám</option>
              </Select>
              <Button type="submit" block disabled={saving}>
                Tạo mã mời
              </Button>
            </form>
            {createdToken ? (
              <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3">
                <p className="text-xs text-[var(--status-warn-text)]">
                  Mã chỉ hiển thị lần này; CLARA chưa tự gửi email.
                </p>
                <code className="mt-2 block break-all text-xs text-[var(--status-warn-text)]">
                  {createdToken}
                </code>
              </div>
            ) : null}
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">Chấp nhận lời mời</h2>
            <form className="mt-4 space-y-3" onSubmit={(event) => void accept(event)}>
              <Field
                label="Mã mời"
                required
                value={inviteToken}
                onChange={(event) => setInviteToken(event.target.value)}
              />
              <Button type="submit" variant="secondary" block disabled={saving}>
                Xem phạm vi và chấp nhận
              </Button>
            </form>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
