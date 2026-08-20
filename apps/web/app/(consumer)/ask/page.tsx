"use client";

import { Suspense, useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  AskComposer,
  type AttachedFileItem,
} from "@/components/ask/ask-composer";
import { AnswerRenderer } from "@/components/ask/answer-renderer";
import { EntryContextBanner } from "@/components/ask/entry-context-banner";
import { PersonalEvidenceDrawer } from "@/components/ask/personal-evidence-drawer";
import { Icon } from "@/components/ui/icon";
import {
  v2Client,
  type ConsumerAnswerEnvelope,
  type ConsumerAskRequest,
  type EntryContextDto,
  type WriteProposalDto,
  type ConsumerSafetyGuidanceDto,
  type ConsumerPersonalEvidenceDto,
  type ConsumerExternalSourceDto,
  type ConsumerDisclosureDto,
  type ConsumerUnknownDto,
} from "@/lib/api/v2-client";
import { usePreferences } from "@/components/shell/preference-provider";
import { useProfileContext } from "@/components/shell/profile-boundary";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

interface AskMessageExchange {
  id: string;
  userText: string;
  userAttachments?: AttachedFileItem[];
  entryContext?: EntryContextDto | null;
  answerEnvelope?: ConsumerAnswerEnvelope | null;
  streamingText?: string;
  status: "sending" | "streaming" | "complete" | "error" | "cancelled";
  errorMessage?: string;
}

const DEFAULT_SUGGESTIONS = [
  {
    title: "Giải thích kết quả xét nghiệm",
    query: "Hãy giải thích ý nghĩa các chỉ số trong kết quả xét nghiệm máu gần đây của tôi.",
    icon: "scan" as const,
  },
  {
    title: "Kiểm tra tác dụng phụ của thuốc",
    query: "Các thuốc tôi đang dùng có tương tác hoặc tác dụng phụ gì cần lưu ý không?",
    icon: "medication" as const,
  },
  {
    title: "Chuẩn bị câu hỏi trước khi đi khám",
    query: "Tôi sắp có buổi tái khám, tôi nên chuẩn bị những câu hỏi gì cho bác sĩ?",
    icon: "calendar" as const,
  },
  {
    title: "Chỉ số huyết áp và nhịp tim",
    query: "Chỉ số huyết áp 135/85 mmHg có phải là mức bình thường không?",
    icon: "body" as const,
  },
];

