// Live pipeline "process" status for the CLARA chat surface.
//
// The chat SSE stream (`POST /api/v1/chat/stream`) emits one `step` event per
// backend pipeline `flow_event` — routing, safety guards, retrieval, evidence
// search/index, external corroboration, GraphRAG, synthesis, verification, …
// (see `services/ml/.../streaming/chat_stream.py` and the `_flow_event`s in
// `rag/pipeline.py`). Each frame carries `{index, stage, status, note, ...}`.
//
// This module turns that raw stream into a friendly, Vietnamese-first "CLARA
// đang làm gì" panel so the user sees WHICH node the request is at, not just a
// spinner. It is pure/presentational: the parent owns the list of steps and
// passes them in. Colors/typography come from `Theme.of(context)`; motion is
// resolved through `A11y` so it collapses under reduced motion.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// Lifecycle status of a single pipeline node, decoupled from color.
enum ChatFlowStatus { pending, running, completed, warning, error }

/// One node in the live pipeline process, distilled from an SSE `step` frame.
///
/// Immutable value type so the parent can rebuild a fresh list on each frame
/// without in-place mutation surprises. [stage] is the raw backend stage id
/// (e.g. `internal_retrieval`); [label] is its friendly localized name.
@immutable
class ChatFlowStep {
  const ChatFlowStep({
    required this.stage,
    required this.status,
    this.note,
  });

  /// Raw backend stage identifier (stable key used for de-duplication).
  final String stage;

  /// Lifecycle status parsed from the frame's `status` field.
  final ChatFlowStatus status;

  /// Optional short human note from the backend (`note`/`detail`).
  final String? note;

  ChatFlowStep copyWith({ChatFlowStatus? status, String? note}) => ChatFlowStep(
        stage: stage,
        status: status ?? this.status,
        note: note ?? this.note,
      );
}

/// Parses a backend `status` string into a [ChatFlowStatus] (fail-soft: an
/// unknown/absent status is treated as `running`, the most useful live default).
ChatFlowStatus parseFlowStatus(Object? raw) {
  final value = raw?.toString().trim().toLowerCase() ?? '';
  switch (value) {
    case 'completed':
    case 'complete':
    case 'done':
    case 'ok':
    case 'success':
      return ChatFlowStatus.completed;
    case 'warning':
    case 'warn':
    case 'degraded':
      return ChatFlowStatus.warning;
    case 'error':
    case 'failed':
    case 'failure':
      return ChatFlowStatus.error;
    case 'started':
    case 'start':
    case 'running':
    case 'in_progress':
      return ChatFlowStatus.running;
    default:
      return ChatFlowStatus.running;
  }
}

/// Folds a raw SSE `step` frame's fields into (or onto) an ordered, de-duplicated
/// list of [ChatFlowStep]s.
///
/// The backend emits a `started` then a `completed` frame for the same stage;
/// this collapses them so the panel shows one row per node whose status
/// advances in place (started → completed/warning/error) rather than a noisy
/// duplicate list. Order of first appearance is preserved.
List<ChatFlowStep> foldFlowStep(
  List<ChatFlowStep> current, {
  required String stage,
  required ChatFlowStatus status,
  String? note,
}) {
  final trimmedStage = stage.trim();
  if (trimmedStage.isEmpty) {
    return current;
  }
  final next = List<ChatFlowStep>.of(current);
  final existingIndex = next.indexWhere((s) => s.stage == trimmedStage);
  if (existingIndex < 0) {
    next.add(ChatFlowStep(stage: trimmedStage, status: status, note: note));
    return next;
  }
  // Never regress a terminal state (completed/warning/error) back to running:
  // a late `started` frame for an already-finished stage is ignored so the row
  // does not flicker backwards.
  final existing = next[existingIndex];
  final existingTerminal = existing.status == ChatFlowStatus.completed ||
      existing.status == ChatFlowStatus.warning ||
      existing.status == ChatFlowStatus.error;
  if (existingTerminal && status == ChatFlowStatus.running) {
    return next;
  }
  next[existingIndex] = existing.copyWith(
    status: status,
    note: note ?? existing.note,
  );
  return next;
}

