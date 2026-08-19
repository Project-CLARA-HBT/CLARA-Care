// Home surface for the CLARA_Mobile redesign (Experience_V3).
//
// Consumes the /api/v2/home read model with prioritized consumer hierarchy:
//   * Priority 1: Top next-action card (severity-based: urgent/attention/normal).
//   * Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances.
//   * Priority 3: Today's schedule (medications, visits, care tasks).
//   * Priority 4: Recent changes (real source records only; no fake activity).
//   * Priority 5: Calm caught-up state when all tasks are complete.
//
// Privileged feature launcher grid is removed from ordinary user personal Home;
// Council and Scribe are scoped to professional drawer/menu for doctor/admin.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/home_v2_model.dart';
import '../../core/session_store.dart';
import '../../screens/careguard_cabinet_screen.dart';
import '../../screens/chat_screen.dart';
import '../../screens/phr_screen.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_chip.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';
import '../unified/visits_surface.dart';
import 'more_screen_v3.dart';

/// Coarse, no-PII screen-view event name for the redesigned Home.
const String kMobileHomeViewedEvent = 'mobile_home_viewed';

/// The redesigned, role-aware Home surface consuming the /api/v2/home read model.
class HomeScreenV3 extends StatefulWidget {
  const HomeScreenV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    required this.summary,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Resolver built by the redesign root from [summary].
  final MobileFeatureFlagResolver resolver;

  /// The already-loaded role-scoped `mobile/summary` (may be null).
  final Map<String, dynamic>? summary;

  /// Optional app-wide language state.
  final LanguageController? languageController;

  @override
  State<HomeScreenV3> createState() => _HomeScreenV3State();
}

class _HomeScreenV3State extends State<HomeScreenV3> {
  late Map<String, dynamic>? _summary = widget.summary;
  late MobileFeatureFlagResolver _resolver = widget.resolver;

  HomeV2Model? _homeModel;
  bool _loading = true;
  String? _error;

  /// Ids of tasks whose completion action is in flight.
  final Set<String> _completing = <String>{};

  @override
  void initState() {
    super.initState();
    getAnalyticsClient().captureScreenView(kMobileHomeViewedEvent);
    if (widget.summary != null) {
      _homeModel = HomeV2Model.fromJson(widget.summary!);
      _loading = false;
    } else {
      _loadHome();
    }
  }

