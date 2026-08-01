// Modern role-aware Home for CLARA_Mobile Experience_V2 (Req 4.1, 4.2, 4.5).
//
// This is the polished landing surface that replaces the flat-list
// `DashboardScreen` when `MOBILE_EXPERIENCE_V2_ENABLED` is on. It renders a
// greeting header, a "Công cụ" section of role-aware quick-action `ClaraCard`s,
// a "Gần đây" recent-items region (placeholder for now), and a Personal Health
// Record card that is ALWAYS present for every authenticated role.
//
// Source of truth: this screen MIRRORS `lib/screens/dashboard_screen.dart`
// exactly for the summary load + gating semantics. It calls the same
// `mobile/summary` endpoint, builds ONE `MobileFeatureFlagResolver`, and gates
// each privileged quick-action with the identical fail-closed rules:
//
//   * Privileged quick-actions are derived ONLY from a successfully loaded,
//     role-scoped summary (a null/unloadable summary ⇒ none are shown).
//   * research / careguard / council via the summary `feature_flags` booleans.
//   * chat / selfMedCabinet / consentCenter / sharing via the resolver gates.
//   * scribe additionally requires the `doctor` role (`scribeEnabled && role ==
//     'doctor'`) so it is never reachable for any other role.
//   * the admin-only system-monitor surface requires `role == 'admin'` AND the
//     `system_monitor` flag — never derived for a non-admin role.
//   * PHR is ALWAYS reachable, independent of the summary (Requirement 4.5).
//
// The body is a single scrollable (`ListView`) and `_loadSummary` is exposed as
// a `Future<void>` refresh callback, so task 6.2 can wrap it in a
// `RefreshIndicator` and task 4.2 can swap the inline retry affordance for the
// shared `ErrorRetryView` without restructuring this file.
//
// Copy is Vietnamese-first with a calm, decision-support tone; analytics is a
// single coarse, no-PII screen-view event.

import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';
import '../screens/careguard_screen.dart';
import '../screens/careguard_cabinet_screen.dart';
import '../screens/chat_screen.dart';
import '../screens/consent_center_screen.dart';
import '../screens/council_screen.dart';
import '../screens/council_case_screen.dart';
import '../screens/phr_screen.dart';
import '../screens/research_screen.dart';
import '../screens/scribe_screen.dart';
import '../screens/selfmed_cabinet_screen.dart';
import '../theme/components/clara_card.dart';
import '../theme/components/section_header.dart';
import '../theme/tokens.dart';
import '../widgets/error_retry_view.dart';
import 'states/empty_state.dart';
import 'states/skeleton.dart';

/// Coarse, no-PII screen-view event name for the modern Home.
///
/// Passed as a string literal (rather than a `MobileAnalyticsEvents` constant)
/// because `analytics.dart` is owned by another concern and is not edited here.
/// It carries no PII and identifies only the surface viewed.
const String kMobileHomeViewedEvent = 'mobile_home_viewed';

