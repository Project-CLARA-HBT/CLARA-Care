"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/ui/surface";
import Button from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
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
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );
  const objectLabel = (objectType: string) => {
    if (objectType === "episode") return copy("familyCircle.object.episode");
    if (objectType === "visit") return copy("familyCircle.object.visit");
    if (objectType === "care_task") return copy("familyCircle.object.careTask");
    return copy("familyCircle.label.sharedScope");
  };
  const actionLabel = (action: string) => {
    if (action === "view") return copy("familyCircle.permission.view");
    if (action === "add_observation") return copy("familyCircle.permission.addObservation");
    if (action === "complete_task") return copy("familyCircle.permission.completeTask");
    return copy("familyCircle.permission.other");
  };
  const outcomeLabel = (outcome: string) => {
    if (outcome === "allowed") return copy("familyCircle.outcome.allowed");
    if (outcome === "denied") return copy("familyCircle.outcome.denied");
    if (outcome === "unknown") return copy("familyCircle.outcome.unknown");
    return copy("familyCircle.outcome.other");
  };
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
    } catch {
      setError(copy("familyCircle.loadError"));
    } finally {
      setLoading(false);
    }
  }, [copy]);
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
    } catch {
      setError(copy("familyCircle.createError"));
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
    } catch {
      setError(copy("familyCircle.acceptError"));
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
    } catch {
      setError(copy("familyCircle.revokeError"));
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
    } catch {
      setError(copy("familyCircle.renewError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      variant="plain"
      title={copy("familyCircle.title")}
      description={copy("familyCircle.description")}
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
                  <h2 className="font-semibold text-[var(--text-primary)]">{copy("familyCircle.grants.title")}</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    {copy("familyCircle.grants.description")}
                  </p>
                </div>
                {grants.length ? (
                  <ul className="divide-y divide-[color:var(--shell-border)]">
                    {grants.map((grant) => (
                      <li key={grant.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-[var(--text-primary)]">
                            {grant.supporter_label || copy("familyCircle.label.supporter")} · {objectLabel(grant.object_type)}
                          </p>
                          <p className="mt-1 text-sm text-[var(--text-secondary)]">
                            {grant.allowed_actions.map(actionLabel).join(", ")} · {grant.purpose === "care_coordination" ? copy("familyCircle.purpose.careCoordination") : copy("familyCircle.purpose.visitSupport")}
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            {copy("familyCircle.label.expires", { date: formatLocaleDate(language, grant.expires_at, { dateStyle: "medium", timeStyle: "short" }) })}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          {grant.status !== "revoked" ? <Button type="button" variant="secondary" size="sm" disabled={saving} onClick={() => void renew(grant.id)}>{copy("familyCircle.action.renew")}</Button> : null}
                          <Button type="button" variant="danger" size="sm" disabled={saving || grant.status === "revoked"} onClick={() => void revoke(grant.id)}>
                            {grant.status === "revoked" ? copy("familyCircle.action.revoked") : copy("familyCircle.action.revoke")}
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    icon="family_restroom"
                    title={copy("familyCircle.grants.emptyTitle")}
                    description={copy("familyCircle.grants.emptyDescription")}
                  />
                )}
              </SurfaceCard>

              <SurfaceCard className="overflow-hidden">
                <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                  <h2 className="font-semibold text-[var(--text-primary)]">{copy("familyCircle.relationships.title")}</h2>
                </div>
                {relationships.length ? (
                  <div className="grid gap-3 p-4 sm:grid-cols-2">
                    {relationships.map((relationship) => (
                      <div key={relationship.id} className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4">
                        <p className="font-medium text-[var(--text-primary)]">
                          {relationship.supporter_label || copy("familyCircle.label.sharedScope")} · {objectLabel(relationship.object_type)}
                        </p>
                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                          {relationship.allowed_actions.map(actionLabel).join(", ")}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    icon="diversity_1"
                    title={copy("familyCircle.relationships.emptyTitle")}
                    description={copy("familyCircle.relationships.emptyDescription")}
                  />
                )}
              </SurfaceCard>

              <SurfaceCard className="p-5">
                <h2 className="font-semibold text-[var(--text-primary)]">{copy("familyCircle.accessLog.title")}</h2>
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
                          {log.actor_label} · {actionLabel(log.action)} · {outcomeLabel(log.outcome)}
                        </p>
                        <p className="text-xs text-[var(--text-muted)]">
                          {objectLabel(log.object_type)} ·{" "}
                          {formatLocaleDate(language, log.created_at, { dateStyle: "medium", timeStyle: "short" })}
                        </p>
                      </div>
                    </div>
                  ))}
                  {!logs.length ? (
                    <p className="text-sm text-[var(--text-secondary)]">{copy("familyCircle.accessLog.empty")}</p>
                  ) : null}
                </div>
              </SurfaceCard>
            </>
          )}
        </div>

        <aside className="space-y-5">
          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">{copy("familyCircle.invite.title")}</h2>
            <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
              {copy("familyCircle.invite.description")}
            </p>
            <form className="mt-4 space-y-3" onSubmit={(event) => void invite(event)}>
              <Field
                label={copy("familyCircle.invite.email")}
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <Select
                label={copy("familyCircle.invite.scope")}
                value={objectType}
                onChange={(event) => {
                  const nextType = event.target.value as "episode" | "visit";
                  setObjectType(nextType);
                  setObjectId(shareable[nextType][0]?.id || "");
                }}
              >
                <option value="episode">{copy("familyCircle.object.episode")}</option>
                <option value="visit">{copy("familyCircle.object.visit")}</option>
              </Select>
              <Select
                label={copy("familyCircle.invite.sharedItem")}
                required
                value={objectId}
                onChange={(event) => setObjectId(event.target.value)}
              >
                <option value="">{copy("familyCircle.invite.chooseItem", { item: objectLabel(objectType) })}</option>
                {shareable[objectType].map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </Select>
              <Select
                label={copy("familyCircle.invite.purpose")}
                value={purpose}
                onChange={(event) =>
                  setPurpose(event.target.value as "care_coordination" | "visit_support")
                }
              >
                <option value="care_coordination">{copy("familyCircle.purpose.careCoordination")}</option>
                <option value="visit_support">{copy("familyCircle.purpose.visitSupport")}</option>
              </Select>
              <Button type="submit" block disabled={saving}>
                {copy("familyCircle.invite.create")}
              </Button>
            </form>
            {createdToken ? (
              <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3">
                <p className="text-xs text-[var(--status-warn-text)]">
                  {copy("familyCircle.invite.createdNotice")}
                </p>
                <code className="mt-2 block break-all text-xs text-[var(--status-warn-text)]">
                  {createdToken}
                </code>
              </div>
            ) : null}
          </SurfaceCard>

          <SurfaceCard className="p-5">
            <h2 className="font-semibold text-[var(--text-primary)]">{copy("familyCircle.accept.title")}</h2>
            <form className="mt-4 space-y-3" onSubmit={(event) => void accept(event)}>
              <Field
                label={copy("familyCircle.accept.token")}
                required
                value={inviteToken}
                onChange={(event) => setInviteToken(event.target.value)}
              />
              <Button type="submit" variant="secondary" block disabled={saving}>
                {copy("familyCircle.accept.submit")}
              </Button>
            </form>
          </SurfaceCard>
        </aside>
      </div>
    </PageShell>
  );
}
