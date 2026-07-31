// Home surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 3 (rebuilt visual Home). This is the
// "Trang chủ" flanking destination: a modern, role-aware landing built on the
// redesign design system (ClaraTokens / ClaraCard / SectionHeader) rather than
// a bare list.
//
// It renders:
//   * a personalized, time-of-day greeting header with a role chip (Req 3.1);
//   * a role-aware quick-action grid of tappable `ClaraCard`s that routes each
//     available tool to its existing feature screen (Req 3.1, 3.6, 3.7);
//   * a "recent activity" region backed by the shared friendly empty state,
//     since no recents endpoint exists yet — no fabricated data (Req 3.1);
//   * a first-load skeleton, a PII-free `ErrorRetryView`, and pull-to-refresh
//     (Req 3.3, 3.4, 3.5).
//
// The redesign root (`redesign_root.dart`) already loaded the role-scoped
// `mobile/summary` and built the [MobileFeatureFlagResolver]; both are passed in
// so this surface does NOT re-fetch for gating. Privileged tool entries are
// derived ONLY from a successfully loaded summary and fail CLOSED — a null
// summary yields only the universally available PHR entry (INV-4, Req 3.2).
// Pull-to-refresh re-fetches `mobile/summary`, updates local state, and rebuilds
// the resolver from the fresh summary so gating stays consistent.
//
// Gating mirrors `lib/experience/home_screen.dart`:
//   * careguard / council via the summary `feature_flags` booleans;
//   * chat / selfMedCabinet / consentCenter via the resolver gates;
//   * scribe requires the flag AND an authorized role — `doctor` OR (for this
//     redesign) `admin`, so it is never reachable for any other role;
//   * PHR is ALWAYS reachable, independent of the summary.
//
// Copy is Vietnamese-first; analytics is a single coarse, no-PII screen-view.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/careguard_cabinet_screen.dart';
import '../../screens/careguard_screen.dart';
import '../../screens/chat_screen.dart';
import '../../screens/consent_center_screen.dart';
import '../../screens/council_case_screen.dart';
import '../../screens/council_screen.dart';
import '../../screens/phr_screen.dart';
import '../../screens/scribe_screen.dart';
import '../../screens/selfmed_cabinet_screen.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../language_controller.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

/// Coarse, no-PII screen-view event name for the redesigned Home.
///
/// A plain string literal (not a `MobileAnalyticsEvents` constant) because
/// `analytics.dart` is owned by another concern. It carries no PII and
/// identifies only the surface viewed (INV-3, Req 3.8).
const String kMobileHomeViewedEvent = 'mobile_home_viewed';

/// The redesigned, role-aware Home surface (Experience_V3, Requirement 3).
///
/// The constructor contract is fixed by `redesign_root.dart`: it is given the
/// already-loaded role-scoped [summary] (may be null) and a [resolver] built
/// from it, so this surface derives tools without a second fetch.
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

  /// Resolver built by the redesign root from [summary]. Used as-is for the
  /// initial render; rebuilt locally after a pull-to-refresh.
  final MobileFeatureFlagResolver resolver;

  /// The already-loaded role-scoped `mobile/summary` (may be null when the
  /// parent's load failed). Privileged tools are derived only when non-null.
  final Map<String, dynamic>? summary;

  /// Optional app-wide language state; absent embeddings stay Vietnamese-first.
  final LanguageController? languageController;

  @override
  State<HomeScreenV3> createState() => _HomeScreenV3State();
}

class _HomeScreenV3State extends State<HomeScreenV3> {
  /// Current role-scoped summary. Seeded from the parent-provided value and
  /// replaced on a successful pull-to-refresh.
  late Map<String, dynamic>? _summary = widget.summary;