/// The modern, role-aware Home surface for Experience_V2.
///
/// Takes the same dependencies as `DashboardScreen` ([apiClient],
/// [sessionStore]) so the app shell can construct it identically.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loadingSummary = false;
  String? _summaryError;
  Map<String, dynamic>? _summary;

  @override
  void initState() {
    super.initState();
    // Coarse, no-PII screen-view through the shared consent/PII-guarded client.
    getAnalyticsClient().captureScreenView(kMobileHomeViewedEvent);
    _loadSummary();
  }

  /// Whether the role-scoped `mobile/summary` was successfully loaded.
  ///
  /// All privileged quick-actions and the admin-only system-monitor surface are
  /// gated on this so the Home fails CLOSED (Requirement 4.3): a null summary
  /// (load failed, in-flight, or no session) ⇒ no privileged tools are derived.
  bool get _summaryLoaded => _summary != null;

  /// The authenticated role, defaulting to the least-privileged `normal`.
  String get _role => widget.sessionStore.role ?? 'normal';

  /// Reads a boolean `feature_flags` entry from the loaded summary, mirroring
  /// `dashboard_screen.dart`'s `_featureEnabled`: an unloadable summary, a
  /// non-map `feature_flags`, a missing key, or a non-`true` value all resolve
  /// to `false` (fail-closed).
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

  /// Loads the role-scoped `mobile/summary` exactly like `DashboardScreen`.
  ///
  /// Exposed as a `Future<void>` so it can be used directly as the
  /// `RefreshIndicator.onRefresh` callback (task 6.2) and the retry affordance
  /// (task 4.2). Handles `ApiException` plus a generic catch with a
  /// Vietnamese-first, PII-free message, and guards every `setState` with
  /// `mounted`.
  Future<void> _loadSummary() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }

    setState(() {
      _loadingSummary = true;
      _summaryError = null;
    });

    try {
      final data = await widget.apiClient.getMobileSummary(accessToken: token);
      if (!mounted) {
        return;
      }
      setState(() {
        _summary = data;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _summaryError = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _summaryError = 'Không thể tải dữ liệu trang chính. Vui lòng thử lại.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loadingSummary = false;
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
    final summaryLoaded = _summaryLoaded;

    // ONE resolver built from the loaded role-scoped summary, reused for every
    // gate and for the PHR card — exactly as `DashboardScreen` does. A
    // null/unloadable summary resolves every gate to its build-time default
    // (all OFF in a normal build), so privileged surfaces stay dark (fail
    // closed).
    final resolver = MobileFeatureFlagResolver(summary: _summary);

    // Privileged quick-actions are derived ONLY from a successfully loaded,
    // role-scoped summary (Requirement 4.2); when the summary is unavailable we
    // fail closed and show none of them (Requirement 4.3).
    final canResearch = _featureEnabled('research');
    final canCareguard = _featureEnabled('careguard');
    final canCouncil = _featureEnabled('council');
    // Scribe is additionally restricted to the doctor role: the gate opens only
    // when the flag is on AND the authenticated role is `doctor`.
    final canScribe = resolver.scribeEnabled && role == 'doctor';

    // Once a load attempt has settled without yielding a summary, offer a
    // retry in place of the privileged quick-actions (fail closed,
    // Requirement 4.3) using the shared `ErrorRetryView` (task 4.2).
    final showSummaryRetry = !summaryLoaded && !_loadingSummary;

    // Initial load: a skeleton stands in for the tools grid while the very
    // first `mobile/summary` is in-flight (Requirement 6.1). On a pull-to-
    // refresh with content already shown, the `RefreshIndicator` spinner is
    // enough — we keep the existing grid rather than blanking the screen.
    final showInitialSkeleton = _loadingSummary && !summaryLoaded;

    final quickActions = <Widget>[
      if (summaryLoaded) ...[
        if (canResearch)
          _QuickActionCard(
            icon: Icons.science,
            title: 'Nghiên cứu y khoa',
            subtitle: 'Tìm hiểu sâu với dẫn chứng',
            onTap: () => _openScreen(
              ResearchScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                deepResearchEnabled: _featureEnabled('research_mobile_deep'),
              ),
            ),
          ),
        if (canCareguard)
          _QuickActionCard(
            icon: Icons.medication,
            title: 'Kiểm tra tương tác thuốc',
            subtitle: 'Phân tích an toàn cho tủ thuốc',
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
            onTap: () => _openScreen(
              CareguardCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
              ),
            ),
          ),
        if (canCouncil)
          _QuickActionCard(
            icon: Icons.groups,
            title: 'Hội chẩn AI',
            subtitle: 'Tổng hợp ý kiến nhiều chuyên khoa',
            onTap: () => _openScreen(
              // Council mobile parity: when COUNCIL_MOBILE_PARITY_ENABLED is on
              // route to the case-based flow, otherwise the legacy run screen —
              // mirroring `DashboardScreen`.
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
        if (resolver.chatEnabled)
          _QuickActionCard(
            icon: Icons.chat_bubble_outline,
            title: 'Trò chuyện',
            subtitle: 'Hỏi đáp cùng CLARA',
            onTap: () => _openScreen(
              ChatScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                resolver: resolver,
                polished: resolver.uxPolishEnabled,
              ),
            ),
          ),
        if (resolver.selfMedCabinetEnabled)
          _QuickActionCard(
            icon: Icons.medication_outlined,
            title: 'Tủ thuốc tự kê',
            subtitle: 'Quản lý thuốc & kiểm tra tương tác',
            onTap: () => _openScreen(
              SelfMedCabinetScreen(
                apiClient: widget.apiClient,
                sessionStore: widget.sessionStore,
                featureFlags: resolver,
              ),
            ),
          ),
        if (canScribe)
          _QuickActionCard(
            icon: Icons.mic_none,
            title: 'Ghi chú lâm sàng',
            subtitle: 'Ghi âm và tạo ghi chú SOAP',
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
            onTap: () => _openScreen(
              ConsentCenterScreen(
                apiClient: widget.apiClient,
                resolver: resolver,
                sessionStore: widget.sessionStore,
              ),
            ),
          ),
      ],
      // PHR is available to every authenticated role independent of the
      // summary, so its card is ALWAYS present (Requirement 4.5).
      _QuickActionCard(
        icon: Icons.folder_shared,
        title: 'Hồ sơ sức khỏe',
        subtitle: 'Xem và cập nhật hồ sơ tự khai',
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
      // Pull-to-refresh on the primary scrollable surface (Requirement 6.5).
      // The list is ALWAYS scrollable so the gesture works even when the
      // content is short, and `_loadSummary` doubles as the refresh callback.
      //
      // TODO(req-6.4 offline): once `HomeScreen` is given a
      // `ConnectivityService` (the app shell constructs it without one today),
      // surface `OfflineBanner(connectivity: …, onRetry: _loadSummary)` at the
      // top of this body. It is omitted here rather than fabricating a
      // connectivity stream this screen does not own — keep wiring additive.
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadSummary,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceMd),
            children: [
              _GreetingHeader(
                role: role,
                email: widget.sessionStore.email,
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              const SectionHeader(title: 'Công cụ'),
              // Initial load shows a polished skeleton instead of a bare
              // spinner or blank region (Requirement 6.1); once loaded (or on
              // refresh with existing content) the real tools grid is shown.
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
              // privileged quick-actions and offers a retry via the shared
              // `ErrorRetryView` (Requirements 4.3, 6.4).
              if (showSummaryRetry) ...[
                const SizedBox(height: ClaraTokens.spaceMd),
                ErrorRetryView(
                  message: _summaryError ??
                      'Không thể tải danh sách công cụ. Vui lòng thử lại.',
                  onRetry: _loadSummary,
                ),
              ],
              const SizedBox(height: ClaraTokens.spaceLg),
              const SectionHeader(title: 'Gần đây'),
              // The recent-items region has no data yet, so it shows a
              // friendly Vietnamese-first empty state (Requirement 6.2).
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
                child: ClaraEmptyState(
                  icon: Icons.history,
                  title: 'Chưa có hoạt động gần đây',
                  message: 'Các hoạt động gần đây của bạn sẽ xuất hiện ở đây.',
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

/// Greeting header: a warm Vietnamese-first welcome plus the signed-in role and
/// email, rendered in a static `ClaraCard`.
class _GreetingHeader extends StatelessWidget {
  const _GreetingHeader({required this.role, this.email});

  final String role;
  final String? email;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final identity = (email != null && email!.isNotEmpty) ? email! : '-';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
      child: ClaraCard.static_(
        semanticLabel: 'Xin chào, vai trò $role',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Xin chào', style: textTheme.headlineSmall),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(identity, style: textTheme.titleMedium),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text('Vai trò: $role', style: textTheme.bodyMedium),
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

/// A single quick-action card: a tappable `ClaraCard` showing an icon, a
/// Vietnamese title, and a short supporting subtitle. The card's
/// `semanticLabel` is the [title] so screen readers announce it as a button.
class _QuickActionCard extends StatelessWidget {
  const _QuickActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return ClaraCard(
      onTap: onTap,
      semanticLabel: title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: colorScheme.primary, size: 28),
          const SizedBox(height: ClaraTokens.spaceSm),
          Text(
            title,
            style: textTheme.titleMedium,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            subtitle,
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
