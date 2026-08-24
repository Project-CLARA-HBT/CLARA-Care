// Today agenda surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// Spec v5 Section 7.1 Recomposition:
//   1. Date & Context greeting header (`Hôm nay, [Date]`).
//   2. Next accepted task as dominant `HeroObject` (title, due time, severity badge, complete action).
//   3. Upcoming accepted tasks timeline.
//   4. Pending confirmations row.
//   5. Active LifeMap journey preview.
//   6. Secondary utility actions (`Hỏi CLARA`, `Tủ thuốc`, `Chuẩn bị khám`).
//   7. Progress / recent authentic source changes.
//
// Gated on PHR profile (409 returns onboarding). Supports offline caching.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/home_v2_model.dart';
import '../../core/lifemap_read_cache.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_chip.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

String _str(Object? value) => value == null ? '' : value.toString();

String _severityBadgeLabel(String severity, ConsumerTerminology copy) {
  final norm = severity.toLowerCase();
  if (norm == 'critical') return copy[ConsumerTerm.homeSeverityCritical];
  if (norm == 'urgent' || norm == 'high') {
    return copy[ConsumerTerm.homeSeverityUrgent];
  }
  if (norm == 'attention' || norm == 'warning' || norm == 'soon') {
    return copy[ConsumerTerm.homeSeverityAttention];
  }
  if (norm == 'routine') return copy[ConsumerTerm.homeSeverityRoutine];
  return copy[ConsumerTerm.homeSeverityNormal];
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
    ][(month - 1).clamp(0, 11)];

/// A single accepted task rendered on the Today agenda.
class _TodayTask {
  const _TodayTask({
    required this.id,
    required this.title,
    this.dueAt,
    this.completed = false,
    this.severity = 'normal',
    this.episodeTitle,
  });

  factory _TodayTask.fromJson(Map<String, dynamic> json) => _TodayTask(
        id: _str(json['id']),
        title: _str(json['title'] ?? json['name'] ?? json['medication_name']),
        dueAt: json['due_at'] == null
            ? (json['time'] == null ? null : _str(json['time']))
            : _str(json['due_at']),
        completed: json['status'] == 'completed' || json['completed'] == true,
        severity: _str(json['severity'] ?? json['priority'] ?? 'normal').toLowerCase(),
        episodeTitle:
            json['episode_title'] == null ? null : _str(json['episode_title']),
      );

  final String id;
  final String title;
  final String? dueAt;
  final bool completed;
  final String severity;
  final String? episodeTitle;

  bool get isUrgent =>
      severity == 'urgent' || severity == 'critical' || severity == 'high';
  bool get isAttention =>
      severity == 'attention' || severity == 'warning' || severity == 'soon';
}

/// A single open care episode summarized on the Today agenda.
class _TodayEpisode {
  const _TodayEpisode({
    required this.id,
    required this.title,
    this.priority = 'routine',
  });

  factory _TodayEpisode.fromJson(Map<String, dynamic> json) => _TodayEpisode(
        id: _str(json['id']),
        title: _str(json['title']),
        priority:
            _str(json['priority']).isEmpty ? 'routine' : _str(json['priority']),
      );

  final String id;
  final String title;
  final String priority;
}

