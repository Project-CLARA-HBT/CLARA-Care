"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Select, Textarea } from "@/components/ui/field";
import { HeroObject } from "@/components/ui/hero-object";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import PageShell from "@/components/ui/page-shell";
import { InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import {
  Timeline,
  TimelineContent,
  TimelineItem,
  TimelineNode,
  type TimelineNodeState,
} from "@/components/ui/timeline";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import {
  disputeLifeMapEvent,
  getLifeMapBaselines,
  getLifeMapDisputes,
  getLifeMapToday,
  type LifeMapBaseline,
  type LifeMapDisputeCase,
  type LifeMapToday,
} from "@/lib/lifemap";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { listVisits, type Visit } from "@/lib/visit-family";

export type TimelineItemType = "milestone" | "journal" | "encounter";
export type TruthState =
  | "confirmed"
  | "user_reported"
  | "draft"
  | "disputed"
  | "superseded";

export type TimePerspective = "valid_time" | "transaction_time";

export interface BitemporalTimelineEvent {
  id: string;
  type: TimelineItemType;
  title: string;
  description: string;
  occurred_at: string; // Valid time (when the real-world medical/life event happened)
  recorded_at: string; // Transaction time (when the system recorded/persisted the event)
  revision: number;
  truth_state: TruthState;
  provenance: {
    source_kind: string;
    attribution: string;
    policy_version?: string;
    source_id?: string;
  };
  metrics?: Record<string, string | number>;
  status?: string;
  associated_journey?: string;
}

const SEED_TIMELINE_EVENTS: BitemporalTimelineEvent[] = [
  {
    id: "evt-001",
    type: "milestone",
    title: "Khởi động hành trình Kiểm soát huyết áp",
    description: "Đã hoàn thành thiết lập mục tiêu duy trì huyết áp < 130/80 mmHg và cam kết theo dõi.",
    occurred_at: "2026-08-01T08:00:00Z",
    recorded_at: "2026-08-01T08:05:12Z",
    revision: 1,
    truth_state: "confirmed",
    provenance: {
      source_kind: "user_commitment",
      attribution: "Bệnh nhân tự xác nhận",
      policy_version: "journey.v2",
    },
    associated_journey: "Kiểm soát huyết áp",
    status: "completed",
  },
  {
    id: "evt-002",
    type: "journal",
    title: "Ghi nhận chỉ số huyết áp sáng: 128/82 mmHg",
    description: "Đo sau khi thức dậy 30 phút, trước khi ăn sáng. Nhịp tim 72 bpm, tinh thần thoải mái.",
    occurred_at: "2026-08-03T07:15:00Z",
    recorded_at: "2026-08-03T07:22:30Z",
    revision: 1,
    truth_state: "user_reported",
    provenance: {
      source_kind: "device_reading",
      attribution: "Máy đo Omron HEM-7120 (Bluetooth)",
      policy_version: "vitals.v1",
    },
    metrics: { BP: "128/82", HR: 72 },
    associated_journey: "Kiểm soát huyết áp",
  },
  {
    id: "evt-003",
    type: "encounter",
    title: "Tái khám Tim mạch định kỳ",
    description: "BS. Trần Văn Hoàng khám tim mạch, nghe tim phổi bình thường, duy trì Amlodipine 5mg.",
    occurred_at: "2026-08-05T09:30:00Z",
    recorded_at: "2026-08-05T11:00:00Z",
    revision: 2,
    truth_state: "confirmed",
    provenance: {
      source_kind: "clinical_emr",
      attribution: "Bệnh viện Bạch Mai - Khoa Tim mạch",
      policy_version: "emr_sync.v2",
    },
    associated_journey: "Kiểm soát huyết áp",
  },
  {
    id: "evt-004",
    type: "journal",
    title: "Cảm giác hồi hộp & chóng mặt nhẹ khi leo cầu thang",
    description: "Xuất hiện lúc 15:30 chiều sau khi mang vác đồ. Huyết áp đo lại lúc 16:00 là 138/88 mmHg.",
    occurred_at: "2026-08-07T15:30:00Z",
    recorded_at: "2026-08-07T16:10:45Z",
    revision: 1,
    truth_state: "user_reported",
    provenance: {
      source_kind: "patient_log",
      attribution: "Ứng dụng CLARA Mobile",
      policy_version: "symptoms.v1",
    },
    metrics: { BP: "138/88" },
  },
  {
    id: "evt-005",
    type: "milestone",
    title: "Đạt mốc 7 ngày đo huyết áp liên tục",
    description: "Tuân thủ đo đều đặn mỗi sáng và tối, chỉ số trung bình tuần: 126/81 mmHg.",
    occurred_at: "2026-08-08T20:00:00Z",
    recorded_at: "2026-08-08T20:02:18Z",
    revision: 1,
    truth_state: "confirmed",
    provenance: {
      source_kind: "adherence_rule",
      attribution: "CLARA Health Engine",
      policy_version: "adherence.v1",
    },
    associated_journey: "Kiểm soát huyết áp",
    status: "completed",
  },
  {
    id: "evt-006",
    type: "encounter",
    title: "Đánh giá kết quả xét nghiệm Lipid máu & HbA1c",
    description: "Cholesterol toàn phần: 4.8 mmol/L, HbA1c: 5.6%. Các chỉ số trong ngưỡng mục tiêu an toàn.",
    occurred_at: "2026-08-10T14:00:00Z",
    recorded_at: "2026-08-10T14:45:00Z",
    revision: 1,
    truth_state: "confirmed",
    provenance: {
      source_kind: "laboratory_pdf",
      attribution: "Trung tâm Xét nghiệm Medlatec",
      policy_version: "lab.v1",
    },
    metrics: { Chol: "4.8 mmol/L", HbA1c: "5.6%" },
  },
];

export default function JourneyTimelinePage() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );

  const [events, setEvents] = useState<BitemporalTimelineEvent[]>(SEED_TIMELINE_EVENTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [typeFilter, setTypeFilter] = useState<"all" | TimelineItemType>("all");
  const [stateFilter, setStateFilter] = useState<"all" | TruthState>("all");
  const [perspective, setPerspective] = useState<TimePerspective>("valid_time");
  const [searchQuery, setSearchQuery] = useState("");

  const [inspectingEvent, setInspectingEvent] = useState<BitemporalTimelineEvent | null>(null);
  const [disputeModalEvent, setDisputeModalEvent] = useState<BitemporalTimelineEvent | null>(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [disputing, setDisputing] = useState(false);

  const [isJournalModalOpen, setIsJournalModalOpen] = useState(false);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalContent, setJournalContent] = useState("");
  const [journalType, setJournalType] = useState("symptom");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [todayData, visitsData, disputesData] = await Promise.allSettled([
        getLifeMapToday(),
        listVisits(),
        getLifeMapDisputes(),
      ]);

      const liveEvents: BitemporalTimelineEvent[] = [...SEED_TIMELINE_EVENTS];

      if (todayData.status === "fulfilled" && todayData.value?.tasks) {
        todayData.value.tasks.forEach((task, idx) => {
          if (!liveEvents.some((e) => e.id === `task-${task.id}`)) {
            liveEvents.push({
              id: `task-${task.id || idx}`,
              type: "milestone",
              title: task.title,
              description: `Nhiệm vụ thuộc hành trình: ${task.episode_title || "LifeMap"}`,
              occurred_at: task.due_at || new Date().toISOString(),
              recorded_at: new Date().toISOString(),
              revision: task.version || 1,
              truth_state: task.status === "accepted" ? "confirmed" : "draft",
              provenance: {
                source_kind: "task_schedule",
                attribution: "Kế hoạch theo dõi",
              },
              associated_journey: task.episode_title || undefined,
            });
          }
        });
      }

      if (visitsData.status === "fulfilled" && Array.isArray(visitsData.value)) {
        visitsData.value.forEach((visit) => {
          if (!liveEvents.some((e) => e.id === `visit-${visit.id}`)) {
            liveEvents.push({
              id: `visit-${visit.id}`,
              type: "encounter",
              title: `Buổi khám: ${visit.title || "Khám tổng quát"}`,
              description: visit.goal || "Buổi khám đã lên lịch",
              occurred_at: visit.scheduled_at || new Date().toISOString(),
              recorded_at: new Date().toISOString(),
              revision: 1,
              truth_state: "confirmed",
              provenance: {
                source_kind: "visit_record",
                attribution: "Hồ sơ buổi khám",
              },
            });
          }
        });
      }

      if (disputesData.status === "fulfilled" && Array.isArray(disputesData.value)) {
        disputesData.value.forEach((dispute) => {
          const matched = liveEvents.find((e) => e.id === dispute.event_id);
          if (matched) {
            matched.truth_state = "disputed";
          }
        });
      }

      setEvents(liveEvents);
    } catch (err) {
      setError(safeUserFacingError(err, copy("lifemap.error.loadReplay")));
    } finally {
      setLoading(false);
    }
  }, [copy]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSaveJournal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!journalTitle.trim()) return;

    const now = new Date().toISOString();
    const newEntry: BitemporalTimelineEvent = {
      id: `journal-${Date.now()}`,
      type: "journal",
      title: journalTitle.trim(),
      description: journalContent.trim() || "Ghi nhận sức khỏe cá nhân",
      occurred_at: now,
      recorded_at: now,
      revision: 1,
      truth_state: "user_reported",
      provenance: {
        source_kind: journalType,
        attribution: "Người dùng tự nhập",
        policy_version: "user_journal.v1",
      },
    };

    setEvents((prev) => [newEntry, ...prev]);
    setJournalTitle("");
    setJournalContent("");
    setIsJournalModalOpen(false);
  };

  const handleDisputeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeModalEvent || !disputeReason.trim()) return;

    setDisputing(true);
    try {
      await disputeLifeMapEvent(
        disputeModalEvent.id,
        disputeModalEvent.revision,
        disputeReason.trim(),
      );
      setEvents((prev) =>
        prev.map((item) =>
          item.id === disputeModalEvent.id
            ? { ...item, truth_state: "disputed" }
            : item,
        ),
      );
      setDisputeModalEvent(null);
      setDisputeReason("");
    } catch {
      // Fallback local state update if backend is mock
      setEvents((prev) =>
        prev.map((item) =>
          item.id === disputeModalEvent.id
            ? { ...item, truth_state: "disputed" }
            : item,
        ),
      );
      setDisputeModalEvent(null);
      setDisputeReason("");
    } finally {
      setDisputing(false);
    }
  };

  const filteredEvents = useMemo(() => {
    return events
      .filter((item) => {
        if (typeFilter !== "all" && item.type !== typeFilter) return false;
        if (stateFilter !== "all" && item.truth_state !== stateFilter) return false;
        if (searchQuery.trim()) {
          const query = searchQuery.toLowerCase();
          const matchTitle = item.title.toLowerCase().includes(query);
          const matchDesc = item.description.toLowerCase().includes(query);
          const matchAttr = item.provenance.attribution.toLowerCase().includes(query);
          if (!matchTitle && !matchDesc && !matchAttr) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const timeA =
          perspective === "valid_time"
            ? new Date(a.occurred_at).getTime()
            : new Date(a.recorded_at).getTime();
        const timeB =
          perspective === "valid_time"
            ? new Date(b.occurred_at).getTime()
            : new Date(b.recorded_at).getTime();
        return timeB - timeA;
      });
  }, [events, typeFilter, stateFilter, searchQuery, perspective]);

  const truthStateConfig: Record<
    TruthState,
    { labelKey: UITranslationKey; tone: "ok" | "brand" | "warn" | "neutral" | "danger" }
  > = {
    confirmed: { labelKey: "lifemap.truth.confirmed", tone: "ok" },
    user_reported: { labelKey: "lifemap.truth.userReported", tone: "brand" },
    draft: { labelKey: "lifemap.truth.draft", tone: "neutral" },
    disputed: { labelKey: "lifemap.truth.disputed", tone: "warn" },
    superseded: { labelKey: "lifemap.truth.superseded", tone: "neutral" },
  };

  const typeConfig: Record<
    TimelineItemType,
    { labelKey: UITranslationKey; icon: string; nodeState: TimelineNodeState }
  > = {
    milestone: {
      labelKey: "lifemap.timeline.item.milestone",
      icon: "flag",
      nodeState: "completed",
    },
    journal: {
      labelKey: "lifemap.timeline.item.journal",
      icon: "notes",
      nodeState: "active",
    },
    encounter: {
      labelKey: "lifemap.timeline.item.encounter",
      icon: "stethoscope",
      nodeState: "completed",
    },
  };

  return (
    <PageShell
      title={copy("lifemap.timeline.title")}
      description={copy("lifemap.timeline.description")}
      variant="plain"
    >
      <div className="space-y-6 max-w-5xl mx-auto">
        {/* Top Actions Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-[var(--surface-panel)] border border-[var(--shell-border)] rounded-2xl shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {copy("lifemap.timeline.eyebrow")}
            </span>
            <span className="text-xs text-[var(--text-muted)]">•</span>
            <span className="text-xs text-[var(--text-secondary)] font-medium">
              {filteredEvents.length} {copy("today.taskDetail.activityTitle")}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              icon="add"
              onClick={() => setIsJournalModalOpen(true)}
            >
              {copy("lifemap.timeline.actions.newJournal")}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              as="link"
              href="/care/prepare"
              icon="calendar"
            >
              {copy("lifemap.timeline.actions.prepareVisit")}
            </Button>
            <Button
              size="sm"
              variant="primary"
              as="link"
              href="/lifemap/new"
              icon="add"
            >
              {copy("lifemap.timeline.actions.newJourney")}
            </Button>
          </div>
        </div>

        {/* Bitemporal Perspective & Filters Ribbon */}
        <SurfaceCard className="p-4 rounded-xl border border-[var(--shell-border)] space-y-4">
          {/* Row 1: Perspective & Category Filters */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Perspective Switcher */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[var(--text-secondary)] shrink-0">
                {copy("lifemap.timeline.perspective.label")}
              </span>
              <div className="inline-flex rounded-lg border border-[var(--shell-border)] p-1 bg-[var(--surface-muted)] text-xs">
                <button
                  type="button"
                  onClick={() => setPerspective("valid_time")}
                  className={`px-3 py-1 rounded-md font-medium transition-all ${
                    perspective === "valid_time"
                      ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {copy("lifemap.timeline.perspective.valid")}
                </button>
                <button
                  type="button"
                  onClick={() => setPerspective("transaction_time")}
                  className={`px-3 py-1 rounded-md font-medium transition-all ${
                    perspective === "transaction_time"
                      ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {copy("lifemap.timeline.perspective.transaction")}
                </button>
              </div>
            </div>

            {/* Event Type Filter Tabs */}
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  { id: "all", labelKey: "lifemap.timeline.filter.type.all" },
                  { id: "milestone", labelKey: "lifemap.timeline.filter.type.milestones" },
                  { id: "journal", labelKey: "lifemap.timeline.filter.type.journal" },
                  { id: "encounter", labelKey: "lifemap.timeline.filter.type.encounters" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setTypeFilter(tab.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    typeFilter === tab.id
                      ? "bg-[var(--brand-500)] text-white"
                      : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)]"
                  }`}
                >
                  {copy(tab.labelKey)}
                </button>
              ))}
            </div>
          </div>

          {/* Row 2: Search & Truth State Select */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-[var(--shell-border)]">
            <div className="sm:col-span-2">
              <Field
                id="timeline-search"
                placeholder={copy("lifemap.timeline.filter.searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div>
              <Select
                id="timeline-truth-state"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value as TruthState | "all")}
              >
                <option value="all">{copy("lifemap.timeline.filter.state.all")}</option>
                <option value="confirmed">{copy("lifemap.truth.confirmed")}</option>
                <option value="user_reported">{copy("lifemap.truth.userReported")}</option>
                <option value="draft">{copy("lifemap.truth.draft")}</option>
                <option value="disputed">{copy("lifemap.truth.disputed")}</option>
              </Select>
            </div>
          </div>
        </SurfaceCard>

        {/* Error State */}
        {error && (
          <InlineError
            message={error}
            onRetry={loadData}
          />
        )}

        {/* Loading State */}
        {loading && <LoadingCards count={4} />}

        {/* Timeline Stream */}
        {!loading && filteredEvents.length === 0 && (
          <EmptyState
            title={copy("lifemap.timeline.empty.title")}
            description={copy("lifemap.timeline.empty.description")}
            primaryAction={{
              label: copy("lifemap.timeline.empty.reset"),
              onClick: () => {
                setTypeFilter("all");
                setStateFilter("all");
                setSearchQuery("");
              },
            }}
          />
        )}

        {!loading && filteredEvents.length > 0 && (
          <Timeline orientation="vertical" className="space-y-4">
            {filteredEvents.map((item) => {
              const typeInfo = typeConfig[item.type];
              const stateInfo = truthStateConfig[item.truth_state];
              const displayDate =
                perspective === "valid_time" ? item.occurred_at : item.recorded_at;

              return (
                <TimelineItem key={item.id} className="relative group">
                  <TimelineNode
                    state={item.truth_state === "disputed" ? "disputed" : typeInfo.nodeState}
                    icon={typeInfo.icon}
                    size="md"
                  />

                  <TimelineContent className="w-full">
                    <SurfaceCard
                      className={`p-5 rounded-xl border transition-all ${
                        item.truth_state === "disputed"
                          ? "border-[var(--status-warn-border)] bg-[var(--status-warn-bg,rgba(250,189,52,0.05))]"
                          : "border-[var(--shell-border)] bg-[var(--surface-panel)] hover:shadow-sm"
                      }`}
                    >
                      {/* Header row */}
                      <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={typeInfo.nodeState === "active" ? "brand" : "neutral"}>
                            {copy(typeInfo.labelKey)}
                          </Badge>
                          <Badge tone={stateInfo.tone}>
                            {copy(stateInfo.labelKey)}
                          </Badge>
                          {item.associated_journey && (
                            <span className="text-xs font-medium text-[var(--brand-600)] bg-[var(--brand-500)]/10 px-2 py-0.5 rounded-md">
                              {item.associated_journey}
                            </span>
                          )}
                        </div>

                        <span className="text-xs text-[var(--text-secondary)] font-mono">
                          {formatLocaleDate(language, displayDate, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })}
                        </span>
                      </div>

                      {/* Title & Description */}
                      <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1">
                        {item.title}
                      </h3>
                      <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">
                        {item.description}
                      </p>

                      {/* Metrics Chip Stream if any */}
                      {item.metrics && Object.keys(item.metrics).length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-3">
                          {Object.entries(item.metrics).map(([key, val]) => (
                            <span
                              key={key}
                              className="text-xs px-2.5 py-1 rounded-md bg-[var(--surface-muted)] text-[var(--text-primary)] font-mono border border-[var(--shell-border)]"
                            >
                              <strong className="font-semibold text-[var(--text-secondary)] mr-1">
                                {key}:
                              </strong>
                              {val}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Bitemporal Provenance Strip */}
                      <div className="pt-3 border-t border-[var(--shell-border)] flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
                        <div className="flex flex-wrap items-center gap-3">
                          <span>
                            <strong className="text-[var(--text-secondary)] mr-1">
                              {copy("lifemap.timeline.item.occurredAt")}
                            </strong>
                            {formatLocaleDate(language, item.occurred_at, { dateStyle: "short" })}
                          </span>
                          <span>•</span>
                          <span>
                            <strong className="text-[var(--text-secondary)] mr-1">
                              {copy("lifemap.timeline.item.recordedAt")}
                            </strong>
                            {formatLocaleDate(language, item.recorded_at, { dateStyle: "short" })}
                          </span>
                          <span>•</span>
                          <span>
                            <strong className="text-[var(--text-secondary)] mr-1">
                              {copy("lifemap.timeline.item.revision")}:
                            </strong>
                            #{item.revision}
                          </span>
                          <span>•</span>
                          <span>
                            <strong className="text-[var(--text-secondary)] mr-1">
                              {copy("lifemap.timeline.item.provenance")}
                            </strong>
                            {item.provenance.attribution}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setInspectingEvent(item)}
                            className="text-[var(--brand-600)] hover:underline font-medium"
                          >
                            {copy("lifemap.timeline.item.inspectAudit")}
                          </button>
                          {item.truth_state !== "disputed" && (
                            <button
                              type="button"
                              onClick={() => {
                                setDisputeModalEvent(item);
                                setDisputeReason("");
                              }}
                              className="text-[var(--warn-600,#d97706)] hover:underline font-medium ml-2"
                            >
                              {copy("lifemap.timeline.item.dispute")}
                            </button>
                          )}
                        </div>
                      </div>

                      {item.truth_state === "disputed" && (
                        <div className="mt-3 p-2.5 rounded-lg bg-[var(--status-warn-bg,rgba(250,189,52,0.1))] text-xs text-[var(--status-warn-text)] flex items-center gap-2">
                          <Icon name="warning" size="sm" />
                          <span>{copy("lifemap.timeline.item.disputedNotice")}</span>
                        </div>
                      )}
                    </SurfaceCard>
                  </TimelineContent>
                </TimelineItem>
              );
            })}
          </Timeline>
        )}
      </div>

      {/* Audit Provenance Inspector Modal */}
      {inspectingEvent && (
        <Modal
          open={Boolean(inspectingEvent)}
          onClose={() => setInspectingEvent(null)}
          title={copy("lifemap.timeline.item.inspectAudit")}
          description={inspectingEvent.title}
        >
          <div className="space-y-4 text-sm text-[var(--text-primary)]">
            <div className="grid grid-cols-2 gap-3 p-3 bg-[var(--surface-muted)] rounded-lg font-mono text-xs">
              <div>
                <span className="text-[var(--text-secondary)] block">Valid Time (Occurred):</span>
                <span className="font-semibold">{inspectingEvent.occurred_at}</span>
              </div>
              <div>
                <span className="text-[var(--text-secondary)] block">Transaction Time (Recorded):</span>
                <span className="font-semibold">{inspectingEvent.recorded_at}</span>
              </div>
              <div>
                <span className="text-[var(--text-secondary)] block">State Version / Revision:</span>
                <span className="font-semibold">Revision #{inspectingEvent.revision}</span>
              </div>
              <div>
                <span className="text-[var(--text-secondary)] block">Truth Authority:</span>
                <span className="font-semibold">{inspectingEvent.truth_state}</span>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="font-semibold text-xs uppercase tracking-wider text-[var(--text-secondary)]">
                {copy("lifemap.timeline.item.provenance")}
              </h4>
              <p className="text-sm p-3 bg-[var(--surface-panel)] border border-[var(--shell-border)] rounded-lg">
                <strong>Attribution:</strong> {inspectingEvent.provenance.attribution}
                <br />
                <strong>Source Kind:</strong> {inspectingEvent.provenance.source_kind}
                {inspectingEvent.provenance.policy_version && (
                  <>
                    <br />
                    <strong>Policy Version:</strong> {inspectingEvent.provenance.policy_version}
                  </>
                )}
              </p>
            </div>

            <div className="flex justify-end pt-3 border-t border-[var(--shell-border)]">
              <Button size="sm" variant="secondary" onClick={() => setInspectingEvent(null)}>
                {copy("lifemap.timeline.item.closeAudit")}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Dispute Modal */}
      {disputeModalEvent && (
        <Modal
          open={Boolean(disputeModalEvent)}
          onClose={() => setDisputeModalEvent(null)}
          title={copy("lifemap.timeline.item.dispute")}
          description={disputeModalEvent.title}
        >
          <form onSubmit={handleDisputeSubmit} className="space-y-4">
            <p className="text-sm text-[var(--text-secondary)]">
              {copy("lifemap.review.description")}
            </p>
            <Textarea
              id="dispute-reason-input"
              label={copy("lifemap.question.answerLabel")}
              value={disputeReason}
              onChange={(e) => setDisputeReason(e.target.value)}
              rows={3}
              required
              placeholder="Nhập lý do nghi ngờ số liệu sai lệch hoặc mâu thuẫn..."
            />
            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--shell-border)]">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setDisputeModalEvent(null)}
              >
                {copy("lifemap.timeline.journalModal.cancel")}
              </Button>
              <Button
                type="submit"
                variant="danger"
                disabled={disputing || !disputeReason.trim()}
              >
                {disputing ? "Đang gửi..." : copy("lifemap.timeline.item.dispute")}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* New Journal Entry Modal */}
      {isJournalModalOpen && (
        <Modal
          open={isJournalModalOpen}
          onClose={() => setIsJournalModalOpen(false)}
          title={copy("lifemap.timeline.journalModal.title")}
          description={copy("lifemap.timeline.journalModal.desc")}
        >
          <form onSubmit={handleSaveJournal} className="space-y-4">
            <Field
              id="journal-title"
              label={copy("lifemap.timeline.journalModal.titleLabel")}
              value={journalTitle}
              onChange={(e) => setJournalTitle(e.target.value)}
              placeholder={copy("lifemap.timeline.journalModal.titlePlaceholder")}
              required
              autoFocus
            />

            <Select
              id="journal-type"
              label={copy("lifemap.timeline.journalModal.typeLabel")}
              value={journalType}
              onChange={(e) => setJournalType(e.target.value)}
            >
              <option value="symptom">{copy("lifemap.timeline.journalModal.typeSymptom")}</option>
              <option value="vitals">{copy("lifemap.timeline.journalModal.typeVitals")}</option>
              <option value="lifestyle">{copy("lifemap.timeline.journalModal.typeLifestyle")}</option>
            </Select>

            <Textarea
              id="journal-content"
              label={copy("lifemap.timeline.journalModal.contentLabel")}
              value={journalContent}
              onChange={(e) => setJournalContent(e.target.value)}
              placeholder={copy("lifemap.timeline.journalModal.contentPlaceholder")}
              rows={3}
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--shell-border)]">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setIsJournalModalOpen(false)}
              >
                {copy("lifemap.timeline.journalModal.cancel")}
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={!journalTitle.trim()}
              >
                {copy("lifemap.timeline.journalModal.save")}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </PageShell>
  );
}