function ConsumerAskContent() {
  const searchParams = useSearchParams();
  const { uiLanguage } = usePreferences();
  const { activeProfileId } = useProfileContext();

  const [entryContext, setEntryContext] = useState<EntryContextDto | null>(null);
  const [exchange, setExchange] = useState<AskMessageExchange | null>(null);
  const [draftText, setDraftText] = useState("");
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const initialQueryHandled = useRef(false);

  const handleCancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setExchange((prev) => {
      if (!prev) return null;
      // Preserve draft from the canceled exchange so the user can easily re-edit
      setDraftText(prev.userText);
      return {
        ...prev,
        status: "cancelled",
        errorMessage: "Đã dừng câu trả lời. Bạn có thể chỉnh sửa câu hỏi và gửi lại.",
      };
    });
  }, []);

  const handleSendQuestion = useCallback(
    async (
      text: string,
      attachments: AttachedFileItem[] = [],
      scopedContext: EntryContextDto | null = entryContext,
    ) => {
      // Abort any ongoing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const exchangeId = `ask_${Date.now()}`;
      const newExchange: AskMessageExchange = {
        id: exchangeId,
        userText: text,
        userAttachments: attachments,
        entryContext: scopedContext,
        status: "sending",
        streamingText: "",
        answerEnvelope: null,
      };

      setExchange(newExchange);
      setDraftText(""); // Clear current draft as it is now in active exchange

      const requestPayload: ConsumerAskRequest = {
        text,
        entry_context: scopedContext,
        ui_language: uiLanguage,
        attachments: attachments.map((a) => ({
          id: a.id,
          name: a.name,
          mime_type: a.type,
          size: a.size,
        })),
      };

      try {
        await v2Client.streamAsk(
          requestPayload,
          {
            onStart: () => {
              setExchange((prev) => (prev ? { ...prev, status: "streaming" } : null));
            },
            onToken: (token) => {
              setExchange((prev) => {
                if (!prev) return null;
                const accumulated = (prev.streamingText || "") + token;
                return {
                  ...prev,
                  status: "streaming",
                  streamingText: accumulated,
                  answerEnvelope: prev.answerEnvelope
                    ? {
                        ...prev.answerEnvelope,
                        answer: {
                          ...prev.answerEnvelope.answer,
                          main_message: accumulated,
                        },
                      }
                    : {
                        answer: {
                          main_message: accumulated,
                          actions: [],
                          sections: [],
                        },
                      },
                };
              });
            },
            onMainMessage: (msg) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  streamingText: msg,
                  answerEnvelope: prev.answerEnvelope
                    ? {
                        ...prev.answerEnvelope,
                        answer: {
                          ...prev.answerEnvelope.answer,
                          main_message: msg,
                        },
                      }
                    : {
                        answer: {
                          main_message: msg,
                          actions: [],
                          sections: [],
                        },
                      },
                };
              });
            },
            onSafety: (safety: ConsumerSafetyGuidanceDto) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  answerEnvelope: {
                    answer: {
                      main_message: prev.streamingText || "",
                      actions: [],
                      sections: [],
                    },
                    ...(prev.answerEnvelope || {}),
                    safety,
                  },
                };
              });
            },
            onEvidence: (ev: {
              personal_evidence?: ConsumerPersonalEvidenceDto[];
              external_sources?: ConsumerExternalSourceDto[];
              disclosure?: ConsumerDisclosureDto;
            }) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  answerEnvelope: {
                    answer: {
                      main_message: prev.streamingText || "",
                      actions: [],
                      sections: [],
                    },
                    ...(prev.answerEnvelope || {}),
                    personal_evidence: ev.personal_evidence,
                    external_sources: ev.external_sources,
                    disclosure: ev.disclosure,
                  },
                };
              });
            },
            onProposals: (proposals: WriteProposalDto[]) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  answerEnvelope: {
                    answer: {
                      main_message: prev.streamingText || "",
                      actions: [],
                      sections: [],
                    },
                    ...(prev.answerEnvelope || {}),
                    write_proposals: proposals,
                  },
                };
              });
            },
            onUnknowns: (unknowns: ConsumerUnknownDto[]) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  answerEnvelope: {
                    answer: {
                      main_message: prev.streamingText || "",
                      actions: [],
                      sections: [],
                    },
                    ...(prev.answerEnvelope || {}),
                    unknowns,
                  },
                };
              });
            },
            onDone: (envelope: ConsumerAnswerEnvelope) => {
              setExchange((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  status: "complete",
                  answerEnvelope: envelope,
                  streamingText: envelope.answer?.main_message || prev.streamingText,
                };
              });
            },
            onError: (err) => {
              const rawMsg =
                typeof err === "string"
                  ? err
                  : err instanceof Error
                  ? err.message
                  : "Không thể nhận phản hồi";
              const safeMsg = sanitizeUpstreamError(rawMsg);

              setExchange((prev) => {
                if (!prev) return null;
                // Preserve draft on error
                setDraftText(prev.userText);
                return {
                  ...prev,
                  status: "error",
                  errorMessage: safeMsg,
                };
              });
            },
          },
          {
            signal: controller.signal,
            profileId: activeProfileId,
          }
        );
      } catch (err: any) {
        if (err?.name === "AbortError" || controller.signal.aborted) {
          // Handled by onCancel
          return;
        }
        const rawMsg = err instanceof Error ? err.message : String(err);
        const safeMsg = sanitizeUpstreamError(rawMsg);
        setExchange((prev) => {
          if (!prev) return null;
          setDraftText(prev.userText);
          return {
            ...prev,
            status: "error",
            errorMessage: safeMsg,
          };
        });
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    },
    [activeProfileId, entryContext, uiLanguage]
  );

  // Parse URL search params for initial query / context / action
  useEffect(() => {
    if (initialQueryHandled.current) return;

    const q = searchParams.get("q") || "";
    const contextKind = searchParams.get("context_kind");
    const contextId = searchParams.get("context_id");
    const contextLabel = searchParams.get("context_label");

    if (contextKind) {
      setEntryContext({
        kind: contextKind,
        resource_id: contextId,
        label: contextLabel || undefined,
      });
    }

    if (q.trim()) {
      setDraftText(q.trim());
      // Automatically send initial question if provided via query param
      initialQueryHandled.current = true;
      void handleSendQuestion(q.trim(), [], {
        kind: contextKind || "global",
        resource_id: contextId,
        label: contextLabel || undefined,
      });
    } else {
      initialQueryHandled.current = true;
    }
  }, [handleSendQuestion, searchParams]);

  // Clean up abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleConfirmProposal = async (proposal: WriteProposalDto) => {
    // Save to user health record if kind matches
    if (proposal.kind === "allergy") {
      await v2Client.addAllergy({
        substance: proposal.title,
        reaction: (proposal.data?.reaction as string) || proposal.summary || undefined,
        severity: (proposal.data?.severity as any) || "moderate",
      });
    } else if (proposal.kind === "condition") {
      await v2Client.addCondition({
        name: proposal.title,
        clinical_status: "active",
        notes: proposal.summary || undefined,
      });
    } else if (proposal.kind === "measurement" && proposal.data?.value && proposal.data?.unit) {
      await v2Client.addMeasurement({
        type: (proposal.data.type as string) || "vital",
        label: proposal.title,
        value: proposal.data.value as string | number,
        unit: proposal.data.unit as string,
        recorded_at: new Date().toISOString(),
      });
    }

    // Update proposal status in exchange
    setExchange((prev) => {
      if (!prev || !prev.answerEnvelope) return prev;
      const updatedProposals = (prev.answerEnvelope.write_proposals || []).map((p) =>
        p.id === proposal.id ? { ...p, status: "confirmed" } : p
      );
      return {
        ...prev,
        answerEnvelope: {
          ...prev.answerEnvelope,
          write_proposals: updatedProposals,
        },
      };
    });
  };

  const handleRejectProposal = async (proposal: WriteProposalDto) => {
    setExchange((prev) => {
      if (!prev || !prev.answerEnvelope) return prev;
      const updatedProposals = (prev.answerEnvelope.write_proposals || []).map((p) =>
        p.id === proposal.id ? { ...p, status: "rejected" } : p
      );
      return {
        ...prev,
        answerEnvelope: {
          ...prev.answerEnvelope,
          write_proposals: updatedProposals,
        },
      };
    });
  };

  const handleEditProposal = async (updatedProposal: WriteProposalDto) => {
    await handleConfirmProposal(updatedProposal);
    setExchange((prev) => {
      if (!prev || !prev.answerEnvelope) return prev;
      const updatedProposals = (prev.answerEnvelope.write_proposals || []).map((p) =>
        p.id === updatedProposal.id ? { ...updatedProposal, status: "edited" } : p
      );
      return {
        ...prev,
        answerEnvelope: {
          ...prev.answerEnvelope,
          write_proposals: updatedProposals,
        },
      };
    });
  };

  const handleStartNewQuestion = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setExchange(null);
    setDraftText("");
    setEntryContext(null);
  };

  const isSubmitting = exchange?.status === "sending" || exchange?.status === "streaming";

  return (
    <div className="space-y-6 pb-6" data-testid="consumer-ask-page">
      {/* Top Bar / Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="chat" size={20} aria-hidden="true" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
              Hỏi CLARA
            </h1>
          </div>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Trợ lý thông tin y tế với hướng dẫn an toàn và dẫn xuất nguồn rõ ràng
          </p>
        </div>

        {exchange ? (
          <button
            type="button"
            onClick={handleStartNewQuestion}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-ring"
            data-testid="ask-new-question-button"
          >
            <Icon name="plus" size={14} aria-hidden="true" />
            <span>Câu hỏi mới</span>
          </button>
        ) : null}
      </div>

      {/* Scoped Entry Context Banner if attached */}
      {entryContext ? (
        <EntryContextBanner
          context={entryContext}
          onClear={() => setEntryContext(null)}
        />
      ) : null}

      {/* Main Conversation Stream / Empty State */}
      <div className="min-h-[280px]">
        {!exchange ? (
          /* Empty State with Suggestions */
          <div className="py-6 space-y-6" data-testid="ask-empty-state">
            <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 text-center shadow-xs">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <Icon name="clinical-notes" size={24} aria-hidden="true" />
              </div>
              <h2 className="mt-3 text-base font-semibold text-[var(--text-primary)]">
                Bạn đang băn khoăn điều gì về sức khỏe?
              </h2>
              <p className="mx-auto mt-1.5 max-w-lg text-xs leading-relaxed text-[var(--text-secondary)]">
                Nhập triệu chứng, thuốc đang dùng, chụp ảnh nhãn thuốc hoặc tải tài liệu kết quả xét nghiệm để được giải thích an toàn.
              </p>
            </div>

            {/* Prompt Suggestion Cards */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-3">
                Gợi ý câu hỏi phổ biến
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {DEFAULT_SUGGESTIONS.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setDraftText(item.query);
                      void handleSendQuestion(item.query, [], entryContext);
                    }}
                    className="flex items-start gap-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-left transition-all hover:border-[color:var(--brand-500)]/40 hover:bg-[var(--surface-muted)] focus-ring"
                    data-testid={`suggestion-chip-${idx}`}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                      <Icon name={item.icon} size={18} aria-hidden="true" />
                    </span>
                    <div>
                      <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                        {item.title}
                      </h4>
                      <p className="mt-1 text-[11px] text-[var(--text-secondary)] leading-relaxed line-clamp-2">
                        {item.query}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Active Exchange Display */
          <div className="space-y-6" data-testid="ask-active-exchange">
            {/* User Message Bubble */}
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-[var(--radius-2xl)] rounded-br-xs bg-[var(--brand-600)] p-4 text-white shadow-sm sm:max-w-[75%]">
                <p className="text-sm font-medium leading-relaxed whitespace-pre-line" data-testid="ask-user-message-text">
                  {exchange.userText}
                </p>

                {/* Attached Files inside user bubble */}
                {exchange.userAttachments && exchange.userAttachments.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2 pt-2 border-t border-white/20">
                    {exchange.userAttachments.map((att) => (
                      <span
                        key={att.id}
                        className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-black/20 px-2.5 py-1 text-xs text-white/90"
                      >
                        <Icon name="folder" size={13} aria-hidden="true" />
                        <span className="max-w-[140px] truncate">{att.name}</span>
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            {/* Assistant Response Box */}
            <div>
              {exchange.status === "sending" && !exchange.streamingText ? (
                <div className="flex items-center gap-3 rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 text-sm text-[var(--text-secondary)]">
                  <span className="relative flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--brand-400)] opacity-75" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-[var(--brand-500)]" />
                  </span>
                  <span>CLARA đang phân tích câu hỏi và tổng hợp thông tin y tế an toàn...</span>
                </div>
              ) : exchange.status === "error" ? (
                <div className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-5 text-sm text-[var(--status-danger-text)]">
                  <div className="flex items-start gap-3">
                    <Icon name="warning" size={20} aria-hidden="true" className="shrink-0 mt-0.5" />
                    <div>
                      <h3 className="font-bold">Không thể hoàn tất câu trả lời</h3>
                      <p className="mt-1 leading-relaxed">{exchange.errorMessage}</p>
                      <p className="mt-2 text-xs font-semibold">
                        Nội dung câu hỏi của bạn đã được giữ lại trong ô nhập để bạn có thể thử gửi lại.
                      </p>
                    </div>
                  </div>
                </div>
              ) : exchange.status === "cancelled" ? (
                <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-sm text-[var(--text-secondary)]">
                  <div className="flex items-start gap-3">
                    <Icon name="stop" size={20} aria-hidden="true" className="shrink-0 mt-0.5 text-[var(--text-muted)]" />
                    <div>
                      <h3 className="font-semibold text-[var(--text-primary)]">Đã dừng câu trả lời</h3>
                      <p className="mt-1 leading-relaxed text-xs">{exchange.errorMessage}</p>
                    </div>
                  </div>
                </div>
              ) : exchange.answerEnvelope || exchange.streamingText ? (
                exchange.answerEnvelope?.answer?.sections && exchange.answerEnvelope.answer.sections.length > 0 ? (
                  <AnswerRenderer
                    envelope={exchange.answerEnvelope}
                    isStreaming={exchange.status === "streaming"}
                    onConfirmProposal={handleConfirmProposal}
                    onRejectProposal={handleRejectProposal}
                    onEditProposal={handleEditProposal}
                    onOpenEvidenceDrawer={() => setIsEvidenceDrawerOpen(true)}
                    locale={uiLanguage}
                  />
                ) : (
                  <AnswerRenderer
                    envelope={
                      exchange.answerEnvelope
                        ? {
                            ...exchange.answerEnvelope,
                            answer: {
                              actions:
                                exchange.answerEnvelope.answer?.actions ??
                                (exchange.answerEnvelope as any).actions ??
                                [],
                              sections:
                                exchange.answerEnvelope.answer?.sections ??
                                (exchange.answerEnvelope as any).sections ??
                                [],
                              main_message:
                                exchange.streamingText ||
                                exchange.answerEnvelope.answer?.main_message ||
                                (exchange.answerEnvelope as any).main_message ||
                                "",
                            },
                          }
                        : {
                            answer: {
                              main_message: exchange.streamingText || "",
                              actions: [],
                              sections: [],
                            },
                          }
                    }
                    isStreaming={exchange.status === "streaming"}
                    onConfirmProposal={handleConfirmProposal}
                    onRejectProposal={handleRejectProposal}
                    onEditProposal={handleEditProposal}
                    onOpenEvidenceDrawer={() => setIsEvidenceDrawerOpen(true)}
                    locale={uiLanguage}
                  />
                )
              ) : null}
            </div>
          </div>
        )}
      </div>

      {/* Composer Section at Bottom */}
      <div className="sticky bottom-2 z-20 pt-2 bg-[var(--bg-canvas)]/90 backdrop-blur-md">
        <AskComposer
          initialText={draftText}
          isSubmitting={isSubmitting}
          onSend={(text, attachments) => void handleSendQuestion(text, attachments, entryContext)}
          onCancel={handleCancel}
          locale={uiLanguage}
          autoFocus={!exchange}
        />

        {/* Safety Footer Disclaimer */}
        <p className="mt-2.5 text-center text-[11px] text-[var(--text-muted)]">
          CLARA là trợ lý hỗ trợ thông tin y tế, không thay thế việc chẩn đoán hay điều trị của bác sĩ chuyên khoa.
        </p>
      </div>

      {/* Personal Evidence Drawer */}
      <PersonalEvidenceDrawer
        isOpen={isEvidenceDrawerOpen}
        onClose={() => setIsEvidenceDrawerOpen(false)}
        evidence={exchange?.answerEnvelope?.personal_evidence || []}
        externalSources={exchange?.answerEnvelope?.external_sources || []}
        locale={uiLanguage}
      />
    </div>
  );
}

export default function ConsumerAskPage() {
  return (
    <Suspense
      fallback={
        <div className="py-12 text-center text-sm text-[var(--text-muted)]">
          Đang tải giao diện Hỏi CLARA...
        </div>
      }
    >
      <ConsumerAskContent />
    </Suspense>
  );
}
