import 'dart:async';

import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../core/api_client.dart';
import '../core/connectivity_service.dart';
import '../core/lifemap_client_contract.dart';
import '../core/lifemap_timeline_cache.dart';
import '../core/lifemap_timeline_models.dart';
import '../core/session_store.dart';
import '../experience/language_controller.dart';
import '../experience/states/empty_state.dart';
import '../experience/states/skeleton.dart';
import '../theme/components/clara_button.dart';
import '../theme/components/clara_card.dart';
import '../theme/components/clara_chip.dart';
import '../theme/tokens.dart';
import '../theme/web_palette.dart';
import 'error_retry_view.dart';

/// Responsive longitudinal health timeline widget for CLARA_Mobile.
///
/// Implements Phase PH12 (LifeMap longitudinal intelligence):
/// - Responsive visual design adapting seamlessly between Phone (<600dp) and
///   Tablet (>=600dp).
/// - Bitemporal view switching: Valid Time (\tau_v, occurred_at) vs
///   Transaction Time (\tau_k, recorded_at).
/// - Vietnamese-first localization with English fallback.
/// - Minimum interactive touch target dimension >= 48dp on all controls (A11y).
/// - Offline cached indicator banner with secure storage persistence via
///   [LifeMapTimelineReadCache].
/// - Event revision history inspection modal.
class LifeMapTimelineWidget extends StatefulWidget {
  const LifeMapTimelineWidget({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    this.languageController,
    this.connectivityService,
    this.readCache,
    this.initialPerspective = LifeMapTimelinePerspective.validTime,
    this.initialEvents,
    this.episodeId,
    this.onCorrectEvent,
    this.onDisputeEvent,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final LanguageController? languageController;
  final ConnectivityService? connectivityService;
  final LifeMapTimelineReadCache? readCache;
  final LifeMapTimelinePerspective initialPerspective;
  final List<LifeMapTimelineEvent>? initialEvents;
  final String? episodeId;
  final Future<void> Function(LifeMapTimelineEvent event)? onCorrectEvent;
  final Future<void> Function(LifeMapTimelineEvent event)? onDisputeEvent;

  @override
  State<LifeMapTimelineWidget> createState() => _LifeMapTimelineWidgetState();
}

class _LifeMapTimelineWidgetState extends State<LifeMapTimelineWidget> {
  late LifeMapTimelinePerspective _perspective = widget.initialPerspective;
  LifeMapPeriodFilter _periodFilter = LifeMapPeriodFilter.all;
  LifeMapEventTypeFilter _typeFilter = LifeMapEventTypeFilter.all;

  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  bool _loading = false;
  String? _error;
  List<LifeMapTimelineEvent> _events = const [];

  bool _isOffline = false;
  DateTime? _cachedAt;
  late final LifeMapTimelineReadCache _cache;
  late final ConnectivityService _connectivity;
  StreamSubscription<bool>? _connectivitySub;

  String get _locale => widget.languageController?.languageCode ?? 'vi';

  @override
  void initState() {
    super.initState();
    _cache = widget.readCache ??
        LifeMapTimelineReadCache(
          storage: widget.sessionStore.storage,
          userId: widget.sessionStore.userId ?? widget.sessionStore.email,
        );
    _connectivity = widget.connectivityService ?? DefaultConnectivityService();
    _isOffline = !_connectivity.currentValue;

    _connectivitySub = _connectivity.isOnline.listen((online) {
      if (mounted) {
        setState(() => _isOffline = !online);
      }
    });

    if (widget.initialEvents != null) {
      _events = widget.initialEvents!;
    } else {
      _loadTimeline();
    }

    _searchController.addListener(() {
      final text = _searchController.text.trim();
      if (text != _searchQuery) {
        setState(() => _searchQuery = text);
      }
    });
  }

  @override
  void dispose() {
    _connectivitySub?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadTimeline() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final token = widget.sessionStore.accessToken;
    final now = DateTime.now().toUtc();

    // 1. Try reading from cache first for fast or offline render
    final cached = await _cache.read(now: now);
    if (cached != null && mounted) {
      setState(() {
        _events = cached.events;
        _cachedAt = cached.cachedAt;
      });
    }

    // 2. If unauthenticated or no token, display cached or error
    if (token == null || token.isEmpty) {
      if (mounted) {
        setState(() {
          _loading = false;
          if (_events.isEmpty) {
            _error = _locale.startsWith('en')
                ? 'Authentication required.'
                : 'Cần đăng nhập để tải dòng thời gian.';
          } else {
            _isOffline = true;
          }
        });
      }
      return;
    }

    // 3. Network fetch
    try {
      final response = await widget.apiClient.getLifeMapTimeline(
        accessToken: token,
        episodeId: widget.episodeId,
      );

      final rawItems = response['items'];
      final fetched = <LifeMapTimelineEvent>[];
      if (rawItems is List) {
        for (final item in rawItems) {
          if (item is Map) {
            fetched.add(LifeMapTimelineEvent.fromJson(item.cast<String, dynamic>()));
          }
        }
      }

      await _cache.save(fetched, now: now);

      if (mounted) {
        setState(() {
          _events = fetched;
          _isOffline = false;
          _cachedAt = null;
          _loading = false;
        });
      }
    } catch (e) {
      // On network failure, fall back to cached data if available
      if (mounted) {
        setState(() {
          _loading = false;
          if (_events.isNotEmpty) {
            _isOffline = true;
          } else {
            _error = _locale.startsWith('en')
                ? 'Unable to load timeline. Please check your network connection.'
                : 'Không thể tải dòng thời gian. Vui lòng kiểm tra kết nối mạng.';
          }
        });
      }
    }
  }

  List<LifeMapTimelineEvent> get _filteredAndSortedEvents {
    final now = DateTime.now().toUtc();

    var list = _events.where((event) {
      // 1. Perspective date matching period filter
      final date = _perspective == LifeMapTimelinePerspective.validTime
          ? event.occurredAt
          : event.recordedAt;
      if (!_periodFilter.matches(date, now)) return false;

      // 2. Type filter
      if (!_typeFilter.matches(event.eventType)) return false;

      // 3. Search query
      if (_searchQuery.isNotEmpty) {
        final query = _searchQuery.toLowerCase();
        final matchesTitle = event.title.toLowerCase().contains(query);
        final matchesSummary = event.summary?.toLowerCase().contains(query) ?? false;
        final matchesType = event.eventType.toLowerCase().contains(query);
        if (!matchesTitle && !matchesSummary && !matchesType) return false;
      }

      return true;
    }).toList();

    // Sort according to active perspective
    if (_perspective == LifeMapTimelinePerspective.validTime) {
      list.sort((a, b) => b.occurredAt.compareTo(a.occurredAt));
    } else {
      list.sort((a, b) => b.recordedAt.compareTo(a.recordedAt));
    }

    return list;
  }

  String _formatDateTime(DateTime dt) {
    final d = dt.toLocal();
    final day = d.day.toString().padLeft(2, '0');
    final month = d.month.toString().padLeft(2, '0');
    final year = d.year.toString();
    final hour = d.hour.toString().padLeft(2, '0');
    final minute = d.minute.toString().padLeft(2, '0');
    return '$day/$month/$year $hour:$minute';
  }

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController != null) {
      return AnimatedBuilder(
        animation: languageController,
        builder: (context, _) => _buildScaffold(context),
      );
    }
    return _buildScaffold(context);
  }

