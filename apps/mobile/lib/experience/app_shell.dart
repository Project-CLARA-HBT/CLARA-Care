// Adaptive app shell for CLARA_Mobile Experience_V2 (Requirements 3.1–3.4).
//
// One scaffold that adapts its primary navigation to the available width:
//
//   * Compact (phone) widths — `width < 600` — render a bottom
//     [NavigationBar] beneath the active destination's body.
//   * Medium / expanded (tablet / large) widths — `width >= 600` — render a
//     side [NavigationRail] + a [VerticalDivider] + the active body in an
//     [Expanded] region.
//
// The breakpoint is resolved per build from [LayoutBuilder] constraints, so the
// shell flips live on resize/rotation. The currently selected destination is
// held in [State] (not derived from width), so it is **preserved across width
// and orientation changes** (Requirement 3.2): a relayout rebuilds the chrome
// around the same `selectedIndex`, it never resets it.
//
// Accessibility & motion (Requirements 3.3, 3.4):
//   * Every navigation control is guaranteed a ≥48dp tap target via
//     [MinTapTarget], and the active body region is labeled with the current
//     destination's name via [A11yLabeled] so assistive tech announces the
//     screen the user landed on. The `NavigationBar`/`NavigationRail`
//     destinations already announce their own labels, so we deliberately do
//     **not** re-label the individual tappable icons — that would double-
//     announce. The icon stays decorative (the destination owns the label) and
//     the body carries the region label.
//   * The body swaps through an [AnimatedSwitcher] whose duration is resolved
//     by [A11y.resolveMotionDuration] against [ClaraTokens.motionMedium], so it
//     collapses to `Duration.zero` (instant) under reduced motion. A fade
//     never blocks or delays input — the new body is interactive immediately.
//
// Pure UI: no analytics, no I/O, no new dependency. Destinations carry their
// own body widget; the shell only owns selection + layout.

import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../theme/tokens.dart';

/// Width (logical px) at and above which the shell switches from the compact
/// bottom [NavigationBar] to the medium/expanded side [NavigationRail]
/// (Requirement 3.1).
const double kAppShellRailBreakpoint = 600.0;

/// A single primary destination in the [AppShell] (Requirement 3.2).
///
/// Pure data: an [icon] (and an optional [selectedIcon] variant shown when the
/// destination is active), a screen-reader/visible [label], and the [body]
/// widget rendered when the destination is selected. No I/O, no analytics.
@immutable
class ShellDestination {
  const ShellDestination({
    required this.icon,
    required this.label,
    required this.body,
    this.selectedIcon,
  });

  /// Icon shown when the destination is unselected (and the fallback when
  /// [selectedIcon] is null).
  final IconData icon;

  /// Optional icon shown when the destination is selected; falls back to
  /// [icon] when null.
  final IconData? selectedIcon;

  /// Human-readable destination label (Vietnamese-first at the call site).
  /// Announced once by the navigation control and reused as the body region
  /// label.
  final String label;

  /// The destination's body, rendered in the content region when selected.
  final Widget body;

  /// The icon to show given the destination's [selected] state.
  IconData iconFor({required bool selected}) =>
      selected ? (selectedIcon ?? icon) : icon;
}