/// Friendly, Vietnamese-first label + icon for a backend pipeline [stage].
///
/// Falls back to a prettified form of the raw stage id for any node not
/// explicitly mapped, so a newly-added backend stage still renders sensibly.
({String label, IconData icon}) describeFlowStage(String stage,
    {bool isEnglish = false}) {
  switch (stage) {
    case 'routing':
    case 'router':
      return (
        label: isEnglish ? 'Routing the request' : 'Định tuyến câu hỏi',
        icon: Icons.alt_route
      );
    case 'emergency_guard':
    case 'emergency_fastpath':
      return (
        label: isEnglish ? 'Emergency screening' : 'Sàng lọc khẩn cấp',
        icon: Icons.emergency_outlined
      );
    case 'legal_guard':
    case 'safety_override':
    case 'retrieval_policy':
      return (
        label: isEnglish ? 'Safety guardrails' : 'Kiểm tra an toàn',
        icon: Icons.verified_user_outlined
      );
    case 'smalltalk_fastpath':
      return (
        label: isEnglish ? 'Quick reply' : 'Trả lời nhanh',
        icon: Icons.bolt_outlined
      );
    case 'planner':
    case 'llm_query_planner':
    case 'query_decomposition':
      return (
        label: isEnglish ? 'Planning retrieval' : 'Lập kế hoạch tra cứu',
        icon: Icons.route_outlined
      );
    case 'retrieval_orchestrator':
      return (
        label: isEnglish ? 'Orchestrating retrieval' : 'Điều phối tra cứu',
        icon: Icons.hub_outlined
      );
    case 'internal_retrieval':
      return (
        label:
            isEnglish ? 'Searching knowledge base' : 'Tìm trong kho tri thức',
        icon: Icons.folder_open_outlined
      );
    case 'evidence_search':
      return (
        label: isEnglish ? 'Searching for evidence' : 'Tìm bằng chứng',
        icon: Icons.travel_explore_outlined
      );
    case 'evidence_index':
    case 'keyword_filter':
      return (
        label: isEnglish ? 'Ranking evidence' : 'Xếp hạng bằng chứng',
        icon: Icons.sort_outlined
      );
    case 'external_scientific_retrieval':
      return (
        label: isEnglish
            ? 'Consulting scientific sources'
            : 'Tra cứu nguồn khoa học',
        icon: Icons.science_outlined
      );
    case 'graphrag_sidecar':
      return (
        label: isEnglish
            ? 'Analyzing knowledge graph'
            : 'Phân tích đồ thị tri thức',
        icon: Icons.account_tree_outlined
      );
    case 'evidence_review':
    case 'contradiction_miner':
      return (
        label: isEnglish ? 'Reviewing evidence' : 'Rà soát bằng chứng',
        icon: Icons.fact_check_outlined
      );
    case 'answer_synthesis':
    case 'llm_generation':
    case 'llm_generation_retry':
    case 'generate':
    case 'deep_beta_report_synthesis':
    case 'deep_beta_chain_synthesis':
      return (
        label: isEnglish ? 'Composing the answer' : 'Tổng hợp câu trả lời',
        icon: Icons.auto_awesome_outlined
      );
    case 'citation_selection':
      return (
        label: isEnglish ? 'Selecting citations' : 'Chọn nguồn trích dẫn',
        icon: Icons.format_quote_outlined
      );
    case 'verification':
    case 'verification_matrix':
    case 'deep_beta_chain_verification':
    case 'deep_beta_evidence_verification':
    case 'deep_beta_evidence_audit':
      return (
        label: isEnglish ? 'Verifying claims' : 'Kiểm chứng nội dung',
        icon: Icons.rule_outlined
      );
    case 'degraded_recovery':
      return (
        label: isEnglish ? 'Recovering safely' : 'Phục hồi an toàn',
        icon: Icons.health_and_safety_outlined
      );
    default:
      return (
        label: _prettifyStage(stage),
        icon: Icons.settings_suggest_outlined
      );
  }
}

/// Turns a raw snake_case stage id into a readable Title Case label as a
/// fallback for unmapped stages (e.g. `deep_beta_gap_fill` → `Deep Beta Gap Fill`).
String _prettifyStage(String stage) {
  final cleaned = stage.replaceAll(RegExp(r'[_\-]+'), ' ').trim();
  if (cleaned.isEmpty) return stage;
  return cleaned
      .split(RegExp(r'\s+'))
      .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');
}

/// A compact, live "process" panel showing which pipeline node CLARA is at.
///
/// While [isActive] (the turn is still streaming) it shows the current node
/// prominently with a subtle progress affordance and an expandable list of all
/// steps so far. When the turn finishes it collapses to a single quiet summary
/// row the user can tap to review what happened.
class ChatFlowStatusView extends StatefulWidget {
  const ChatFlowStatusView({
    super.key,
    required this.steps,
    required this.isActive,
    this.isEnglish = false,
  });

  final List<ChatFlowStep> steps;
  final bool isActive;
  final bool isEnglish;

  @override
  State<ChatFlowStatusView> createState() => _ChatFlowStatusViewState();
}