/// The daily agenda surface: accepted tasks, open journeys, and the pending-
/// confirmation count.
class TodaySurface extends StatefulWidget {
  const TodaySurface({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.onNeedsOnboarding,
    this.onOpenLifeMap,
    this.onAskHealth,
    this.onCheckMedicines,
    this.onSaveHealthInfo,
    this.onPrepareVisit,
    this.readCache,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Invoked when the agenda cannot load because no PHR profile exists yet
  /// (the API returns 409). The caller routes the user to onboarding.
  final VoidCallback? onNeedsOnboarding;

  /// Invoked when the user chooses to open the full LifeMap surface.
  final VoidCallback? onOpenLifeMap;

  /// Task-first entry points. They navigate only to existing consent-gated
  /// surfaces and never create or confirm health data on the user's behalf.
  final VoidCallback? onAskHealth;
  final VoidCallback? onCheckMedicines;
  final VoidCallback? onSaveHealthInfo;
  final VoidCallback? onPrepareVisit;
  final LifeMapReadCache? readCache;

  /// Optional app-level language state.
  final LanguageController? languageController;

  @override
  State<TodaySurface> createState() => _TodaySurfaceState();
}

class _TodaySurfaceState extends State<TodaySurface> {
  bool _loading = true;
  String? _error;

  /// True when the load failed with 409 (no PHR profile yet).
  bool _needsOnboarding = false;

  HomeV2Model? _homeModel;
  List<_TodayTask> _tasks = const [];
  List<_TodayEpisode> _episodes = const [];
  List<HomeRecentChange> _recentChanges = const [];
  HomeNextAction? _topAction;
  int _pendingConfirmationCount = 0;
  DateTime? _offlineCachedAt;
  DateTime? _offlineValidUntil;

  /// Ids of tasks whose "Hoàn tất" action is in flight.
  final Set<String> _completing = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
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
      Map<String, dynamic> data;
      try {
        data = await widget.apiClient.getHomeV2(accessToken: token);
      } on ApiException catch (e) {
        if (e.statusCode == 409) rethrow;
        data = await widget.apiClient.getLifeMapToday(accessToken: token);
      } catch (_) {
        data = await widget.apiClient.getLifeMapToday(accessToken: token);
      }

      final homeModel = HomeV2Model.fromJson(data);

      final tasks = <_TodayTask>[];
      final rawTasks = data['today'] ?? data['tasks'] ?? data['schedule'];
      if (rawTasks is List) {
        for (final item in rawTasks) {
          if (item is Map) {
            tasks.add(_TodayTask.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      final episodes = <_TodayEpisode>[];
      final rawEpisodes = data['episodes'];
      if (rawEpisodes is List) {
        for (final item in rawEpisodes) {
          if (item is Map) {
            episodes.add(_TodayEpisode.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      final pending = data['pending_confirmation_count'];
      await widget.readCache?.save(data);
      if (!mounted) return;
      setState(() {
        _homeModel = homeModel;
        _tasks = tasks;
        _episodes = episodes;
        _topAction = homeModel.topAction;
        _recentChanges = homeModel.recentChanges;
        _pendingConfirmationCount =
            pending is int ? pending : int.tryParse(_str(pending)) ?? 0;
        _offlineCachedAt = null;
        _offlineValidUntil = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 409) {
        widget.onNeedsOnboarding?.call();
        setState(() => _needsOnboarding = true);
        return;
      }
      if (await _restoreOfflineCache()) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      if (await _restoreOfflineCache()) return;
      setState(() => _error = _copy[ConsumerTerm.todayLoadFailed]);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<bool> _restoreOfflineCache() async {
    final cached = await widget.readCache?.read();
    if (cached == null || !mounted) return false;
    final data = cached.data;
    final tasks = (data['tasks'] as List? ?? data['today'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => _TodayTask.fromJson(item.cast<String, dynamic>()))
        .toList();
    final episodes = (data['episodes'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => _TodayEpisode.fromJson(item.cast<String, dynamic>()))
        .toList();
    setState(() {
      _homeModel = HomeV2Model.fromJson(data);
      _tasks = tasks;
      _episodes = episodes;
      _topAction = _homeModel?.topAction;
      _recentChanges = _homeModel?.recentChanges ?? const [];
      _pendingConfirmationCount = data['pending_confirmation_count'] is int
          ? data['pending_confirmation_count'] as int
          : 0;
      _offlineCachedAt = cached.cachedAt;
      _offlineValidUntil = cached.validUntil;
      _error = null;
    });
    return true;
  }

  Future<void> _completeTask(_TodayTask task) async {
    if (_offlineCachedAt != null) {
      _showSnack(_copy[ConsumerTerm.todayOfflineActionBlocked]);
      return;
    }
    final token = _token;
    if (token == null || _completing.contains(task.id)) return;
    setState(() => _completing.add(task.id));
    try {
      await widget.apiClient
          .completeLifeMapTask(accessToken: token, taskId: task.id);
      await _load();
    } on ApiException catch (error) {
      _showSnack(error.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.todayCompleteFailed]);
    } finally {
      if (mounted) {
        setState(() => _completing.remove(task.id));
      }
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  String _formatDue(String? dueAt) {
    final trimmed = dueAt?.trim() ?? '';
    if (trimmed.isEmpty) return _copy[ConsumerTerm.todayNoDueDate];
    final parsed = DateTime.tryParse(trimmed);
    if (parsed == null) return _copy[ConsumerTerm.todayNoDueDate];
    final local = parsed.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    final date = _copy.locale == 'en'
        ? '${_englishMonth(local.month)} ${local.day}, ${local.year}'
        : '${two(local.day)}/${two(local.month)}/${local.year}';
    return _copy.format(ConsumerTerm.todayDueDate, {'date': date});
  }

  String _formatTodayDate(DateTime now, ConsumerTerminology copy) {
    final local = now.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    if (copy.locale == 'en') {
      return '${_englishMonth(local.month)} ${local.day}, ${local.year}';
    }
    return '${two(local.day)}/${two(local.month)}/${local.year}';
  }

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
    if (_loading && _tasks.isEmpty && _episodes.isEmpty && !_needsOnboarding) {
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
    if (_error != null && _tasks.isEmpty) {
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
                _copy[ConsumerTerm.todayProfileRequiredTitle],
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                _copy[ConsumerTerm.todayProfileRequiredDescription],
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceLg),
              ClaraButton.primary(
                label: _copy[ConsumerTerm.todayCreateProfile],
                icon: Icons.arrow_forward,
                onPressed: () => widget.onNeedsOnboarding?.call(),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLoaded(BuildContext context) {
    final copy = _copy;
    final topAction = _topAction;
    final recentChanges = _recentChanges;

    final uncompletedTasks = _tasks.where((t) => !t.completed).toList();
    final completedTasks = _tasks.where((t) => t.completed).toList();
    final isCaughtUp = _tasks.isNotEmpty && uncompletedTasks.isEmpty;

    final nextTask =
        uncompletedTasks.isNotEmpty ? uncompletedTasks.first : null;
    final upcomingTasks = uncompletedTasks.isNotEmpty
        ? uncompletedTasks.skip(1).toList()
        : const <_TodayTask>[];

    final headerGreeting =
        '${copy[ConsumerTerm.todayTitle]}, ${_formatTodayDate(DateTime.now(), copy)}';

    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: [
        if (_offlineCachedAt != null) ...[
          _buildOfflineNotice(context),
          const SizedBox(height: ClaraTokens.spaceSm),
        ],

        // 1. Date & Context greeting header (`Hôm nay, [Date]`).
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      headerGreeting,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: Theme.of(context).colorScheme.primary,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.5,
                          ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(
                      copy[ConsumerTerm.todayTitle],
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ],
                ),
              ),
              if (widget.onOpenLifeMap != null)
                TextButton.icon(
                  onPressed: widget.onOpenLifeMap,
                  icon: const Icon(Icons.map_outlined, size: 18),
                  label: Text(copy[ConsumerTerm.todayOpenLifeMap]),
                ),
            ],
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),

        // 2. Next accepted task as dominant HeroObject (title, due time, severity badge, complete action).
        if (nextTask != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _NextTaskHeroObject(
              task: nextTask,
              copy: copy,
              onComplete: () => _completeTask(nextTask),
              onOpen: widget.onOpenLifeMap,
              isCompleting: _completing.contains(nextTask.id),
              offline: _offlineCachedAt != null,
              formattedDue: _formatDue(nextTask.dueAt),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ] else if (isCaughtUp) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _CaughtUpBanner(copy: copy),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ] else if (topAction != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _TopActionBanner(
              action: topAction,
              copy: copy,
              onAction: () {
                if (topAction.kind == 'medication') {
                  widget.onCheckMedicines?.call();
                } else if (topAction.kind == 'visit') {
                  widget.onPrepareVisit?.call();
                } else if (topAction.kind == 'chat' ||
                    topAction.kind == 'review') {
                  widget.onAskHealth?.call();
                } else {
                  widget.onOpenLifeMap?.call();
                }
              },
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ] else if (_tasks.isEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: ClaraEmptyState(
              icon: Icons.task_alt_outlined,
              title: copy[ConsumerTerm.todayEmptyTitle],
              message: copy[ConsumerTerm.todayEmptyDescription],
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ],

        if (_loading && _tasks.isNotEmpty) ...[
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: LinearProgressIndicator(),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
        ],

        // 3. Upcoming accepted tasks timeline.
        if (upcomingTasks.isNotEmpty ||
            (completedTasks.isNotEmpty && !isCaughtUp)) ...[
          _UpcomingTimelineSection(
            tasks: upcomingTasks,
            completedTasks: completedTasks,
            copy: copy,
            onCompleteTask: _completeTask,
            completingIds: _completing,
            offline: _offlineCachedAt != null,
            dueFormatter: _formatDue,
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ],

        // 4. Pending confirmations row.
        if (_pendingConfirmationCount > 0) ...[
          _PendingConfirmationsRow(
            count: _pendingConfirmationCount,
            copy: copy,
            onTap: widget.onOpenLifeMap,
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ],

        // 5. Active LifeMap journey preview.
        if (_episodes.isNotEmpty) ...[
          _ActiveJourneyPreviewSection(
            episodes: _episodes,
            copy: copy,
            onOpenLifeMap: widget.onOpenLifeMap,
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ],

        // 6. Secondary utility actions (`Hỏi CLARA`, `Tủ thuốc`, `Chuẩn bị khám`).
        _SecondaryUtilityActions(
          copy: copy,
          onAskHealth: widget.onAskHealth,
          onCheckMedicines: widget.onCheckMedicines,
          onSaveHealthInfo: widget.onSaveHealthInfo,
          onPrepareVisit: widget.onPrepareVisit,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),

        // 7. Progress / recent authentic source changes.
        _ProgressAndRecentChangesSection(
          recentChanges: recentChanges,
          completedCount: completedTasks.length,
          pendingCount: uncompletedTasks.length,
          episodesCount: _episodes.length,
          pendingConfirmationCount: _pendingConfirmationCount,
          copy: copy,
        ),
      ],
    );
  }

  Widget _buildOfflineNotice(BuildContext context) {
    final now = DateTime.now().toUtc();
    final stale = _offlineValidUntil == null ||
        !now.isBefore(_offlineValidUntil!.toUtc());
    final cachedAt = _offlineCachedAt!.toLocal();
    String two(int value) => value.toString().padLeft(2, '0');
    final timestamp = _copy.locale == 'en'
        ? '${_englishMonth(cachedAt.month)} ${cachedAt.day}, '
            '${cachedAt.year} at ${two(cachedAt.hour)}:${two(cachedAt.minute)}'
        : '${two(cachedAt.hour)}:${two(cachedAt.minute)} '
            '${two(cachedAt.day)}/${two(cachedAt.month)}/${cachedAt.year}';
    return Semantics(
      liveRegion: true,
      label: stale
          ? _copy[ConsumerTerm.todayOfflineStale]
          : _copy.format(
              ConsumerTerm.todayOfflineFresh,
              {'timestamp': timestamp},
            ),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.secondaryContainer,
          borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        ),
        child: Text(
          stale
              ? _copy[ConsumerTerm.todayOfflineStale]
              : _copy.format(
                  ConsumerTerm.todayOfflineFresh,
                  {'timestamp': timestamp},
                ),
        ),
      ),
    );
  }
}

/// Dominant HeroObject for the next accepted task (Spec v5 Section 7.1).
class _NextTaskHeroObject extends StatelessWidget {
  const _NextTaskHeroObject({
    required this.task,
    required this.copy,
    required this.onComplete,
    required this.formattedDue,
    this.onOpen,
    this.isCompleting = false,
    this.offline = false,
  });

  final _TodayTask task;
  final ConsumerTerminology copy;
  final VoidCallback onComplete;
  final VoidCallback? onOpen;
  final bool isCompleting;
  final bool offline;
  final String formattedDue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final isUrgent = task.isUrgent;
    final isAttention = task.isAttention;

    final accentColor = isUrgent
        ? const Color(0xFFDC2626)
        : isAttention
            ? const Color(0xFFD97706)
            : scheme.primary;

    final badgeLabel = _severityBadgeLabel(task.severity, copy);

    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        border: Border.all(
          color: isUrgent
              ? const Color(0xFFDC2626)
              : isAttention
                  ? const Color(0xFFD97706)
                  : const Color(0xFF2A3950),
          width: 2,
        ),
        boxShadow: [
          BoxShadow(
            color: accentColor.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Overline row: Action icon/label, Due time, Severity badge
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaraTokens.spaceSm,
                  vertical: ClaraTokens.spaceXs,
                ),
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isUrgent ? Icons.warning_amber_rounded : Icons.task_alt,
                      color: accentColor,
                      size: 16,
                    ),
                    const SizedBox(width: ClaraTokens.spaceXs),
                    Text(
                      copy[ConsumerTerm.homeNextActionTitle],
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: accentColor,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              ClaraChip(
                label: badgeLabel,
                selected: isUrgent || isAttention,
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceMd),

          // Dominant task title
          Text(
            task.title.isEmpty ? copy[ConsumerTerm.todayUnnamedTask] : task.title,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          if (task.episodeTitle != null && task.episodeTitle!.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              task.episodeTitle!,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
          const SizedBox(height: ClaraTokens.spaceSm),

          // Due date / time
          Row(
            children: [
              Icon(
                Icons.schedule,
                size: 16,
                color: scheme.onSurfaceVariant,
              ),
              const SizedBox(width: ClaraTokens.spaceXs),
              Text(
                formattedDue,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          const Divider(height: 1),
          const SizedBox(height: ClaraTokens.spaceMd),

          // Action row
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              if (onOpen != null) ...[
                ClaraButton.secondary(
                  label: copy[ConsumerTerm.actionOpen],
                  icon: Icons.arrow_forward_rounded,
                  onPressed: onOpen,
                ),
                const SizedBox(width: ClaraTokens.spaceSm),
              ],
              ClaraButton.primary(
                label: copy[ConsumerTerm.actionComplete],
                icon: Icons.check,
                loading: isCompleting,
                onPressed: offline ? null : onComplete,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Upcoming accepted tasks timeline section (Spec v5 Section 7.1).
class _UpcomingTimelineSection extends StatelessWidget {
  const _UpcomingTimelineSection({
    required this.tasks,
    required this.completedTasks,
    required this.copy,
    required this.onCompleteTask,
    required this.completingIds,
    required this.offline,
    required this.dueFormatter,
  });

  final List<_TodayTask> tasks;
  final List<_TodayTask> completedTasks;
  final ConsumerTerminology copy;
  final ValueChanged<_TodayTask> onCompleteTask;
  final Set<String> completingIds;
  final bool offline;
  final String Function(String?) dueFormatter;

  @override
  Widget build(BuildContext context) {
    if (tasks.isEmpty && completedTasks.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: copy[ConsumerTerm.homeScheduleTitle],
            trailing: tasks.isNotEmpty
                ? ClaraChip(
                    label: '${tasks.length} ${copy[ConsumerTerm.todayPending]}',
                    selected: true,
                  )
                : null,
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          ...tasks.map(
            (task) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: _TaskCard(
                task: task,
                copy: copy,
                formattedDue: dueFormatter(task.dueAt),
                isCompleting: completingIds.contains(task.id),
                offline: offline,
                onComplete: () => onCompleteTask(task),
              ),
            ),
          ),
          ...completedTasks.map(
            (task) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: _TaskCard(
                task: task,
                copy: copy,
                formattedDue: dueFormatter(task.dueAt),
                isCompleting: false,
                offline: offline,
                onComplete: null,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A single task card row.
class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.task,
    required this.copy,
    required this.formattedDue,
    required this.isCompleting,
    required this.offline,
    required this.onComplete,
  });

  final _TodayTask task;
  final ConsumerTerminology copy;
  final String formattedDue;
  final bool isCompleting;
  final bool offline;
  final VoidCallback? onComplete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isUrgent = task.isUrgent;
    final isAttention = task.isAttention;

    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        task.title.isEmpty
                            ? copy[ConsumerTerm.todayUnnamedTask]
                            : task.title,
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                          decoration:
                              task.completed ? TextDecoration.lineThrough : null,
                        ),
                      ),
                    ),
                    if (!task.completed && (isUrgent || isAttention))
                      ClaraChip(
                        label: _severityBadgeLabel(task.severity, copy),
                        selected: true,
                      ),
                  ],
                ),
                const SizedBox(height: ClaraTokens.spaceXs),
                Text(
                  formattedDue,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          if (task.completed)
            ClaraChip(label: copy[ConsumerTerm.actionComplete])
          else
            ClaraButton.primary(
              label: copy[ConsumerTerm.actionComplete],
              icon: Icons.check,
              loading: isCompleting,
              onPressed: offline ? null : onComplete,
            ),
        ],
      ),
    );
  }
}

/// Pending confirmations alert row (Spec v5 Section 7.1).
class _PendingConfirmationsRow extends StatelessWidget {
  const _PendingConfirmationsRow({
    required this.count,
    required this.copy,
    this.onTap,
  });

  final int count;
  final ConsumerTerminology copy;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard(
        onTap: onTap,
        semanticLabel: '$count ${copy[ConsumerTerm.todayConfirmation]}',
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(ClaraTokens.spaceSm),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
              ),
              child: const Icon(
                Icons.mark_email_unread_outlined,
                color: Color(0xFFD97706),
                size: 24,
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$count ${copy[ConsumerTerm.todayConfirmation]}',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF92400E),
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    copy[ConsumerTerm.todayStartHereDescription],
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (onTap != null)
              Icon(
                Icons.chevron_right_rounded,
                color: theme.colorScheme.onSurfaceVariant,
              ),
          ],
        ),
      ),
    );
  }
}

/// Active LifeMap journey preview section (Spec v5 Section 7.1).
class _ActiveJourneyPreviewSection extends StatelessWidget {
  const _ActiveJourneyPreviewSection({
    required this.episodes,
    required this.copy,
    this.onOpenLifeMap,
  });

  final List<_TodayEpisode> episodes;
  final ConsumerTerminology copy;
  final VoidCallback? onOpenLifeMap;

  @override
  Widget build(BuildContext context) {
    if (episodes.isEmpty) return const SizedBox.shrink();

    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: copy[ConsumerTerm.lifeMapCareJourneys],
            trailing: onOpenLifeMap != null
                ? TextButton.icon(
                    onPressed: onOpenLifeMap,
                    icon: const Icon(Icons.map_outlined, size: 16),
                    label: Text(copy[ConsumerTerm.todayOpenLifeMap]),
                  )
                : null,
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          ...episodes.map(
            (episode) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: ClaraCard(
                onTap: onOpenLifeMap,
                semanticLabel: episode.title,
                child: Row(
                  children: [
                    Icon(
                      Icons.route_outlined,
                      color: theme.colorScheme.primary,
                      size: 24,
                    ),
                    const SizedBox(width: ClaraTokens.spaceMd),
                    Expanded(
                      child: Text(
                        episode.title,
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Icon(
                      Icons.chevron_right_rounded,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Secondary utility actions: Ask CLARA + Start Here task shortcuts (Spec v5 Section 7.1).
class _SecondaryUtilityActions extends StatelessWidget {
  const _SecondaryUtilityActions({
    required this.copy,
    this.onAskHealth,
    this.onCheckMedicines,
    this.onSaveHealthInfo,
    this.onPrepareVisit,
  });

  final ConsumerTerminology copy;
  final VoidCallback? onAskHealth;
  final VoidCallback? onCheckMedicines;
  final VoidCallback? onSaveHealthInfo;
  final VoidCallback? onPrepareVisit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Ask CLARA entry card
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: _AskClaraCard(
            copy: copy,
            onText: onAskHealth,
            onCamera: onCheckMedicines,
            onVoice: onAskHealth,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceLg),

        // Task-first entry points (Start Here)
        _buildStartHere(context),
      ],
    );
  }

  Widget _buildStartHere(BuildContext context) {
    final actions = <_TodayStartAction>[
      _TodayStartAction(
        icon: Icons.forum_outlined,
        title: copy[ConsumerTerm.todayAskHealthTitle],
        description: copy[ConsumerTerm.todayAskHealthDescription],
        onTap: onAskHealth,
      ),
      _TodayStartAction(
        icon: Icons.medication_outlined,
        title: copy[ConsumerTerm.todayCheckMedicineTitle],
        description: copy[ConsumerTerm.todayCheckMedicineDescription],
        onTap: onCheckMedicines,
      ),
      _TodayStartAction(
        icon: Icons.folder_shared_outlined,
        title: copy[ConsumerTerm.todaySaveHealthInfoTitle],
        description: copy[ConsumerTerm.todaySaveHealthInfoDescription],
        onTap: onSaveHealthInfo,
      ),
      _TodayStartAction(
        icon: Icons.event_note_outlined,
        title: copy[ConsumerTerm.todayPrepareVisitTitle],
        description: copy[ConsumerTerm.todayPrepareVisitDescription],
        onTap: onPrepareVisit,
      ),
    ].where((action) => action.onTap != null).toList(growable: false);

    if (actions.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(title: copy[ConsumerTerm.todayStartHereTitle]),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            copy[ConsumerTerm.todayStartHereDescription],
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          ...actions.map(
            (action) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: _TodayStartActionCard(action: action),
            ),
          ),
        ],
      ),
    );
  }
}

/// Progress / non-zero statistics & recent authentic source changes (Spec v5 Section 7.1).
class _ProgressAndRecentChangesSection extends StatelessWidget {
  const _ProgressAndRecentChangesSection({
    required this.recentChanges,
    required this.completedCount,
    required this.pendingCount,
    required this.episodesCount,
    required this.pendingConfirmationCount,
    required this.copy,
  });

  final List<HomeRecentChange> recentChanges;
  final int completedCount;
  final int pendingCount;
  final int episodesCount;
  final int pendingConfirmationCount;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Suppress 0-count stat cards!
    final statCards = <Widget>[
      if (completedCount > 0)
        _StatCard(
          icon: Icons.check_circle_outline,
          label: copy[ConsumerTerm.actionComplete],
          value: completedCount,
        ),
      if (pendingCount > 0)
        _StatCard(
          icon: Icons.pending_actions_outlined,
          label: copy[ConsumerTerm.todayPending],
          value: pendingCount,
        ),
      if (episodesCount > 0)
        _StatCard(
          icon: Icons.route_outlined,
          label: copy[ConsumerTerm.todayEpisodes],
          value: episodesCount,
        ),
      if (pendingConfirmationCount > 0)
        _StatCard(
          icon: Icons.mark_email_unread_outlined,
          label: copy[ConsumerTerm.todayConfirmation],
          value: pendingConfirmationCount,
        ),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (statCards.isNotEmpty) ...[
            Wrap(
              spacing: ClaraTokens.spaceMd,
              runSpacing: ClaraTokens.spaceMd,
              children: statCards,
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
          ],
          SectionHeader(title: copy[ConsumerTerm.homeRecentChangesTitle]),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            copy[ConsumerTerm.homeRecentChangesRealSourceNotice],
            style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          if (recentChanges.isEmpty)
            ClaraEmptyState(
              icon: Icons.history,
              title: copy[ConsumerTerm.homeRecentChangesEmpty],
              message: copy[ConsumerTerm.homeScreenNoRecentDescription],
            )
          else
            ...recentChanges.map(
              (change) => Padding(
                padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
                child: ClaraCard.static_(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.description_outlined,
                        color: theme.colorScheme.primary,
                        size: 22,
                      ),
                      const SizedBox(width: ClaraTokens.spaceMd),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              change.title,
                              style: theme.textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                            ),
                            if (change.summary != null)
                              Text(
                                change.summary!,
                                style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                              ),
                            if (change.source != null)
                              Padding(
                                padding: const EdgeInsets.only(top: ClaraTokens.spaceXs),
                                child: ClaraChip(
                                  label: change.source!,
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _TopActionBanner extends StatelessWidget {
  const _TopActionBanner({
    required this.action,
    required this.copy,
    required this.onAction,
  });

  final HomeNextAction action;
  final ConsumerTerminology copy;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final isUrgent = action.isUrgent;
    final isAttention = action.isAttention;

    final accentColor = isUrgent
        ? const Color(0xFFDC2626)
        : isAttention
            ? const Color(0xFFD97706)
            : scheme.primary;

    final badgeLabel = _severityBadgeLabel(action.severity, copy);

    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        border: const Border(
          top: BorderSide(color: Color(0xFF2A3950), width: 2),
          left: BorderSide(color: Color(0x33414751)),
          right: BorderSide(color: Color(0x33414751)),
          bottom: BorderSide(color: Color(0x33414751)),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isUrgent ? Icons.warning_amber_rounded : Icons.task_alt,
                color: accentColor,
                size: 22,
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Text(
                  action.title,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              ClaraChip(
                label: badgeLabel,
                selected: isUrgent || isAttention,
              ),
            ],
          ),
          if (action.description != null) ...[
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              action.description!,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          const SizedBox(height: ClaraTokens.spaceMd),
          Align(
            alignment: Alignment.centerRight,
            child: ClaraButton.primary(
              label: action.actionLabel ?? copy[ConsumerTerm.actionOpen],
              icon: Icons.arrow_forward_rounded,
              onPressed: onAction,
            ),
          ),
        ],
      ),
    );
  }
}

class _AskClaraCard extends StatelessWidget {
  const _AskClaraCard({
    required this.copy,
    this.onText,
    this.onCamera,
    this.onVoice,
  });

  final ConsumerTerminology copy;
  final VoidCallback? onText;
  final VoidCallback? onCamera;
  final VoidCallback? onVoice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onText,
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceXs),
              child: Row(
                children: [
                  Icon(Icons.auto_awesome, color: scheme.primary, size: 24),
                  const SizedBox(width: ClaraTokens.spaceMd),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          copy[ConsumerTerm.actionAskClara],
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          copy[ConsumerTerm.homeAskPlaceholder],
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          const Divider(height: 1),
          const SizedBox(height: ClaraTokens.spaceSm),
          Row(
            children: [
              Expanded(
                child: _AskActionPill(
                  icon: Icons.chat_bubble_outline,
                  label: copy[ConsumerTerm.homeAskText],
                  onTap: onText,
                ),
              ),
              Expanded(
                child: _AskActionPill(
                  icon: Icons.camera_alt_outlined,
                  label: copy[ConsumerTerm.homeAskCamera],
                  onTap: onCamera,
                ),
              ),
              Expanded(
                child: _AskActionPill(
                  icon: Icons.mic_none_outlined,
                  label: copy[ConsumerTerm.homeAskVoice],
                  onTap: onVoice,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AskActionPill extends StatelessWidget {
  const _AskActionPill({
    required this.icon,
    required this.label,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Material(
      type: MaterialType.transparency,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: ClaraTokens.spaceXs,
            vertical: ClaraTokens.spaceSm,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 18, color: scheme.primary),
              const SizedBox(width: ClaraTokens.spaceXs),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: scheme.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CaughtUpBanner extends StatelessWidget {
  const _CaughtUpBanner({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDF4),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        border: Border.all(color: const Color(0xFF86EFAC)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.task_alt_rounded,
            color: Color(0xFF16A34A),
            size: 24,
          ),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  copy[ConsumerTerm.homeCaughtUpTitle],
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: const Color(0xFF166534),
                  ),
                ),
                Text(
                  copy[ConsumerTerm.homeCaughtUpDescription],
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TodayStartAction {
  const _TodayStartAction({
    required this.icon,
    required this.title,
    required this.description,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String description;
  final VoidCallback? onTap;
}

class _TodayStartActionCard extends StatelessWidget {
  const _TodayStartActionCard({required this.action});

  final _TodayStartAction action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ClaraCard(
      onTap: action.onTap!,
      semanticLabel: '${action.title}. ${action.description}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(action.icon, color: theme.colorScheme.primary, size: 28),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  action.title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: ClaraTokens.spaceXs),
                Text(
                  action.description,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Icon(
            Icons.chevron_right_rounded,
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 100, maxWidth: 200),
      child: ClaraCard.static_(
        semanticLabel: '$label: $value',
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 22, color: scheme.primary),
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              '$value',
              style: theme.textTheme.headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