  Widget _buildScaffold(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isTablet = constraints.maxWidth >= 600.0;
        return RefreshIndicator(
          onRefresh: _loadTimeline,
          child: isTablet ? _buildTabletLayout(context) : _buildPhoneLayout(context),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Phone Layout (< 600dp width)
  // ---------------------------------------------------------------------------
  Widget _buildPhoneLayout(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceMd,
      ),
      children: [
        _buildHeader(context),
        const SizedBox(height: ClaraTokens.spaceMd),
        _buildOfflineNotice(context),
        _buildPerspectiveSelector(context),
        const SizedBox(height: ClaraTokens.spaceMd),
        _buildSearchField(context),
        const SizedBox(height: ClaraTokens.spaceSm),
        _buildPeriodFilterChips(context),
        const SizedBox(height: ClaraTokens.spaceSm),
        _buildEventTypeFilterChips(context),
        const SizedBox(height: ClaraTokens.spaceLg),
        _buildTimelineContent(context),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Tablet Layout (>= 600dp width)
  // ---------------------------------------------------------------------------
  Widget _buildTabletLayout(BuildContext context) {
    final theme = Theme.of(context);

    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000),
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceLg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(context),
              const SizedBox(height: ClaraTokens.spaceMd),
              _buildOfflineNotice(context),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Left Column: Filter Sidebar
                    SizedBox(
                      width: 320,
                      child: ClaraCard.static_(
                        child: ListView(
                          shrinkWrap: true,
                          children: [
                            Text(
                              _locale.startsWith('en')
                                  ? 'Timeline Controls'
                                  : 'Điều khiển dòng thời gian',
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: ClaraTokens.spaceMd),
                            _buildPerspectiveSelector(context),
                            const Divider(height: ClaraTokens.spaceLg),
                            _buildSearchField(context),
                            const SizedBox(height: ClaraTokens.spaceMd),
                            Text(
                              LifeMapTimelineStrings.periodFilterLabel(_locale),
                              style: theme.textTheme.labelMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: ClaraTokens.spaceXs),
                            _buildPeriodFilterChips(context, wrapMode: true),
                            const Divider(height: ClaraTokens.spaceLg),
                            Text(
                              LifeMapTimelineStrings.categoryFilterLabel(_locale),
                              style: theme.textTheme.labelMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: ClaraTokens.spaceXs),
                            _buildEventTypeFilterChips(context, wrapMode: true),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: ClaraTokens.spaceLg),
                    // Right Column: Timeline Stream
                    Expanded(
                      child: ListView(
                        children: [
                          _buildTimelineContent(context),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Header Section
  // ---------------------------------------------------------------------------
  Widget _buildHeader(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.timeline_outlined,
              size: 28,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Text(
                LifeMapTimelineStrings.timelineTitle(_locale),
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            if (_isOffline)
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaraTokens.spaceSm,
                  vertical: ClaraTokens.spaceXs,
                ),
                decoration: BoxDecoration(
                  color: theme.colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                ),
                child: Text(
                  _locale.startsWith('en') ? 'OFFLINE' : 'NGOẠI TUYẾN',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          LifeMapTimelineStrings.timelineSubtitle(_locale),
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Offline Notice Banner
  // ---------------------------------------------------------------------------
  Widget _buildOfflineNotice(BuildContext context) {
    if (!_isOffline && _cachedAt == null) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final status = theme.extension<ClaraStatusColors>();
    final cachedTime = _cachedAt != null ? _formatDateTime(_cachedAt!) : 'gần đây';

    return Padding(
      padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
      child: Semantics(
        liveRegion: true,
        child: Container(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          decoration: BoxDecoration(
            color: status?.warning.withOpacity(0.12) ?? theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            border: Border.all(
              color: status?.warning ?? theme.colorScheme.outlineVariant,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.cloud_off_outlined,
                color: status?.onWarning ?? theme.colorScheme.primary,
                size: 22,
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      LifeMapTimelineStrings.offlineBannerTitle(_locale),
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: status?.onWarning ?? theme.colorScheme.onSurface,
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(
                      LifeMapTimelineStrings.offlineBannerDescription(_locale, cachedTime),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Bitemporal Perspective Selector (\tau_v vs \tau_k)
  // ---------------------------------------------------------------------------
  Widget _buildPerspectiveSelector(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          LifeMapTimelineStrings.perspectiveLabel(_locale),
          style: theme.textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        SegmentedButton<LifeMapTimelinePerspective>(
          segments: [
            ButtonSegment(
              value: LifeMapTimelinePerspective.validTime,
              label: Text(
                LifeMapTimelinePerspective.validTime.label(_locale),
                textAlign: TextAlign.center,
              ),
              icon: const Icon(Icons.schedule_outlined, size: 18),
            ),
            ButtonSegment(
              value: LifeMapTimelinePerspective.systemTime,
              label: Text(
                LifeMapTimelinePerspective.systemTime.label(_locale),
                textAlign: TextAlign.center,
              ),
              icon: const Icon(Icons.sync_outlined, size: 18),
            ),
          ],
          selected: {_perspective},
          onSelectionChanged: (selected) {
            if (selected.isNotEmpty) {
              setState(() => _perspective = selected.first);
            }
          },
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          _perspective.description(_locale),
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
            fontStyle: FontStyle.italic,
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Search Bar
  // ---------------------------------------------------------------------------
  Widget _buildSearchField(BuildContext context) {
    return TextField(
      controller: _searchController,
      decoration: InputDecoration(
        hintText: LifeMapTimelineStrings.searchPlaceholder(_locale),
        prefixIcon: const Icon(Icons.search, size: 20),
        suffixIcon: _searchQuery.isNotEmpty
            ? MinTapTarget(
                child: IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    setState(() => _searchQuery = '');
                  },
                ),
              )
            : null,
        filled: true,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Period Filter Chips
  // ---------------------------------------------------------------------------
  Widget _buildPeriodFilterChips(BuildContext context, {bool wrapMode = false}) {
    final chips = LifeMapPeriodFilter.values.map((filter) {
      final isSelected = _periodFilter == filter;
      return MinTapTarget(
        child: ClaraChip(
          label: filter.label(_locale),
          selected: isSelected,
          onTap: () => setState(() => _periodFilter = filter),
          selectedSemanticsValue: isSelected ? 'Đang chọn' : null,
        ),
      );
    }).toList();

    if (wrapMode) {
      return Wrap(
        spacing: ClaraTokens.spaceSm,
        runSpacing: ClaraTokens.spaceSm,
        children: chips,
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: chips
            .map((c) => Padding(
                  padding: const EdgeInsets.only(right: ClaraTokens.spaceSm),
                  child: c,
                ))
            .toList(),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Event Type Filter Chips
  // ---------------------------------------------------------------------------
  Widget _buildEventTypeFilterChips(BuildContext context, {bool wrapMode = false}) {
    final chips = LifeMapEventTypeFilter.values.map((filter) {
      final isSelected = _typeFilter == filter;
      return MinTapTarget(
        child: ClaraChip(
          label: filter.label(_locale),
          icon: _getFilterIcon(filter),
          selected: isSelected,
          onTap: () => setState(() => _typeFilter = filter),
          selectedSemanticsValue: isSelected ? 'Đang chọn' : null,
        ),
      );
    }).toList();

    if (wrapMode) {
      return Wrap(
        spacing: ClaraTokens.spaceSm,
        runSpacing: ClaraTokens.spaceSm,
        children: chips,
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: chips
            .map((c) => Padding(
                  padding: const EdgeInsets.only(right: ClaraTokens.spaceSm),
                  child: c,
                ))
            .toList(),
      ),
    );
  }

  IconData? _getFilterIcon(LifeMapEventTypeFilter filter) {
    switch (filter) {
      case LifeMapEventTypeFilter.medication:
        return Icons.medication_outlined;
      case LifeMapEventTypeFilter.symptom:
        return Icons.healing_outlined;
      case LifeMapEventTypeFilter.visit:
        return Icons.calendar_today_outlined;
      case LifeMapEventTypeFilter.result:
        return Icons.science_outlined;
      case LifeMapEventTypeFilter.measurement:
        return Icons.monitor_heart_outlined;
      case LifeMapEventTypeFilter.document:
        return Icons.description_outlined;
      case LifeMapEventTypeFilter.all:
        return null;
    }
  }

  // ---------------------------------------------------------------------------
  // Timeline Content (Loading, Error, Empty, List)
  // ---------------------------------------------------------------------------
  Widget _buildTimelineContent(BuildContext context) {
    if (_loading && _events.isEmpty) {
      return const ClaraSkeletonList(itemCount: 4);
    }

    if (_error != null && _events.isEmpty) {
      return ErrorRetryView(
        message: _error!,
        onRetry: _loadTimeline,
      );
    }

    final displayed = _filteredAndSortedEvents;

    if (displayed.isEmpty) {
      return ClaraEmptyState(
        icon: Icons.history_edu_outlined,
        title: LifeMapTimelineStrings.emptyTitle(_locale),
        message: LifeMapTimelineStrings.emptyDescription(_locale),
      );
    }

    return Column(
      children: List.generate(displayed.length, (index) {
        final event = displayed[index];
        final isFirst = index == 0;
        final isLast = index == displayed.length - 1;
        return _buildTimelineEventRow(context, event, isFirst: isFirst, isLast: isLast);
      }),
    );
  }

  // ---------------------------------------------------------------------------
  // Single Timeline Row with Rail and Event Card
  // ---------------------------------------------------------------------------
  Widget _buildTimelineEventRow(
    BuildContext context,
    LifeMapTimelineEvent event, {
    required bool isFirst,
    required bool isLast,
  }) {
    final theme = Theme.of(context);
    final primaryDate = _perspective == LifeMapTimelinePerspective.validTime
        ? event.occurredAt
        : event.recordedAt;
    final secondaryDate = _perspective == LifeMapTimelinePerspective.validTime
        ? event.recordedAt
        : event.occurredAt;

    final primaryLabel = _perspective == LifeMapTimelinePerspective.validTime
        ? (_locale.startsWith('en') ? 'Occurred:' : 'Diễn ra:')
        : (_locale.startsWith('en') ? 'Recorded:' : 'Ghi nhận:');

    final secondaryLabel = _perspective == LifeMapTimelinePerspective.validTime
        ? (_locale.startsWith('en') ? 'System Ingested:' : 'Hệ thống lưu:')
        : (_locale.startsWith('en') ? 'Real Occurred:' : 'Diễn ra thực tế:');

    final nodeColor = _truthStateColor(theme, event.truthState);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Timeline Rail (Connecting line + Node Circle)
          SizedBox(
            width: 36,
            child: Stack(
              alignment: Alignment.topCenter,
              children: [
                // Rail Line
                Positioned.fill(
                  top: isFirst ? 20 : 0,
                  bottom: isLast ? null : 0,
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: Container(
                      width: 2,
                      height: isLast ? 24 : double.infinity,
                      color: theme.colorScheme.outlineVariant,
                    ),
                  ),
                ),
                // Node circle
                Positioned(
                  top: 14,
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surface,
                      shape: BoxShape.circle,
                      border: Border.all(color: nodeColor, width: 2.5),
                    ),
                    child: Center(
                      child: Icon(
                        _eventKindIcon(event.eventType),
                        size: 14,
                        color: nodeColor,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          // Event Card
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
              child: ClaraCard(
                onTap: () => _showRevisionInspector(context, event),
                semanticLabel: '${event.title}, ${event.truthState.label(_locale)}',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Top Bar: Event Type Tag + Truth State Badge + Revision Chip
                    Wrap(
                      spacing: ClaraTokens.spaceSm,
                      runSpacing: ClaraTokens.spaceXs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        _buildTruthStateBadge(theme, event.truthState),
                        if (event.revisionNo > 1)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: ClaraTokens.spaceXs,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: theme.colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
                            ),
                            child: Text(
                              'v${event.revisionNo}',
                              style: theme.textTheme.labelSmall?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        if (event.sourceKind != null)
                          Text(
                            '• ${LifeMapTimelineStrings.sourceKindLabel(_locale, event.sourceKind)}',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    // Title
                    Text(
                      event.title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    if (event.summary != null && event.summary!.isNotEmpty) ...[
                      const SizedBox(height: ClaraTokens.spaceXs),
                      Text(
                        event.summary!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: ClaraTokens.spaceSm),
                    // Bitemporal Timestamps
                    Row(
                      children: [
                        Icon(
                          Icons.access_time_outlined,
                          size: 14,
                          color: theme.colorScheme.primary,
                        ),
                        const SizedBox(width: ClaraTokens.spaceXs),
                        Expanded(
                          child: Text(
                            '$primaryLabel ${_formatDateTime(primaryDate)}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: theme.colorScheme.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '$secondaryLabel ${_formatDateTime(secondaryDate)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        fontSize: 11,
                      ),
                    ),
                    // Action: Inspect button meeting >=48dp touch target
                    const SizedBox(height: ClaraTokens.spaceSm),
                    Align(
                      alignment: Alignment.centerRight,
                      child: MinTapTarget(
                        child: TextButton.icon(
                          onPressed: () => _showRevisionInspector(context, event),
                          icon: const Icon(Icons.history_outlined, size: 16),
                          label: Text(
                            _locale.startsWith('en')
                                ? 'History & Details'
                                : 'Lịch sử & Chi tiết',
                          ),
                        ),
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

  IconData _eventKindIcon(String eventType) {
    final lower = eventType.toLowerCase();
    if (lower.contains('med') || lower.contains('thuoc')) {
      return Icons.medication_outlined;
    }
    if (lower.contains('symptom') || lower.contains('trieu_chung')) {
      return Icons.healing_outlined;
    }
    if (lower.contains('visit') || lower.contains('kham')) {
      return Icons.calendar_today_outlined;
    }
    if (lower.contains('lab') || lower.contains('result') || lower.contains('xet_nghiem')) {
      return Icons.science_outlined;
    }
    if (lower.contains('measurement') || lower.contains('vital') || lower.contains('chi_so')) {
      return Icons.monitor_heart_outlined;
    }
    if (lower.contains('document') || lower.contains('tai_lieu')) {
      return Icons.description_outlined;
    }
    return Icons.event_note_outlined;
  }

  Color _truthStateColor(ThemeData theme, LifeMapClientState state) {
    final status = theme.extension<ClaraStatusColors>();
    switch (state) {
      case LifeMapClientState.confirmed:
        return status?.success ?? theme.colorScheme.primary;
      case LifeMapClientState.awaitingReview:
        return theme.colorScheme.secondary;
      case LifeMapClientState.disputed:
        return theme.colorScheme.error;
      case LifeMapClientState.stale:
        return status?.warning ?? theme.colorScheme.tertiary;
      case LifeMapClientState.draft:
      case LifeMapClientState.unavailable:
      case LifeMapClientState.offline:
        return theme.colorScheme.outline;
    }
  }

  Widget _buildTruthStateBadge(ThemeData theme, LifeMapClientState state) {
    final color = _truthStateColor(theme, state);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceSm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        state.label(_locale),
        style: theme.textTheme.labelSmall?.copyWith(
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Revision History & Details Inspector Modal Sheet
  // ---------------------------------------------------------------------------
  void _showRevisionInspector(BuildContext context, LifeMapTimelineEvent event) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);
        return SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.85,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceMd,
                0,
                ClaraTokens.spaceMd,
                ClaraTokens.spaceLg,
              ),
              child: ListView(
                children: [
                  Text(
                    LifeMapTimelineStrings.revisionInspectorTitle(_locale),
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    LifeMapTimelineStrings.revisionInspectorDescription(_locale),
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const Divider(height: ClaraTokens.spaceLg),
                  // Event identity & status
                  Row(
                    children: [
                      _buildTruthStateBadge(theme, event.truthState),
                      const SizedBox(width: ClaraTokens.spaceSm),
                      Text(
                        LifeMapTimelineStrings.revisionBadge(_locale, event.revisionNo),
                        style: theme.textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaraTokens.spaceSm),
                  Text(
                    event.title,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (event.summary != null) ...[
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(
                      event.summary!,
                      style: theme.textTheme.bodyMedium,
                    ),
                  ],
                  const SizedBox(height: ClaraTokens.spaceMd),
                  // Bitemporal details box
                  Container(
                    padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _locale.startsWith('en')
                              ? 'Bitemporal Tracking:'
                              : 'Theo dõi song trục thời gian:',
                          style: theme.textTheme.labelLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: ClaraTokens.spaceSm),
                        Text(
                          '• Thời gian diễn ra (\tau_v): ${_formatDateTime(event.occurredAt)}',
                          style: theme.textTheme.bodySmall,
                        ),
                        const SizedBox(height: ClaraTokens.spaceXs),
                        Text(
                          '• Thời gian ghi nhận (\tau_k): ${_formatDateTime(event.recordedAt)}',
                          style: theme.textTheme.bodySmall,
                        ),
                        if (event.sourceKind != null) ...[
                          const SizedBox(height: ClaraTokens.spaceXs),
                          Text(
                            '• Nguồn dữ liệu: ${LifeMapTimelineStrings.sourceKindLabel(_locale, event.sourceKind)}',
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  // Revisions trail
                  if (event.revisions.isNotEmpty) ...[
                    Text(
                      _locale.startsWith('en')
                          ? 'Audit Revisions Trail'
                          : 'Các phiên bản lịch sử kiểm toán',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: ClaraTokens.spaceSm),
                    ...event.revisions.map((rev) {
                      final revNo = rev['revision_no']?.toString() ?? '1';
                      final why = rev['why'];
                      final reason = why is Map ? why['text']?.toString() : rev['reason']?.toString();
                      return Padding(
                        padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            border: Border.all(color: theme.colorScheme.outlineVariant),
                            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(ClaraTokens.spaceMd),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Phiên bản $revNo',
                                  style: theme.textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                if (reason != null && reason.isNotEmpty) ...[
                                  const SizedBox(height: ClaraTokens.spaceXs),
                                  Text(
                                    '${LifeMapTimelineStrings.reasonLabel(_locale)} $reason',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),
                      );
                    }),
                    const SizedBox(height: ClaraTokens.spaceMd),
                  ],
                  // Actions (Online required)
                  if (!_isOffline) ...[
                    Row(
                      children: [
                        if (widget.onCorrectEvent != null)
                          Expanded(
                            child: MinTapTarget(
                              child: ClaraButton.secondary(
                                label: LifeMapTimelineStrings.correctAction(_locale),
                                icon: Icons.edit_outlined,
                                onPressed: () {
                                  Navigator.of(sheetContext).pop();
                                  widget.onCorrectEvent!(event);
                                },
                              ),
                            ),
                          ),
                        if (widget.onCorrectEvent != null && widget.onDisputeEvent != null)
                          const SizedBox(width: ClaraTokens.spaceSm),
                        if (widget.onDisputeEvent != null &&
                            event.truthState != LifeMapClientState.disputed)
                          Expanded(
                            child: MinTapTarget(
                              child: ClaraButton.secondary(
                                label: LifeMapTimelineStrings.disputeAction(_locale),
                                icon: Icons.report_outlined,
                                onPressed: () {
                                  Navigator.of(sheetContext).pop();
                                  widget.onDisputeEvent!(event);
                                },
                              ),
                            ),
                          ),
                      ],
                    ),
                  ] else ...[
                    Text(
                      _locale.startsWith('en')
                          ? 'Action buttons disabled in offline mode.'
                          : 'Các thao tác chỉnh sửa bị khóa ở chế độ ngoại tuyến.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.error,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                  const SizedBox(height: ClaraTokens.spaceMd),
                  MinTapTarget(
                    child: ClaraButton.primary(
                      label: LifeMapTimelineStrings.close(_locale),
                      onPressed: () => Navigator.of(sheetContext).pop(),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