/// An adaptive navigation scaffold that hosts a set of [ShellDestination]s
/// (Requirements 3.1–3.4).
///
/// Holds the selected index in [State] so it survives relayout (resize /
/// orientation), and renders a bottom [NavigationBar] on compact widths or a
/// side [NavigationRail] on medium/expanded widths, with the active body
/// swapped through a reduced-motion-aware [AnimatedSwitcher].
///
/// ```dart
/// AppShell(
///   initialIndex: 0,
///   destinations: const [
///     ShellDestination(icon: Icons.home_outlined, selectedIcon: Icons.home,
///         label: 'Trang chủ', body: HomeScreen()),
///     ShellDestination(icon: Icons.settings_outlined, selectedIcon: Icons.settings,
///         label: 'Cài đặt', body: SettingsScreen()),
///   ],
/// );
/// ```
class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.destinations,
    this.initialIndex = 0,
  }) : assert(destinations.length > 0, 'AppShell needs at least one destination');

  /// The primary destinations, in display order. Must be non-empty.
  final List<ShellDestination> destinations;

  /// The destination selected on first build. Clamped into range so an
  /// out-of-bounds value degrades gracefully to the nearest valid index.
  final int initialIndex;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  /// The selected destination index. Lives in [State] (not derived from width)
  /// so it is preserved across width/orientation changes (Requirement 3.2).
  late int _selectedIndex;

  @override
  void initState() {
    super.initState();
    _selectedIndex = _clampIndex(widget.initialIndex);
  }

  @override
  void didUpdateWidget(covariant AppShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Keep the selection valid if the destination set shrinks; never reset a
    // still-valid selection on rebuild.
    if (_selectedIndex >= widget.destinations.length) {
      _selectedIndex = _clampIndex(_selectedIndex);
    }
  }

  int _clampIndex(int index) =>
      index.clamp(0, widget.destinations.length - 1).toInt();

  void _onDestinationSelected(int index) {
    if (index == _selectedIndex) {
      return;
    }
    setState(() => _selectedIndex = _clampIndex(index));
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final useRail = constraints.maxWidth >= kAppShellRailBreakpoint;
        return useRail ? _buildRailScaffold(context) : _buildBarScaffold(context);
      },
    );
  }

  /// The active destination's body, swapped through a reduced-motion-aware
  /// [AnimatedSwitcher] and labeled as the current screen region. Keyed by the
  /// selected index so the switcher animates on change; the fade never blocks
  /// input (the incoming body is interactive immediately).
  Widget _buildBody(BuildContext context) {
    final destination = widget.destinations[_selectedIndex];
    final duration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionMedium);
    return A11yLabeled(
      label: destination.label,
      isHeader: true,
      child: AnimatedSwitcher(
        duration: duration,
        child: KeyedSubtree(
          key: ValueKey<int>(_selectedIndex),
          child: destination.body,
        ),
      ),
    );
  }

  /// Compact layout: body above a bottom [NavigationBar] (Requirement 3.1).
  Widget _buildBarScaffold(BuildContext context) {
    return Scaffold(
      body: SafeArea(child: _buildBody(context)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onDestinationSelected,
        destinations: [
          for (var i = 0; i < widget.destinations.length; i++)
            _barDestination(widget.destinations[i], selected: i == _selectedIndex),
        ],
      ),
    );
  }

  /// Medium/expanded layout: a side [NavigationRail] + divider + body
  /// (Requirement 3.1).
  Widget _buildRailScaffold(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            NavigationRail(
              selectedIndex: _selectedIndex,
              onDestinationSelected: _onDestinationSelected,
              labelType: NavigationRailLabelType.all,
              destinations: [
                for (var i = 0; i < widget.destinations.length; i++)
                  _railDestination(
                    widget.destinations[i],
                    selected: i == _selectedIndex,
                  ),
              ],
            ),
            const VerticalDivider(width: 1, thickness: 1),
            Expanded(child: _buildBody(context)),
          ],
        ),
      ),
    );
  }

  /// Builds a [NavigationDestination] whose icon is guaranteed a ≥48dp tap
  /// target via [MinTapTarget]. The label is owned by the destination (single
  /// announcement), so the icon is excluded from semantics to avoid a
  /// duplicate read (Requirement 3.3).
  NavigationDestination _barDestination(
    ShellDestination destination, {
    required bool selected,
  }) {
    return NavigationDestination(
      icon: _navIcon(destination.iconFor(selected: false)),
      selectedIcon: _navIcon(destination.iconFor(selected: true)),
      label: destination.label,
    );
  }

  /// Builds a [NavigationRailDestination] with the same ≥48dp + single-label
  /// guarantees as [_barDestination] (Requirement 3.3).
  NavigationRailDestination _railDestination(
    ShellDestination destination, {
    required bool selected,
  }) {
    return NavigationRailDestination(
      icon: _navIcon(destination.iconFor(selected: false)),
      selectedIcon: _navIcon(destination.iconFor(selected: true)),
      label: Text(destination.label),
    );
  }

  /// Wraps a nav [icon] in a [MinTapTarget] (≥48dp) and excludes it from
  /// semantics so the destination's own label is the single announcement
  /// (no double-announce — Requirement 3.3).
  Widget _navIcon(IconData icon) {
    return MinTapTarget(
      child: ExcludeSemantics(child: Icon(icon)),
    );
  }
}
