// Visits surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// `VisitsSurface` lists the user's visit-prep sessions and lets them create a
// new one. A visit is a way to PREPARE for a doctor's appointment — collecting
// concerns and intake answers so the conversation with the clinician is more
// productive. It is never medical advice or a diagnosis: CLARA is a clinical
// assistant, not a doctor.
//
// It reads its data from `ApiClient.getVisits`, which returns 409 when the user
// has no PHR profile yet; that case renders a gentle "create a health profile
// first" prompt rather than an error. Loading uses skeletons, failures reuse
// `ErrorRetryView`, and an empty list uses `ClaraEmptyState`. All copy is
// Vietnamese-first and PII-free.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';
import '../language_controller.dart';
import 'visit_detail_surface.dart';

String _str(Object? value) => value == null ? '' : value.toString();

/// A single visit-prep session summarized on the Visits surface.
class _Visit {
  const _Visit({
    required this.id,
    required this.title,
    required this.reason,
    this.scheduledAt,
  });

  factory _Visit.fromJson(Map<String, dynamic> json) {
    // Be defensive about field names — render whichever the server provides.
    final title = _firstNonEmpty(<Object?>[
      json['title'],
      json['name'],
      json['summary'],
    ]);
    final reason = _firstNonEmpty(<Object?>[
      json['reason'],
      json['chief_complaint'],
      json['description'],
      json['note'],
    ]);
    final scheduled = _firstNonEmpty(<Object?>[
      json['scheduled_at'],
      json['scheduled_for'],
      json['visit_date'],
      json['appointment_at'],
    ]);
    return _Visit(
      id: _str(json['id']),
      title: title,
      reason: reason,
      scheduledAt: scheduled.isEmpty ? null : scheduled,
    );
  }

  final String id;
  final String title;
  final String reason;
  final String? scheduledAt;
}

/// Returns the first non-empty stringified value in [values], or `''`.
String _firstNonEmpty(List<Object?> values) {
  for (final value in values) {
    final s = _str(value).trim();
    if (s.isNotEmpty) return s;
  }
  return '';
}

/// The Visits surface: list visit-prep sessions and create new ones.
class VisitsSurface extends StatefulWidget {
  const VisitsSurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Optional app-level language state. Direct embedding remains
  /// Vietnamese-first when it is not supplied.
  final LanguageController? languageController;

  @override
  State<VisitsSurface> createState() => _VisitsSurfaceState();
}

class _VisitsSurfaceState extends State<VisitsSurface> {
  bool _loading = true;
  String? _error;

  /// True when the load failed with 409 (no PHR profile yet).
  bool _needsOnboarding = false;

  List<_Visit> _visits = const [];