  String get _role => widget.sessionStore.role ?? 'normal';
  bool get _isDoctorOrAdmin => _role == 'doctor' || _role == 'admin';

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  Future<void> _loadHome() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = _copy[ConsumerTerm.sessionExpired];
        });
      }
      return;
    }

    try {
      Map<String, dynamic> data;
      try {
        data = await widget.apiClient.getHomeV2(accessToken: token);
      } catch (_) {
        // Fallback to mobile/summary or cached state if getHomeV2 is unavailable
        if (_summary != null) {
          data = _summary!;
        } else {
          data = await widget.apiClient.getMobileSummary(accessToken: token);
        }
      }

      if (!mounted) return;
      setState(() {
        _homeModel = HomeV2Model.fromJson(data);
        _loading = false;
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _copy[ConsumerTerm.todayLoadFailed];
      });
    }
  }

  Future<void> _refresh() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return;

    try {
      final data = await widget.apiClient.getHomeV2(accessToken: token);
      if (!mounted) return;
      setState(() {
        _homeModel = HomeV2Model.fromJson(data);
        _error = null;
      });
    } catch (_) {
      try {
        final summaryData =
            await widget.apiClient.getMobileSummary(accessToken: token);
        if (!mounted) return;
        setState(() {
          _summary = summaryData;
          _resolver = MobileFeatureFlagResolver(summary: summaryData);
          _homeModel = HomeV2Model.fromJson(summaryData);
        });
      } catch (_) {}
    }
  }

  Future<void> _openScreen(Widget screen) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  }

  Future<void> _completeTask(String taskId) async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty || _completing.contains(taskId)) return;

    setState(() => _completing.add(taskId));
    try {
      await widget.apiClient
          .completeLifeMapTask(accessToken: token, taskId: taskId);
      // Optimistically update schedule item state
      if (_homeModel != null) {
        final updatedSchedule = _homeModel!.schedule.map((item) {
          if (item.id == taskId) {
            return item.copyWith(completed: true, status: 'completed');
          }
          return item;
        }).toList();
        setState(() {
          _homeModel = HomeV2Model(
            profileId: _homeModel!.profileId,
            displayName: _homeModel!.displayName,
            topAction: _homeModel!.topAction,
            schedule: updatedSchedule,
            recentChanges: _homeModel!.recentChanges,
            alerts: _homeModel!.alerts,
            generatedAt: _homeModel!.generatedAt,
            contextVersion: _homeModel!.contextVersion,
            hasConnectedHealth: _homeModel!.hasConnectedHealth,
          );
        });
      }
      await _refresh();
    } on ApiException catch (e) {
      _showSnack(e.message);
    } catch (_) {
      _showSnack(_copy[ConsumerTerm.todayCompleteFailed]);
    } finally {
      if (mounted) {
        setState(() => _completing.remove(taskId));
      }
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void _handleTopAction(HomeNextAction action) {
    final kind = action.kind.toLowerCase();
    if (kind == 'medication') {
      _openScreen(
        CareguardCabinetScreen(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
        ),
      );
    } else if (kind == 'visit') {
      _openScreen(
        VisitsSurface(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          languageController: widget.languageController,
        ),
      );
    } else if (kind == 'review' || kind == 'chat') {
      _openScreen(
        ChatScreen(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          resolver: _resolver,
          polished: _resolver.uxPolishEnabled,
        ),
      );
    } else if (kind == 'phr') {
      _openScreen(
        PhrScreen(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          featureFlags: _resolver,
        ),
      );
    } else {
      _completeTask(action.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final copy = _copy;

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: _buildBody(copy),
        ),
      ),
    );
  }

  Widget _buildBody(ConsumerTerminology copy) {
    if (_loading && _homeModel == null) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceMd),
        children: [
          _GreetingHeader(
            role: _role,
            email: widget.sessionStore.email,
            onOpenProfessionalTools: _isDoctorOrAdmin
                ? () => _openScreen(
                      MoreScreenV3(
                        apiClient: widget.apiClient,
                        sessionStore: widget.sessionStore,
                        resolver: _resolver,
                        role: _role,
                        languageController: widget.languageController,
                      ),
                    )
                : null,
          ),
          const SizedBox(height: ClaraTokens.spaceXl),
          const Center(child: CircularProgressIndicator()),
        ],
      );
    }

    if (_error != null && _homeModel == null) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        children: [
          const SizedBox(height: ClaraTokens.spaceXl),
          ErrorRetryView(message: _error!, onRetry: _loadHome),
        ],
      );
    }

    final home = _homeModel ?? const HomeV2Model();
    final topAction = home.topAction;
    final schedule = home.schedule;
    final recentChanges = home.recentChanges;
    final isCaughtUp = home.isCaughtUp;

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceMd),
      children: [
        // Top Greeting Header
        _GreetingHeader(
          role: _role,
          email: widget.sessionStore.email,
          onOpenProfessionalTools: _isDoctorOrAdmin
              ? () => _openScreen(
                    MoreScreenV3(
                      apiClient: widget.apiClient,
                      sessionStore: widget.sessionStore,
                      resolver: _resolver,
                      role: _role,
                      languageController: widget.languageController,
                    ),
                  )
              : null,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),

        // Priority 1: Top next-action card (severity-based)
        if (topAction != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _TopNextActionCard(
              action: topAction,
              copy: copy,
              onAction: () => _handleTopAction(topAction),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
        ],

        // Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: _AskClaraEntryCard(
            copy: copy,
            onTextTap: () => _openScreen(
              ChatScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                resolver: _resolver,
                polished: _resolver.uxPolishEnabled,
              ),
            ),
            onCameraTap: () => _openScreen(
              CareguardCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              ),
            ),
            onVoiceTap: () => _openScreen(
              ChatScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                resolver: _resolver,
                polished: _resolver.uxPolishEnabled,
              ),
            ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceLg),

        // Priority 3: Today's schedule (medications, visits, care tasks)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: _TodayScheduleSection(
            schedule: schedule,
            completingIds: _completing,
            copy: copy,
            onCompleteTask: _completeTask,
            onOpenMedications: () => _openScreen(
              CareguardCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              ),
            ),
            onOpenVisits: () => _openScreen(
              VisitsSurface(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                languageController: widget.languageController,
              ),
            ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceLg),

        // Priority 5: Calm caught-up state when all tasks are complete
        if (isCaughtUp || (schedule.isNotEmpty && schedule.every((e) => e.completed))) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
            child: _CaughtUpCard(copy: copy),
          ),
          const SizedBox(height: ClaraTokens.spaceLg),
        ],

        // Priority 4: Recent changes (real source records only; no fake activity)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: _RecentChangesSection(
            recentChanges: recentChanges,
            copy: copy,
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceXl),
      ],
    );
  }
}