class _ChatFlowStatusViewState extends State<ChatFlowStatusView> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    if (widget.steps.isEmpty) {
      return const SizedBox.shrink();
    }
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // The "current" node is the last running one, else the last known step.
    final current = widget.steps.lastWhere(
      (s) => s.status == ChatFlowStatus.running,
      orElse: () => widget.steps.last,
    );
    final desc = describeFlowStage(current.stage, isEnglish: widget.isEnglish);

    final expanded = _expanded || widget.isActive;

    final headerLabel = widget.isActive
        ? desc.label
        : (widget.isEnglish
            ? 'Process (${widget.steps.length} steps)'
            : 'Tiến trình (${widget.steps.length} bước)');

    return Container(
      margin: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            liveRegion: widget.isActive,
            button: !widget.isActive,
            label: widget.isActive
                ? '${widget.isEnglish ? 'CLARA is' : 'CLARA đang'}: ${desc.label}'
                : headerLabel,
            child: InkWell(
              borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
              onTap: widget.isActive
                  ? null
                  : () => setState(() => _expanded = !_expanded),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaraTokens.spaceMd,
                  vertical: ClaraTokens.spaceSm,
                ),
                child: Row(
                  children: [
                    if (widget.isActive)
                      _SpinningLeading(color: scheme.primary)
                    else
                      Icon(Icons.checklist_rtl_outlined,
                          size: 18, color: scheme.onSurfaceVariant),
                    const SizedBox(width: ClaraTokens.spaceSm),
                    Expanded(
                      child: Text(
                        headerLabel,
                        style: textTheme.labelLarge?.copyWith(
                          color: scheme.onSurface,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    if (!widget.isActive)
                      Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                        size: 20,
                        color: scheme.onSurfaceVariant,
                      ),
                  ],
                ),
              ),
            ),
          ),
          if (expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceSm,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (var i = 0; i < widget.steps.length; i++)
                    _FlowStepRow(
                      step: widget.steps[i],
                      isLast: i == widget.steps.length - 1,
                      isEnglish: widget.isEnglish,
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// One row in the expanded process list: a status dot + connector line, the
/// node's friendly label, and its status conveyed by icon + (implicit) text.
class _FlowStepRow extends StatelessWidget {
  const _FlowStepRow({
    required this.step,
    required this.isLast,
    required this.isEnglish,
  });

  final ChatFlowStep step;
  final bool isLast;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final desc = describeFlowStage(step.stage, isEnglish: isEnglish);
    final color = _statusColor(context, step.status);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              const SizedBox(height: 2),
              _StatusDot(status: step.status, color: color),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 2),
                    color: scheme.outlineVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(desc.icon, size: 15, color: scheme.onSurfaceVariant),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                          desc.label,
                          style: textTheme.bodySmall?.copyWith(
                            color: scheme.onSurface,
                            fontWeight: step.status == ChatFlowStatus.running
                                ? FontWeight.w600
                                : FontWeight.w400,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (step.status == ChatFlowStatus.warning ||
                      step.status == ChatFlowStatus.error)
                    Padding(
                      padding: const EdgeInsets.only(top: 2, left: 21),
                      child: Text(
                        _statusWord(step.status, isEnglish),
                        style: textTheme.labelSmall?.copyWith(color: color),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  static String _statusWord(ChatFlowStatus status, bool isEnglish) {
    switch (status) {
      case ChatFlowStatus.warning:
        return isEnglish
            ? 'Degraded — continued safely'
            : 'Suy giảm — vẫn tiếp tục an toàn';
      case ChatFlowStatus.error:
        return isEnglish
            ? 'Failed — fell back'
            : 'Lỗi — đã chuyển phương án dự phòng';
      default:
        return '';
    }
  }
}

Color _statusColor(BuildContext context, ChatFlowStatus status) {
  final scheme = Theme.of(context).colorScheme;
  switch (status) {
    case ChatFlowStatus.completed:
      return Colors.green.shade600;
    case ChatFlowStatus.warning:
      return Colors.orange.shade700;
    case ChatFlowStatus.error:
      return scheme.error;
    case ChatFlowStatus.running:
      return scheme.primary;
    case ChatFlowStatus.pending:
      return scheme.onSurfaceVariant;
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status, required this.color});

  final ChatFlowStatus status;
  final Color color;

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case ChatFlowStatus.running:
        return SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(strokeWidth: 2, color: color),
        );
      case ChatFlowStatus.completed:
        return Icon(Icons.check_circle, size: 14, color: color);
      case ChatFlowStatus.warning:
        return Icon(Icons.warning_amber_rounded, size: 14, color: color);
      case ChatFlowStatus.error:
        return Icon(Icons.error_outline, size: 14, color: color);
      case ChatFlowStatus.pending:
        return Icon(Icons.radio_button_unchecked, size: 14, color: color);
    }
  }
}

/// A small spinning leading indicator for the active header; collapses to a
/// static icon under reduced motion.
class _SpinningLeading extends StatelessWidget {
  const _SpinningLeading({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    if (A11y.prefersReducedMotion(context)) {
      return Icon(Icons.sync, size: 18, color: color);
    }
    return SizedBox(
      width: 18,
      height: 18,
      child: CircularProgressIndicator(strokeWidth: 2.2, color: color),
    );
  }
}