  // --- "Tạo buổi khám" (create visit) form state ---------------------------
  bool _formOpen = false;
  bool _creating = false;
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _reasonController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  Future<void> _load() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _loading = false;
        _error = _copy[ConsumerTerm.sessionExpired];
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _needsOnboarding = false;
    });
    try {
      final data = await widget.apiClient.getVisits(accessToken: token);
      final visits = <_Visit>[];
      // The list may be top-level (`visits`/`data`/`items`) — be defensive.
      final raw = data['visits'] ?? data['data'] ?? data['items'];
      if (raw is List) {
        for (final item in raw) {
          if (item is Map) {
            visits.add(_Visit.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      if (!mounted) return;
      setState(() => _visits = visits);
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 409) {
        setState(() => _needsOnboarding = true);
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = _copy[ConsumerTerm.visitsLoadFailed]);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _createVisit() async {
    final token = _token;
    if (token == null || _creating) return;
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      _showSnack(_copy[ConsumerTerm.visitsNameRequired]);
      return;
    }
    setState(() => _creating = true);
    try {
      final reason = _reasonController.text.trim();
      await widget.apiClient.createVisit(
        accessToken: token,
        payload: <String, dynamic>{
          'title': title,
          'goal': reason,
          'visit_type': 'other',
        },
      );
      _titleController.clear();
      _reasonController.clear();
      if (mounted) {
        setState(() => _formOpen = false);
      }
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.visitsCreateFailed]);
    } finally {
      if (mounted) {
        setState(() => _creating = false);
      }
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  /// Formats an ISO date with the active UI locale, or a friendly fallback.
  String _formatScheduled(String? scheduledAt) {
    final trimmed = scheduledAt?.trim() ?? '';
    if (trimmed.isEmpty) return _copy[ConsumerTerm.visitsNoSchedule];
    final parsed = DateTime.tryParse(trimmed);
    if (parsed == null) return trimmed;
    final local = parsed.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    final date = _copy.locale == 'en'
        ? '${_englishMonth(local.month)} ${local.day}, ${local.year}'
        : '${two(local.day)}/${two(local.month)}/${local.year}';
    return _copy.format(ConsumerTerm.visitsScheduledDate, {'date': date});
  }

  String _englishMonth(int month) => const <String>[
        'Jan',
        'Feb',
        'Mar',
        'Apr',
        'May',
        'Jun',
        'Jul',
        'Aug',
        'Sep',
        'Oct',
        'Nov',
        'Dec',
      ][month - 1];

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController != null) {
      return AnimatedBuilder(
        animation: languageController,
        builder: (context, _) => _buildRefreshableBody(context),
      );
    }
    return _buildRefreshableBody(context);
  }

  Widget _buildRefreshableBody(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _visits.isEmpty && !_needsOnboarding) {
      return ListView(
        children: const [
          SizedBox(height: ClaraTokens.spaceLg),
          ClaraSkeletonList(itemCount: 4),
        ],
      );
    }
    if (_needsOnboarding) {
      return _buildOnboardingPrompt(context);
    }
    if (_error != null) {
      // Keep the error scrollable so pull-to-refresh still works.
      return ListView(
        children: [
          const SizedBox(height: ClaraTokens.spaceXl),
          ErrorRetryView(message: _error!, onRetry: _load),
        ],
      );
    }
    return _buildLoaded(context);
  }

  Widget _buildOnboardingPrompt(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      children: [
        ClaraCard.static_(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.assignment_ind_outlined,
                size: 40,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              Text(
                _copy[ConsumerTerm.visitsProfileRequiredTitle],
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                _copy[ConsumerTerm.visitsProfileRequiredDescription],
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLoaded(BuildContext context) {
    final children = <Widget>[
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Row(
          children: [
            Expanded(
              child: SectionHeader(
                title: _copy[ConsumerTerm.visitsTitle],
                emphasize: true,
              ),
            ),
            ClaraButton.secondary(
              label: _formOpen
                  ? _copy[ConsumerTerm.visitsClose]
                  : _copy[ConsumerTerm.visitsCreate],
              icon: _formOpen ? Icons.close : Icons.add,
              onPressed: () => setState(() => _formOpen = !_formOpen),
            ),
          ],
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      _buildStandingNote(context),
      const SizedBox(height: ClaraTokens.spaceMd),
    ];

    if (_formOpen) {
      children
        ..add(
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _buildForm(context),
          ),
        )
        ..add(const SizedBox(height: ClaraTokens.spaceMd));
    }

    if (_visits.isEmpty) {
      children.add(
        ClaraEmptyState(
          icon: Icons.event_note_outlined,
          title: _copy[ConsumerTerm.visitsEmptyTitle],
          message: _copy[ConsumerTerm.visitsEmptyDescription],
          action: ClaraButton.primary(
            label: _copy[ConsumerTerm.visitsCreate],
            icon: Icons.add,
            onPressed: () => setState(() => _formOpen = true),
          ),
        ),
      );
    } else {
      if (_loading) {
        children.add(
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: LinearProgressIndicator(),
          ),
        );
      }
      children.addAll(
        _visits.map(
          (visit) => Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildVisitCard(context, visit),
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: children,
    );
  }

  Widget _buildStandingNote(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: _copy[ConsumerTerm.visitsSafetyLabel],
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.info_outline,
              size: 20,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Text(
                _copy[ConsumerTerm.visitsSafetyNotice],
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildForm(BuildContext context) {
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _titleController,
            textInputAction: TextInputAction.next,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.visitsNameLabel],
              hintText: _copy[ConsumerTerm.visitsNameHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          TextField(
            controller: _reasonController,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(
              labelText: _copy[ConsumerTerm.visitsReasonLabel],
              hintText: _copy[ConsumerTerm.visitsReasonHint],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: _copy[ConsumerTerm.visitsCreate],
              icon: Icons.check,
              loading: _creating,
              onPressed: _createVisit,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVisitCard(BuildContext context, _Visit visit) {
    final theme = Theme.of(context);
    final details = <Widget>[];
    if (visit.reason.isNotEmpty) {
      details
        ..add(const SizedBox(height: ClaraTokens.spaceXs))
        ..add(
          Text(
            visit.reason,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        );
    }
    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.event_note_outlined,
                size: 20,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Text(
                  visit.title.isEmpty
                      ? _copy[ConsumerTerm.visitsUnnamed]
                      : visit.title,
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          ...details,
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            _formatScheduled(visit.scheduledAt),
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.secondary(
              label: _copy[ConsumerTerm.visitsOpenPreparation],
              icon: Icons.arrow_forward,
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => VisitDetailSurface(
                    apiClient: widget.apiClient,
                    sessionStore: widget.sessionStore,
                    visitId: visit.id,
                    title: visit.title.isEmpty
                        ? _copy[ConsumerTerm.visitsPreparationTitle]
                        : visit.title,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