// =============================================================================
// Header & Greeting
// =============================================================================

String _roleLabel(String role) {
  switch (role) {
    case 'admin':
      return 'Quản trị viên';
    case 'doctor':
      return 'Bác sĩ';
    case 'researcher':
      return 'Nhà nghiên cứu';
    case 'normal':
    default:
      return 'Người dùng';
  }
}

String _timeOfDayGreeting(DateTime now) {
  final hour = now.hour;
  if (hour < 11) return 'Chào buổi sáng';
  if (hour < 14) return 'Chào buổi trưa';
  if (hour < 18) return 'Chào buổi chiều';
  return 'Chào buổi tối';
}

IconData _timeOfDayIcon(DateTime now) {
  final hour = now.hour;
  if (hour < 11) return Icons.wb_sunny_outlined;
  if (hour < 14) return Icons.wb_sunny;
  if (hour < 18) return Icons.wb_twilight;
  return Icons.nightlight_round;
}

class _GreetingHeader extends StatelessWidget {
  const _GreetingHeader({
    required this.role,
    this.email,
    this.onOpenProfessionalTools,
  });

  final String role;
  final String? email;
  final VoidCallback? onOpenProfessionalTools;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);
    final now = DateTime.now();
    final greeting = _timeOfDayGreeting(now);
    final hasEmail = email != null && email!.isNotEmpty;

    final radius = BorderRadius.circular(
      GlassTokens.radiusCard * GlassTokens.squircleFactor,
    );

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClipRRect(
        borderRadius: radius,
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: radius,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color.lerp(scheme.primary, Colors.white, 0.12)!,
                scheme.primary,
                Color.lerp(scheme.primary, Colors.black, 0.22)!,
              ],
            ),
            boxShadow: [
              BoxShadow(
                color: scheme.primary.withValues(alpha: 0.32),
                blurRadius: 24,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              Positioned(
                right: -8,
                top: -8,
                child: ExcludeSemantics(
                  child: Icon(
                    _timeOfDayIcon(now),
                    size: 96,
                    color: Colors.white.withValues(alpha: 0.14),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(ClaraTokens.spaceLg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      greeting,
                      style: textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                      textScaler: textScaler,
                    ),
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(
                      'CLARA sẵn sàng đồng hành cùng sức khỏe của bạn.',
                      style: textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.88),
                      ),
                      textScaler: textScaler,
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    Wrap(
                      spacing: ClaraTokens.spaceSm,
                      runSpacing: ClaraTokens.spaceSm,
                      children: [
                        _HeroChip(
                          icon: Icons.badge_outlined,
                          label: _roleLabel(role),
                        ),
                        if (hasEmail)
                          _HeroChip(
                            icon: Icons.mail_outline,
                            label: email!,
                          ),
                        if (onOpenProfessionalTools != null)
                          Material(
                            type: MaterialType.transparency,
                            child: InkWell(
                              onTap: onOpenProfessionalTools,
                              borderRadius:
                                  BorderRadius.circular(GlassTokens.radiusPill),
                              child: const _HeroChip(
                                icon: Icons.medical_services_outlined,
                                label: 'Công cụ chuyên môn →',
                              ),
                            ),
                          ),
                      ],
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
}

class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceSm,
        vertical: ClaraTokens.spaceXs,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.20),
        borderRadius: BorderRadius.circular(GlassTokens.radiusPill),
        border: Border.all(color: Colors.white.withValues(alpha: 0.30)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: Colors.white),
          const SizedBox(width: ClaraTokens.spaceXs),
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// Priority 1: Top Next-Action Card (Severity-Based)
// =============================================================================

class _TopNextActionCard extends StatelessWidget {
  const _TopNextActionCard({
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
    final textTheme = theme.textTheme;

    final isUrgent = action.isUrgent;
    final isAttention = action.isAttention;

    final Color accentColor = isUrgent
        ? const Color(0xFFDC2626) // Red
        : isAttention
            ? const Color(0xFFD97706) // Amber
            : scheme.primary; // Brand Teal

    final Color containerColor = isUrgent
        ? const Color(0xFFFEF2F2)
        : isAttention
            ? const Color(0xFFFFFBEB)
            : scheme.primaryContainer.withValues(alpha: 0.25);

    final String badgeLabel = isUrgent
        ? copy[ConsumerTerm.homeSeverityUrgent]
        : isAttention
            ? copy[ConsumerTerm.homeSeverityAttention]
            : copy[ConsumerTerm.homeSeverityNormal];

    final IconData icon = isUrgent
        ? Icons.warning_amber_rounded
        : isAttention
            ? Icons.priority_high_rounded
            : Icons.task_alt_outlined;

    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: containerColor,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        border: Border.all(color: accentColor.withValues(alpha: 0.45), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: accentColor.withValues(alpha: 0.10),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                ),
                child: Icon(icon, color: accentColor, size: 22),
              ),
              const SizedBox(width: ClaraTokens.spaceSm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      copy[ConsumerTerm.homeNextActionTitle],
                      style: textTheme.labelSmall?.copyWith(
                        color: accentColor,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.4,
                      ),
                    ),
                    Text(
                      action.title,
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: theme.colorScheme.onSurface,
                      ),
                    ),
                  ],
                ),
              ),
              ClaraChip(
                label: badgeLabel,
                selected: isUrgent || isAttention,
              ),
            ],
          ),
          if (action.description != null && action.description!.isNotEmpty) ...[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              action.description!,
              style: textTheme.bodyMedium?.copyWith(
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

// =============================================================================
// Priority 2: Full-width Ask CLARA Entry Card with text/camera/voice affordances
// =============================================================================

class _AskClaraEntryCard extends StatelessWidget {
  const _AskClaraEntryCard({
    required this.copy,
    required this.onTextTap,
    required this.onCameraTap,
    required this.onVoiceTap,
  });

  final ConsumerTerminology copy;
  final VoidCallback onTextTap;
  final VoidCallback onCameraTap;
  final VoidCallback onVoiceTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return ClaraCard.static_(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onTextTap,
            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceXs),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [scheme.primary, const Color(0xFF2563EB)],
                      ),
                      borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                    ),
                    child: const Icon(Icons.auto_awesome, color: Colors.white, size: 22),
                  ),
                  const SizedBox(width: ClaraTokens.spaceMd),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          copy[ConsumerTerm.actionAskClara],
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          copy[ConsumerTerm.homeAskPlaceholder],
                          style: textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceXs),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: scheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          const Divider(height: 1),
          const SizedBox(height: ClaraTokens.spaceSm),
          Row(
            children: [
              Expanded(
                child: _AskAffordanceButton(
                  icon: Icons.chat_bubble_outline,
                  label: copy[ConsumerTerm.homeAskText],
                  onTap: onTextTap,
                ),
              ),
              Expanded(
                child: _AskAffordanceButton(
                  icon: Icons.camera_alt_outlined,
                  label: copy[ConsumerTerm.homeAskCamera],
                  onTap: onCameraTap,
                ),
              ),
              Expanded(
                child: _AskAffordanceButton(
                  icon: Icons.mic_none_outlined,
                  label: copy[ConsumerTerm.homeAskVoice],
                  onTap: onVoiceTap,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AskAffordanceButton extends StatelessWidget {
  const _AskAffordanceButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

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

// =============================================================================
// Priority 3: Today's Schedule (Medications, Visits, Care Tasks)
// =============================================================================

class _TodayScheduleSection extends StatelessWidget {
  const _TodayScheduleSection({
    required this.schedule,
    required this.completingIds,
    required this.copy,
    required this.onCompleteTask,
    required this.onOpenMedications,
    required this.onOpenVisits,
  });

  final List<HomeScheduleItem> schedule;
  final Set<String> completingIds;
  final ConsumerTerminology copy;
  final ValueChanged<String> onCompleteTask;
  final VoidCallback onOpenMedications;
  final VoidCallback onOpenVisits;

  @override
  Widget build(BuildContext context) {
    final pendingItems = schedule.where((item) => !item.completed).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: copy[ConsumerTerm.homeScheduleTitle],
          trailing: pendingItems.isNotEmpty
              ? ClaraChip(
                  label:
                      '${pendingItems.length} ${copy[ConsumerTerm.todayPending]}',
                  selected: true,
                )
              : null,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        if (schedule.isEmpty)
          ClaraEmptyState(
            icon: Icons.calendar_today_outlined,
            title: copy[ConsumerTerm.homeScheduleEmpty],
            message: copy[ConsumerTerm.todayEmptyDescription],
          )
        else
          ...schedule.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: _ScheduleItemCard(
                item: item,
                isCompleting: completingIds.contains(item.id),
                copy: copy,
                onComplete: () => onCompleteTask(item.id),
                onOpenMedications: onOpenMedications,
                onOpenVisits: onOpenVisits,
              ),
            ),
          ),
      ],
    );
  }
}

class _ScheduleItemCard extends StatelessWidget {
  const _ScheduleItemCard({
    required this.item,
    required this.isCompleting,
    required this.copy,
    required this.onComplete,
    required this.onOpenMedications,
    required this.onOpenVisits,
  });

  final HomeScheduleItem item;
  final bool isCompleting;
  final ConsumerTerminology copy;
  final VoidCallback onComplete;
  final VoidCallback onOpenMedications;
  final VoidCallback onOpenVisits;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final kind = item.kind.toLowerCase();

    final IconData icon = kind == 'medication'
        ? Icons.medication_outlined
        : kind == 'visit'
            ? Icons.event_available_outlined
            : Icons.task_alt_outlined;

    final Color iconColor = kind == 'medication'
        ? const Color(0xFF0D9488)
        : kind == 'visit'
            ? const Color(0xFF2563EB)
            : const Color(0xFF7C3AED);

    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
            ),
            child: Icon(icon, color: iconColor, size: 22),
          ),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title.isEmpty
                      ? copy[ConsumerTerm.todayUnnamedTask]
                      : item.title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    decoration:
                        item.completed ? TextDecoration.lineThrough : null,
                  ),
                ),
                if (item.subtitle != null && item.subtitle!.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    item.subtitle!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
                if (item.time != null && item.time!.isNotEmpty) ...[
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    item.time!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: scheme.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          if (item.completed)
            const ClaraChip(
              label: 'Đã xong',
            )
          else if (kind == 'medication')
            TextButton.icon(
              onPressed: onOpenMedications,
              icon: const Icon(Icons.check, size: 16),
              label: Text(copy[ConsumerTerm.actionComplete]),
            )
          else if (kind == 'visit')
            TextButton.icon(
              onPressed: onOpenVisits,
              icon: const Icon(Icons.arrow_forward, size: 16),
              label: Text(copy[ConsumerTerm.actionOpen]),
            )
          else
            ClaraButton.primary(
              label: copy[ConsumerTerm.actionComplete],
              icon: Icons.check,
              loading: isCompleting,
              onPressed: onComplete,
            ),
        ],
      ),
    );
  }
}

