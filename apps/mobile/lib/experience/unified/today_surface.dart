// Today agenda surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// Consumes the /api/v2/home read model:
//   * Priority 1: Top next-action card (severity-based).
//   * Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances.
//   * Priority 3: Today's schedule (medications, visits, care tasks).
//   * Priority 4: Recent changes (real source records only; no fake activity).
//   * Priority 5: Calm caught-up state when all tasks are complete.
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

/// A single accepted task rendered on the Today agenda.
class _TodayTask {
  const _TodayTask({required this.id, required this.title, this.dueAt, this.completed = false});

  factory _TodayTask.fromJson(Map<String, dynamic> json) => _TodayTask(
        id: _str(json['id']),
        title: _str(json['title'] ?? json['name']),
        dueAt: json['due_at'] == null ? null : _str(json['due_at']),
        completed: json['status'] == 'completed' || json['completed'] == true,
      );

  final String id;
  final String title;
  final String? dueAt;
  final bool completed;
}

/// A single open care episode summarized on the Today agenda.
class _TodayEpisode {
  const _TodayEpisode({required this.id, required this.title});

  factory _TodayEpisode.fromJson(Map<String, dynamic> json) => _TodayEpisode(
        id: _str(json['id']),
        title: _str(json['title']),
      );

  final String id;
  final String title;
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
    final isCaughtUp = _tasks.isNotEmpty && _tasks.every((t) => t.completed);

    final children = <Widget>[
      if (_offlineCachedAt != null) _buildOfflineNotice(context),

      // Header row
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Row(
          children: [
            Expanded(
              child: SectionHeader(
                title: copy[ConsumerTerm.todayTitle],
                emphasize: true,
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
      const SizedBox(height: ClaraTokens.spaceSm),

      // Priority 1: Top next-action card (severity-based)
      if (topAction != null) ...[
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
              } else if (topAction.kind == 'chat' || topAction.kind == 'review') {
                widget.onAskHealth?.call();
              } else {
                widget.onOpenLifeMap?.call();
              }
            },
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
      ],

      // Stats
      _buildStats(context),
      const SizedBox(height: ClaraTokens.spaceLg),

      // Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: _AskClaraCard(
          copy: copy,
          onText: widget.onAskHealth,
          onCamera: widget.onCheckMedicines,
          onVoice: widget.onAskHealth,
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceLg),

      // Task-first entry points (Start Here)
      _buildStartHere(context),
      const SizedBox(height: ClaraTokens.spaceLg),

      // Priority 3: Today's schedule (Medications, Visits, Care tasks)
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: SectionHeader(
          title: copy[ConsumerTerm.todayAccepted],
          trailing: _tasks.where((t) => !t.completed).isNotEmpty
              ? ClaraChip(
                  label:
                      '${_tasks.where((t) => !t.completed).length} ${copy[ConsumerTerm.todayPending]}',
                  selected: true,
                )
              : null,
        ),
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
    ];

    // Priority 5: Calm caught-up state
    if (isCaughtUp) {
      children.add(
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: _CaughtUpBanner(copy: copy),
        ),
      );
      children.add(const SizedBox(height: ClaraTokens.spaceMd));
    }

    if (_tasks.isEmpty) {
      children.add(
        ClaraEmptyState(
          icon: Icons.task_alt_outlined,
          title: copy[ConsumerTerm.todayEmptyTitle],
          message: copy[ConsumerTerm.todayEmptyDescription],
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
        _tasks.map(
          (task) => Padding(
            padding: const EdgeInsets.fromLTRB(
              ClaraTokens.spaceMd,
              0,
              ClaraTokens.spaceMd,
              ClaraTokens.spaceMd,
            ),
            child: _buildTaskCard(context, task),
          ),
        ),
      );
    }

    // Priority 4: Recent changes (real source records only)
    children.add(const SizedBox(height: ClaraTokens.spaceLg));
    children.add(
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionHeader(title: copy[ConsumerTerm.homeRecentChangesTitle]),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              copy[ConsumerTerm.homeRecentChangesRealSourceNotice],
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
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
                          color: Theme.of(context).colorScheme.primary,
                          size: 22,
                        ),
                        const SizedBox(width: ClaraTokens.spaceMd),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                change.title,
                                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                              ),
                              if (change.summary != null)
                                Text(
                                  change.summary!,
                                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                        color: Theme.of(context).colorScheme.onSurfaceVariant,
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
      ),
    );

    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: children,
    );
  }

  Widget _buildStartHere(BuildContext context) {
    final actions = <_TodayStartAction>[
      _TodayStartAction(
        icon: Icons.forum_outlined,
        title: _copy[ConsumerTerm.todayAskHealthTitle],
        description: _copy[ConsumerTerm.todayAskHealthDescription],
        onTap: widget.onAskHealth,
      ),
      _TodayStartAction(
        icon: Icons.medication_outlined,
        title: _copy[ConsumerTerm.todayCheckMedicineTitle],
        description: _copy[ConsumerTerm.todayCheckMedicineDescription],
        onTap: widget.onCheckMedicines,
      ),
      _TodayStartAction(
        icon: Icons.folder_shared_outlined,
        title: _copy[ConsumerTerm.todaySaveHealthInfoTitle],
        description: _copy[ConsumerTerm.todaySaveHealthInfoDescription],
        onTap: widget.onSaveHealthInfo,
      ),
      _TodayStartAction(
        icon: Icons.event_note_outlined,
        title: _copy[ConsumerTerm.todayPrepareVisitTitle],
        description: _copy[ConsumerTerm.todayPrepareVisitDescription],
        onTap: widget.onPrepareVisit,
      ),
    ].where((action) => action.onTap != null).toList(growable: false);

    if (actions.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(title: _copy[ConsumerTerm.todayStartHereTitle]),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            _copy[ConsumerTerm.todayStartHereDescription],
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
        margin: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          0,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
        ),
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

  Widget _buildStats(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: Wrap(
        spacing: ClaraTokens.spaceMd,
        runSpacing: ClaraTokens.spaceMd,
        children: [
          _StatCard(
            icon: Icons.pending_actions_outlined,
            label: _copy[ConsumerTerm.todayPending],
            value: _tasks.where((t) => !t.completed).length,
          ),
          _StatCard(
            icon: Icons.route_outlined,
            label: _copy[ConsumerTerm.todayEpisodes],
            value: _episodes.length,
          ),
          _StatCard(
            icon: Icons.mark_email_unread_outlined,
            label: _copy[ConsumerTerm.todayConfirmation],
            value: _pendingConfirmationCount,
          ),
        ],
      ),
    );
  }

  Widget _buildTaskCard(BuildContext context, _TodayTask task) {
    final theme = Theme.of(context);
    final busy = _completing.contains(task.id);
    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task.title.isEmpty
                      ? _copy[ConsumerTerm.todayUnnamedTask]
                      : task.title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    decoration:
                        task.completed ? TextDecoration.lineThrough : null,
                  ),
                ),
                const SizedBox(height: ClaraTokens.spaceXs),
                Text(
                  _formatDue(task.dueAt),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          if (task.completed)
            const ClaraChip(label: 'Đã xong')
          else
            ClaraButton.primary(
              label: _copy[ConsumerTerm.actionComplete],
              icon: Icons.check,
              loading: busy,
              onPressed:
                  _offlineCachedAt == null ? () => _completeTask(task) : null,
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

    final badgeLabel = isUrgent
        ? copy[ConsumerTerm.homeSeverityUrgent]
        : isAttention
            ? copy[ConsumerTerm.homeSeverityAttention]
            : copy[ConsumerTerm.homeSeverityNormal];

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