  /// Resolver for the current [_summary]. Seeded from the parent-built resolver
  /// and rebuilt from the fresh summary after a refresh so gating stays in sync.
  late MobileFeatureFlagResolver _resolver = widget.resolver;

  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    // Coarse, no-PII screen-view through the shared consent/PII-guarded client.
    getAnalyticsClient().captureScreenView(kMobileHomeViewedEvent);
  }

  /// Whether a role-scoped summary is currently available (fail-closed gate).
  bool get _summaryLoaded => _summary != null;

  /// The authenticated role, defaulting to the least-privileged `normal`.
  String get _role => widget.sessionStore.role ?? 'normal';

  ConsumerTerminology get _copy => ConsumerTerminology.forLocale(
        widget.languageController?.languageCode,
      );

  /// Reads a boolean `feature_flags` entry from the current summary, mirroring
  /// `home_screen.dart`'s `_featureEnabled`: an unloadable summary, a non-map
  /// `feature_flags`, a missing key, or a non-`true` value all resolve to
  /// `false` (fail-closed).
  bool _featureEnabled(String key) {
    final summary = _summary;
    if (summary == null) {
      return false;
    }
    final flags = summary['feature_flags'];
    if (flags is! Map<String, dynamic>) {
      return false;
    }
    return flags[key] == true;
  }

  /// Whether the summary reports the API as healthy. Reads the `api_health`
  /// status the summary already carries; a missing/non-`ok` status resolves to
  /// `false` (fail-closed). No extra request is made.
  bool get _apiHealthy {
    final summary = _summary;
    if (summary == null) {
      return false;
    }
    final health = summary['api_health'];
    if (health is! Map) {
      return false;
    }
    return health['status'] == 'ok';
  }

  /// Re-fetches the role-scoped `mobile/summary` and rebuilds the resolver from
  /// the fresh payload. Exposed as the `RefreshIndicator.onRefresh` callback and
  /// the `ErrorRetryView` retry affordance. Guards every `setState` with
  /// `mounted` and surfaces a Vietnamese-first, PII-free error.
  Future<void> _refreshSummary() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }

    setState(() {
      _refreshing = true;
    });

    try {
      final data = await widget.apiClient.getMobileSummary(accessToken: token);
      if (!mounted) {
        return;
      }
      setState(() {
        _summary = data;
        _resolver = MobileFeatureFlagResolver(summary: data);
      });
    } on ApiException {
      if (!mounted) {
        return;
      }
    } catch (_) {
      if (!mounted) {
        return;
      }
    } finally {
      if (mounted) {
        setState(() {
          _refreshing = false;
        });
      }
    }
  }

  Future<void> _openScreen(Widget screen) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    final role = _role;
    final resolver = _resolver;
    final summaryLoaded = _summaryLoaded;
    final apiHealthy = _apiHealthy;

    // Privileged tool entries are derived ONLY from a successfully loaded,
    // role-scoped summary; when it is unavailable we fail closed and show none
    // of them (INV-4, Req 3.2).
    final canCareguard = _featureEnabled('careguard');
    final canCouncil = _featureEnabled('council');
    // Scribe additionally requires an authorized role. In this redesign both
    // `doctor` and `admin` may reach it; every other role stays fail-closed.
    final canScribe =
        resolver.scribeEnabled && (role == 'doctor' || role == 'admin');

    // A skeleton stands in for the tools grid only while a refresh is in flight
    // and we have no summary to show yet (Req 3.3). When content already exists,
    // the RefreshIndicator spinner is enough — we don't blank the screen.
    final showInitialSkeleton = _refreshing && !summaryLoaded;

    // A settled state with no summary shows no privileged entries and offers a
    // retry via the shared `ErrorRetryView` (INV-4, Req 3.4).
    final showSummaryRetry = !summaryLoaded && !_refreshing;

    final quickActions = <Widget>[
      if (summaryLoaded) ...[
        if (resolver.chatEnabled)
          _QuickActionCard(
            icon: Icons.chat_bubble_outline,
            title: _copy[ConsumerTerm.todayAskHealthTitle],
            subtitle: _copy[ConsumerTerm.todayAskHealthDescription],
            accent: const Color(0xFF2563EB),
            onTap: () => _openScreen(
              ChatScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                resolver: resolver,
                polished: resolver.uxPolishEnabled,
              ),
            ),
          ),
        if (canCareguard)
          _QuickActionCard(
            icon: Icons.medication,
            title: _copy[ConsumerTerm.todayCheckMedicineTitle],
            subtitle: _copy[ConsumerTerm.todayCheckMedicineDescription],
            accent: const Color(0xFF0EA5A4),
            onTap: () => _openScreen(
              CareguardScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              ),
            ),
          ),
        if (kCareguardMobileCabinetEnabled && canCareguard)
          _QuickActionCard(
            icon: Icons.medical_services_outlined,
            title: 'Tủ thuốc',
            subtitle: 'Quản lý danh sách thuốc của bạn',
            accent: const Color(0xFF14B8A6),
            onTap: () => _openScreen(
              CareguardCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              ),
            ),
          ),
        if (resolver.selfMedCabinetEnabled)
          _QuickActionCard(
            icon: Icons.medication_outlined,
            title: 'Tủ thuốc tự kê',
            subtitle: 'Quản lý thuốc & kiểm tra tương tác',
            accent: const Color(0xFF14B8A6),
            onTap: () => _openScreen(
              SelfMedCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                featureFlags: resolver,
              ),
            ),
          ),
        if (canCouncil)
          _QuickActionCard(
            icon: Icons.groups,
            title: 'Hội chẩn AI',
            subtitle: 'Tổng hợp ý kiến nhiều chuyên khoa',
            accent: const Color(0xFF7C3AED),
            onTap: () => _openScreen(
              // Council mobile parity: when COUNCIL_MOBILE_PARITY_ENABLED is on
              // route to the case-based flow, otherwise the legacy run screen —
              // mirroring `home_screen.dart`.
              kCouncilMobileParityEnabled
                  ? CouncilCaseScreen(
                      apiClient: widget.apiClient,
                      sessionStore: widget.sessionStore,
                    )
                  : CouncilScreen(
                      apiClient: widget.apiClient,
                      sessionStore: widget.sessionStore,
                    ),
            ),
          ),
        if (canScribe)
          _QuickActionCard(
            icon: Icons.mic_none,
            title: 'Ghi chú lâm sàng',
            subtitle: 'Ghi âm và tạo ghi chú SOAP',
            accent: const Color(0xFFDB2777),
            onTap: () => _openScreen(
              ScribeScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                featureFlags: resolver,
              ),
            ),
          ),
        if (resolver.consentCenterEnabled)
          _QuickActionCard(
            icon: Icons.privacy_tip_outlined,
            title: 'Trung tâm đồng ý',
            subtitle: 'Quản lý quyền riêng tư & yêu cầu dữ liệu',
            accent: const Color(0xFFF59E0B),
            onTap: () => _openScreen(
              ConsentCenterScreen(
                resolver: resolver,
                sessionStore: widget.sessionStore,
              ),
            ),
          ),
      ],
      // PHR is available to every authenticated role independent of the
      // summary, so its card is ALWAYS present (Req 3.2).
      _QuickActionCard(
        icon: Icons.folder_shared,
        title: _copy[ConsumerTerm.todaySaveHealthInfoTitle],
        subtitle: _copy[ConsumerTerm.todaySaveHealthInfoDescription],
        accent: const Color(0xFF0284C7),
        onTap: () => _openScreen(
          PhrScreen(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            // Enhanced read-only PHR surfaces are gated by
            // `phr_enhanced_mobile_enabled`; a null/unloadable summary resolves
            // the gate to false, so the screen behaves as the legacy PHR.
            featureFlags: resolver,
          ),
        ),
      ),
    ];

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          // Pull-to-refresh reloads the role-scoped summary (Req 3.5). The list
          // is ALWAYS scrollable so the gesture works even when content is short.
          onRefresh: _refreshSummary,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceMd),
            children: [
              _GreetingHeader(
                role: role,
                email: widget.sessionStore.email,
              ),
              // Primary call-to-action: the single most useful action for this
              // audience is to ask CLARA a question, so it gets a prominent,
              // full-width entry right under the hero. Only shown when a summary
              // is loaded and chat is granted for the role (fail-closed).
              if (summaryLoaded && resolver.chatEnabled) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaraTokens.spaceMd,
                  ),
                  child: _PrimaryChatCta(
                    title: _copy[ConsumerTerm.todayAskHealthTitle],
                    subtitle: _copy[ConsumerTerm.todayAskHealthDescription],
                    onTap: () => _openScreen(
                      ChatScreen(
                        apiClient: widget.apiClient,
                        sessionStore: widget.sessionStore,
                        resolver: resolver,
                        polished: resolver.uxPolishEnabled,
                      ),
                    ),
                  ),
                ),
              ],
              // A daily wellness tip: general, non-clinical encouragement that
              // makes the surface feel alive on every open. It is deterministic
              // (keyed off the calendar day), never fabricates medical claims,
              // and carries a soft reminder that CLARA supports decisions only.
              const SizedBox(height: ClaraTokens.spaceMd),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
                child: _DailyTipCard(),
              ),
              // At-a-glance stats: only rendered when a summary is loaded, and
              // only from data it already carries (system status + the number
              // of tools this role can reach). No extra fetch, no PII.
              if (summaryLoaded && !showInitialSkeleton) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaraTokens.spaceMd,
                  ),
                  child: _AtAGlanceRow(
                    apiHealthy: apiHealthy,
                    toolCount: quickActions.length,
                  ),
                ),
              ],
              const SizedBox(height: ClaraTokens.spaceSm),
              SectionHeader(title: _copy[ConsumerTerm.homeScreenToolsTitle]),
              // First load shows a polished skeleton instead of a blank region
              // (Req 3.3); once a summary exists the real tools grid is shown.
              if (showInitialSkeleton)
                const ClaraSkeletonList(itemCount: 4, showLeading: false)
              else
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaraTokens.spaceMd,
                  ),
                  child: _QuickActionGrid(children: quickActions),
                ),
              // Fail-closed error: a settled load with no summary shows no
              // privileged entries and offers a retry (INV-4, Req 3.4).
              if (showSummaryRetry) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                ErrorRetryView(
                  message: _copy[ConsumerTerm.homeScreenToolsLoadFailed],
                  onRetry: _refreshSummary,
                ),
              ],
              const SizedBox(height: ClaraTokens.spaceLg),
              SectionHeader(title: _copy[ConsumerTerm.homeScreenRecentTitle]),
              // No recents endpoint yet, so a friendly Vietnamese-first empty
              // state stands in — no fabricated data (Req 3.1).
              Padding(
                padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
                child: ClaraEmptyState(
                  icon: Icons.history,
                  title: _copy[ConsumerTerm.homeScreenNoRecentTitle],
                  message: _copy[ConsumerTerm.homeScreenNoRecentDescription],
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceXl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Maps an RBAC role id to a Vietnamese-first display label. Unknown roles fall
/// back to the least-privileged label so the header never leaks a raw id.
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

/// A time-of-day greeting keyed off the local hour, Vietnamese-first.
String _timeOfDayGreeting(DateTime now) {
  final hour = now.hour;
  if (hour < 11) {
    return 'Chào buổi sáng';
  }
  if (hour < 14) {
    return 'Chào buổi trưa';
  }
  if (hour < 18) {
    return 'Chào buổi chiều';
  }
  return 'Chào buổi tối';
}

/// A time-of-day icon that echoes the greeting (decorative only).
IconData _timeOfDayIcon(DateTime now) {
  final hour = now.hour;
  if (hour < 11) {
    return Icons.wb_sunny_outlined;
  }
  if (hour < 14) {
    return Icons.wb_sunny;
  }
  if (hour < 18) {
    return Icons.wb_twilight;
  }
  return Icons.nightlight_round;
}

/// Greeting hero: a bold, brand-gradient welcome banner with a soft glow, a
/// decorative time-of-day glyph, a role chip, and the signed-in email. Pure
/// chrome (no clinical text). The gradient is a deliberate, high-impact modern
/// hero — distinct from the flatter glass cards below it.
class _GreetingHeader extends StatelessWidget {
  const _GreetingHeader({required this.role, this.email});

  final String role;
  final String? email;

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
      child: A11yLabeled(
        label: '$greeting, vai trò ${_roleLabel(role)}',
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
            children: [
              // Decorative oversized time-of-day glyph, softly clipped.
              Positioned(
                right: -8,
                top: -8,
                child: Icon(
                  _timeOfDayIcon(now),
                  size: 96,
                  color: Colors.white.withValues(alpha: 0.14),
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
                      'CLARA sẵn sàng hỗ trợ bạn hôm nay.',
                      style: textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.88),
                      ),
                      textScaler: textScaler,
                    ),
                    const SizedBox(height: ClaraTokens.spaceMd),
                    Row(
                      children: [
                        _HeroChip(
                          icon: Icons.badge_outlined,
                          label: _roleLabel(role),
                        ),
                        if (hasEmail) ...[
                          const SizedBox(width: ClaraTokens.spaceSm),
                          Flexible(
                            child: _HeroChip(
                              icon: Icons.mail_outline,
                              label: email!,
                            ),
                          ),
                        ],
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

/// A translucent white pill used on the brand-gradient hero (chrome only).
class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Container(
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
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                textScaler: A11y.resolveTextScaler(context),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Lays out quick-action cards in a responsive grid: two columns on phone
/// widths, three on wider (tablet/rail) layouts. Uses a `Wrap` so it never
/// overflows and sizes naturally with dynamic text scaling.
class _QuickActionGrid extends StatelessWidget {
  const _QuickActionGrid({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = ClaraTokens.spaceMd;
        final maxWidth = constraints.maxWidth;
        final columns = maxWidth >= 600 ? 3 : 2;
        final itemWidth = (maxWidth - spacing * (columns - 1)) / columns;

        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final child in children)
              SizedBox(width: itemWidth, child: child),
          ],
        );
      },
    );
  }
}

/// A single quick-action card: a tappable liquid-glass chrome surface with a
/// tinted leading icon, a Vietnamese title, and a short supporting subtitle.
///
/// These are navigation affordances (labels/subtitles are chrome copy, not
/// clinical content), so they render on [GlassSurface]. When the ambient
/// [GlassScope] is disabled the surface falls back to the same opaque squircle,
/// so contrast and layout are preserved. The whole surface is the tap target
/// (announced as a button via [A11yLabeled]) and far exceeds the 48dp minimum.
class _QuickActionCard extends StatelessWidget {
  const _QuickActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.accent,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  /// Optional per-tool accent color for the icon tile so the grid reads as a
  /// set of distinct tools rather than a wall of identical blue cards. Falls
  /// back to the scheme primary when null. Decorative only (title text carries
  /// the meaning), so it never affects contrast of the label.
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    final textScaler = A11y.resolveTextScaler(context);
    final tileColor = accent ?? scheme.primary;

    return A11yLabeled(
      label: title,
      isButton: true,
      child: GlassSurface(
        radius: GlassTokens.radiusCard,
        blurSigma: GlassTokens.blurCard,
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(
              GlassTokens.radiusCard * GlassTokens.squircleFactor,
            ),
            child: Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Color.lerp(tileColor, Colors.white, 0.15)!,
                          tileColor,
                        ],
                      ),
                      borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                      boxShadow: [
                        BoxShadow(
                          color: tileColor.withValues(alpha: 0.35),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Icon(
                      icon,
                      color: Colors.white,
                      size: 24,
                    ),
                  ),
                  const SizedBox(height: ClaraTokens.spaceMd),
                  Text(
                    title,
                    style: textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                    textScaler: textScaler,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: ClaraTokens.spaceXs),
                  Text(
                    subtitle,
                    style: textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                    textScaler: textScaler,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// An "at-a-glance" row of small glass stat chips built ONLY from data the
/// role-scoped summary already carries — the API health status and the number
/// of tools this role can reach. No extra network call and no PII; a stat with
/// no real backing is simply omitted by the caller.
class _AtAGlanceRow extends StatelessWidget {
  const _AtAGlanceRow({required this.apiHealthy, required this.toolCount});

  /// Whether the summary reported the API as healthy (`api_health.status`).
  final bool apiHealthy;

  /// The number of quick-action tools currently available to this role.
  final int toolCount;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatChip(
            child: StatusByText(
              label: apiHealthy ? 'Hệ thống ổn định' : 'Đang kiểm tra',
              level: apiHealthy
                  ? A11yStatusLevel.success
                  : A11yStatusLevel.warning,
              semanticsPrefix: 'Trạng thái hệ thống',
            ),
          ),
        ),
        const SizedBox(width: ClaraTokens.spaceMd),
        Expanded(
          child: _StatChip(
            child: _StatValue(
              value: '$toolCount',
              label: 'công cụ khả dụng',
            ),
          ),
        ),
      ],
    );
  }
}

/// A compact glass chrome chip hosting a single at-a-glance stat.
class _StatChip extends StatelessWidget {
  const _StatChip({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return GlassSurface(
      radius: GlassTokens.radiusControl,
      blurSigma: GlassTokens.blurCard,
      fill: GlassFill.thin,
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceSm,
      ),
      child: Align(alignment: Alignment.centerLeft, child: child),
    );
  }
}

/// A numeric stat: a prominent value over a muted Vietnamese caption.
class _StatValue extends StatelessWidget {
  const _StatValue({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);

    return Semantics(
      label: '$value $label',
      container: true,
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(
              value,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
                color: scheme.primary,
              ),
              textScaler: textScaler,
            ),
            const SizedBox(width: ClaraTokens.spaceXs),
            Flexible(
              child: Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
                textScaler: textScaler,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A prominent, full-width primary call-to-action inviting the user to ask
/// CLARA a question — the single most useful action for this audience. Pure
/// navigation chrome (no clinical content); the whole surface is one large tap
/// target announced as a button.
class _PrimaryChatCta extends StatelessWidget {
  const _PrimaryChatCta({
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    final textScaler = A11y.resolveTextScaler(context);
    final radius = BorderRadius.circular(
      GlassTokens.radiusCard * GlassTokens.squircleFactor,
    );

    return A11yLabeled(
      label: title,
      isButton: true,
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          onTap: onTap,
          borderRadius: radius,
          child: Ink(
            decoration: BoxDecoration(
              borderRadius: radius,
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [
                  scheme.primary,
                  Color.lerp(scheme.primary, const Color(0xFF7C3AED), 0.55)!,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: scheme.primary.withValues(alpha: 0.28),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.20),
                      borderRadius:
                          BorderRadius.circular(GlassTokens.radiusPill),
                    ),
                    child: const ExcludeSemantics(
                      child: Icon(Icons.auto_awesome,
                          color: Colors.white, size: 26),
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceMd),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          title,
                          style: textTheme.titleMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                          ),
                          textScaler: textScaler,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          subtitle,
                          style: textTheme.bodySmall?.copyWith(
                            color: Colors.white.withValues(alpha: 0.88),
                          ),
                          textScaler: textScaler,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  const ExcludeSemantics(
                    child: Icon(Icons.arrow_forward_rounded,
                        color: Colors.white, size: 22),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A rotating daily wellness tip: general, non-clinical encouragement so the
/// Home feels alive on every open. Deterministic (keyed off the calendar day)
/// so it is stable within a day and testable; it NEVER makes a medical claim or
/// fabricates data, and stays clearly in the "supports decisions only" framing.
class _DailyTipCard extends StatelessWidget {
  const _DailyTipCard();

  /// General wellness prompts — deliberately non-diagnostic and non-prescriptive
  /// (hydration, sleep, movement, medication organization, check-in prep).
  static const List<({IconData icon, String text})> _tips = [
    (
      icon: Icons.local_drink_outlined,
      text: 'Uống đủ nước trong ngày giúp cơ thể tỉnh táo và khỏe khoắn hơn.'
    ),
    (
      icon: Icons.bedtime_outlined,
      text: 'Ngủ đủ giấc và đúng giờ là nền tảng cho sức khỏe lâu dài.'
    ),
    (
      icon: Icons.directions_walk_outlined,
      text: 'Vận động nhẹ mỗi ngày, dù chỉ vài phút, đều có ích cho tim mạch.'
    ),
    (
      icon: Icons.medication_outlined,
      text: 'Sắp xếp thuốc theo lịch giúp bạn dùng đúng liều, đúng giờ.'
    ),
    (
      icon: Icons.event_note_outlined,
      text:
          'Ghi lại triệu chứng trước khi đi khám giúp bác sĩ hiểu bạn nhanh hơn.'
    ),
    (
      icon: Icons.self_improvement_outlined,
      text: 'Dành ít phút hít thở sâu có thể giúp giảm căng thẳng trong ngày.'
    ),
    (
      icon: Icons.restaurant_outlined,
      text: 'Bữa ăn cân bằng rau, đạm và tinh bột hỗ trợ năng lượng ổn định.'
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    final textScaler = A11y.resolveTextScaler(context);

    final now = DateTime.now();
    final dayIndex = now.difference(DateTime(2020)).inDays;
    final tip = _tips[dayIndex % _tips.length];

    return A11yLabeled(
      label: 'Gợi ý hôm nay: ${tip.text}',
      child: GlassSurface(
        radius: GlassTokens.radiusCard,
        blurSigma: GlassTokens.blurCard,
        fill: GlassFill.thin,
        padding: const EdgeInsets.all(ClaraTokens.spaceMd),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: scheme.primary.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
              ),
              child: ExcludeSemantics(
                child: Icon(tip.icon, color: scheme.primary, size: 22),
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Gợi ý hôm nay',
                    style: textTheme.labelSmall?.copyWith(
                      color: scheme.primary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.4,
                    ),
                    textScaler: textScaler,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    tip.text,
                    style: textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurface,
                    ),
                    textScaler: textScaler,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