// =============================================================================
// Priority 5: Calm Caught-Up State
// =============================================================================

class _CaughtUpCard extends StatelessWidget {
  const _CaughtUpCard({required this.copy});

  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceLg),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FDF4),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        border: Border.all(color: const Color(0xFF86EFAC)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.task_alt_rounded,
            color: Color(0xFF16A34A),
            size: 28,
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
                const SizedBox(height: ClaraTokens.spaceXs),
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

// =============================================================================
// Priority 4: Recent Changes (Real Source Records Only; No Fake Activity)
// =============================================================================

class _RecentChangesSection extends StatelessWidget {
  const _RecentChangesSection({
    required this.recentChanges,
    required this.copy,
  });

  final List<HomeRecentChange> recentChanges;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: copy[ConsumerTerm.homeRecentChangesTitle]),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          copy[ConsumerTerm.homeRecentChangesRealSourceNotice],
          style: theme.textTheme.bodySmall?.copyWith(
            color: scheme.onSurfaceVariant,
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
              child: _RecentChangeCard(change: change, copy: copy),
            ),
          ),
      ],
    );
  }
}

class _RecentChangeCard extends StatelessWidget {
  const _RecentChangeCard({
    required this.change,
    required this.copy,
  });

  final HomeRecentChange change;
  final ConsumerTerminology copy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final IconData icon = change.kind.contains('medication')
        ? Icons.medication_outlined
        : change.kind.contains('visit')
            ? Icons.event_note_outlined
            : Icons.description_outlined;

    return ClaraCard.static_(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: scheme.primary, size: 22),
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
                if (change.summary != null && change.summary!.isNotEmpty) ...[
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    change.summary!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
                if (change.source != null && change.source!.isNotEmpty) ...[
                  const SizedBox(height: ClaraTokens.spaceXs),
                  ClaraChip(
                    label: change.source!,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
