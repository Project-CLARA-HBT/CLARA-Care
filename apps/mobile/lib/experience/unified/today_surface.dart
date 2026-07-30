// Today agenda surface for the CLARA_Mobile unified experience
// (clara-mobile-unified).
//
// `TodaySurface` is the daily home for LifeMap: it shows the tasks the user has
// already ACCEPTED into their day, the open care journeys, and the count of
// items awaiting confirmation. Framing is deliberately non-clinical — these are
// "việc bạn đã chấp nhận" (things you accepted), never medical advice or a
// diagnosis (CLARA is a clinical assistant, not a doctor).
//
// It reads its agenda from `ApiClient.getLifeMapToday`, which returns 409 when
// the user has no PHR profile yet; that case routes to onboarding via
// [TodaySurface.onNeedsOnboarding] and renders a gentle prompt rather than an
// error. Loading uses skeletons, failures reuse `ErrorRetryView`, and an empty
// agenda uses `ClaraEmptyState`. Product copy comes from the versioned,
// Vietnamese-first terminology contract and remains PII-free.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/lifemap_read_cache.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

String _str(Object? value) => value == null ? '' : value.toString();

/// A single accepted task rendered on the Today agenda.
class _TodayTask {
  const _TodayTask({required this.id, required this.title, this.dueAt});

  factory _TodayTask.fromJson(Map<String, dynamic> json) => _TodayTask(
        id: _str(json['id']),
        title: _str(json['title']),
        dueAt: json['due_at'] == null ? null : _str(json['due_at']),
      );

  final String id;
  final String title;
  final String? dueAt;
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
  final LifeMapReadCache? readCache;

  /// Optional app-level language state. Omit only for legacy/direct embedding;
  /// it then resolves Vietnamese through [ConsumerTerminology]'s fallback.
  final LanguageController? languageController;

  @override
  State<TodaySurface> createState() => _TodaySurfaceState();
}

class _TodaySurfaceState extends State<TodaySurface> {
  bool _loading = true;
  String? _error;

  /// True when the load failed with 409 (no PHR profile yet).
  bool _needsOnboarding = false;

  List<_TodayTask> _tasks = const [];
  List<_TodayEpisode> _episodes = const [];
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
      final data = await widget.apiClient.getLifeMapToday(accessToken: token);
      final tasks = <_TodayTask>[];
      final rawTasks = data['tasks'];
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
        _tasks = tasks;
        _episodes = episodes;
        _pendingConfirmationCount =
            pending is int ? pending : int.tryParse(_str(pending)) ?? 0;
        _offlineCachedAt = null;
        _offlineValidUntil = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode == 409) {
        // No PHR profile yet — route to onboarding and show a gentle prompt.
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
    final tasks = (data['tasks'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => _TodayTask.fromJson(item.cast<String, dynamic>()))
        .toList();
    final episodes = (data['episodes'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => _TodayEpisode.fromJson(item.cast<String, dynamic>()))
        .toList();
    setState(() {
      _tasks = tasks;
      _episodes = episodes;
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

  /// Formats an ISO due date as `dd/MM/yyyy`, or a friendly fallback when the
  /// task has no concrete deadline.
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
    final children = <Widget>[
      if (_offlineCachedAt != null) _buildOfflineNotice(context),
      Row(
        children: [
          Expanded(
            child: SectionHeader(
              title: _copy[ConsumerTerm.todayTitle],
              emphasize: true,
            ),
          ),
          if (widget.onOpenLifeMap != null)
            TextButton.icon(
              onPressed: widget.onOpenLifeMap,
              icon: const Icon(Icons.map_outlined, size: 18),
              label: Text(_copy[ConsumerTerm.todayOpenLifeMap]),
            ),
        ],
      ),
      const SizedBox(height: ClaraTokens.spaceSm),
      _buildStats(context),
      const SizedBox(height: ClaraTokens.spaceLg),
      SectionHeader(title: _copy[ConsumerTerm.todayAccepted]),
    ];

    if (_tasks.isEmpty) {
      children.add(
        ClaraEmptyState(
          icon: Icons.task_alt_outlined,
          title: _copy[ConsumerTerm.todayEmptyTitle],
          message: _copy[ConsumerTerm.todayEmptyDescription],
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

    return ListView(
      padding: const EdgeInsets.only(
        top: ClaraTokens.spaceMd,
        bottom: ClaraTokens.spaceXl,
      ),
      children: children,
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
            value: _tasks.length,
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
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
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

/// A compact summary statistic card used in the Today header.
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
