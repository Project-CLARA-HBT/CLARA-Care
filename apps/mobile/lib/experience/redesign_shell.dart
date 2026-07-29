// Adaptive navigation shell for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 2 (restructured information architecture
// with a centered circular Chat action).
//
// One scaffold that adapts its primary navigation to the available width:
//
//   * Compact (phone) widths — `width < 600` — render a custom bottom bar with
//     FOUR flanking destinations and a raised, circular, brand-filled **Chat**
//     action docked at the horizontal center (a `FloatingActionButton` over a
//     notched `BottomAppBar`). The center Chat action is always present and
//     always routes to Chat (Requirement 2.1, 2.2).
//   * Medium / expanded (tablet / large) widths — `width >= 600` — render a
//     side [NavigationRail] whose FIRST item is Chat (kept prominent), then the
//     flanking destinations, with the active body in an [Expanded] region.
//
// The breakpoint (600dp) and the "selection preserved across relayout"
// guarantee match the existing `AppShell` (Requirement 2.3): the selected index
// lives in [State] (not derived from width), so a resize/rotation rebuilds the
// chrome around the same selection, never resetting it.
//
// Accessibility & motion (inherits the app's a11y discipline):
//   * Every navigation control is guaranteed a ≥48dp tap target via
//     [MinTapTarget], and the active body region is labeled with the current
//     destination's name via [A11yLabeled] so assistive tech announces the
//     screen the user landed on. Nav icons are decorative (the destination owns
//     the label) to avoid a double-announce.
//   * The body swaps through an [AnimatedSwitcher] whose duration is resolved by
//     [A11y.resolveMotionDuration] against [ClaraTokens.motionMedium], so it
//     collapses to `Duration.zero` under reduced motion.
//
// Pure UI: no analytics, no I/O, no new dependency. Destinations carry their own
// body widget; the shell only owns selection + layout. The center Chat action's
// body is supplied separately so Chat is never one of the flanking slots.

import 'package:flutter/material.dart';

import '../core/a11y.dart';
import '../theme/glass/glass_surface.dart';
import '../theme/glass/glass_tokens.dart';
import '../theme/tokens.dart';

/// Width (logical px) at and above which the shell switches from the compact
/// bottom bar to the side [NavigationRail] (Requirement 2.3). Matches the
/// existing `AppShell` breakpoint.
const double kRedesignShellRailBreakpoint = 600.0;

/// Diameter (logical px) of the raised circular center Chat action.
const double kRedesignChatActionDiameter = 60.0;

/// A single flanking destination in the [RedesignShell] (Requirement 2.4).
///
/// Pure data: an [icon] (and optional [selectedIcon] shown when active), a
/// screen-reader/visible [label], and the [body] rendered when selected.
@immutable
class RedesignDestination {
  const RedesignDestination({
    required this.icon,
    required this.label,
    required this.body,
    this.selectedIcon,
  });

  /// Icon shown when unselected (and the fallback when [selectedIcon] is null).
  final IconData icon;

  /// Optional icon shown when selected; falls back to [icon].
  final IconData? selectedIcon;

  /// Human-readable destination label (Vietnamese-first at the call site).
  final String label;

  /// The destination's body, rendered in the content region when selected.
  final Widget body;

  /// The icon to show given the destination's [selected] state.
  IconData iconFor({required bool selected}) =>
      selected ? (selectedIcon ?? icon) : icon;
}

/// An adaptive navigation scaffold with a centered circular Chat action.
///
/// Holds the selected slot in [State] so it survives relayout. On compact
/// widths it renders a custom bottom bar (flanking destinations + docked
/// circular Chat FAB); on medium/expanded widths a [NavigationRail] with Chat
/// as the first item.
class RedesignShell extends StatefulWidget {
  const RedesignShell({
    super.key,
    required this.destinations,
    required this.chatBody,
    this.chatLabel = 'Trò chuyện',
    this.chatIcon = Icons.forum_rounded,
    this.initialIndex = 0,
  }) : assert(
          destinations.length > 0,
          'RedesignShell needs at least one flanking destination',
        );

  /// The flanking primary destinations, in display order. On compact widths
  /// they are split evenly to the left and right of the center Chat action.
  final List<RedesignDestination> destinations;

  /// The Chat surface body, opened by the center circular action. Chat is the
  /// navigation anchor and is never one of the flanking [destinations].
  final Widget chatBody;

  /// Vietnamese-first label for the center Chat action.
  final String chatLabel;

  /// Icon for the center Chat action.
  final IconData chatIcon;

  /// The flanking destination selected on first build (0-based into
  /// [destinations]). Clamped so an out-of-range value degrades gracefully.
  final int initialIndex;

  @override
  State<RedesignShell> createState() => _RedesignShellState();
}

class _RedesignShellState extends State<RedesignShell> {
  /// The selected slot. `-1` means the center Chat action is active; `0..n-1`
  /// selects a flanking destination. Lives in [State] so it is preserved across
  /// width/orientation changes (Requirement 2.3).
  late int _selectedIndex;

  /// Sentinel for "the center Chat action is selected".
  static const int _chatIndex = -1;

  @override
  void initState() {
    super.initState();
    _selectedIndex = _clampIndex(widget.initialIndex);
  }

  @override
  void didUpdateWidget(covariant RedesignShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_selectedIndex != _chatIndex &&
        _selectedIndex >= widget.destinations.length) {
      _selectedIndex = _clampIndex(_selectedIndex);
    }
  }

  int _clampIndex(int index) =>
      index.clamp(0, widget.destinations.length - 1).toInt();

  bool get _isChatSelected => _selectedIndex == _chatIndex;

  void _selectDestination(int index) {
    final next = _clampIndex(index);
    if (next == _selectedIndex) {
      return;
    }
    setState(() => _selectedIndex = next);
  }

  void _selectChat() {
    if (_isChatSelected) {
      return;
    }
    setState(() => _selectedIndex = _chatIndex);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final useRail = constraints.maxWidth >= kRedesignShellRailBreakpoint;
        return useRail
            ? _buildRailScaffold(context)
            : _buildBarScaffold(context);
      },
    );
  }

  /// The active body (Chat when the center action is selected, otherwise the
  /// selected flanking destination), swapped through a reduced-motion-aware
  /// [AnimatedSwitcher] and labeled as the current screen region.
  Widget _buildBody(BuildContext context) {
    final Widget body;
    final String label;
    if (_isChatSelected) {
      body = widget.chatBody;
      label = widget.chatLabel;
    } else {
      final destination = widget.destinations[_selectedIndex];
      body = destination.body;
      label = destination.label;
    }

    final duration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionMedium);
    return A11yLabeled(
      label: label,
      isHeader: true,
      child: AnimatedSwitcher(
        duration: duration,
        child: KeyedSubtree(
          key: ValueKey<int>(_selectedIndex),
          child: body,
        ),
      ),
    );
  }

  // --- Compact: bottom bar with docked circular Chat action ------------------

  Widget _buildBarScaffold(BuildContext context) {
    // `extendBody: true` lets the content flow UNDER the floating glass nav pill
    // so its backdrop blur samples real content (the iOS-26 liquid-glass look).
    return Scaffold(
      extendBody: true,
      body: SafeArea(bottom: false, child: _buildBody(context)),
      bottomNavigationBar: _buildFloatingNav(context),
    );
  }

  // --- Compact: floating liquid-glass nav pill with a raised Chat button -----

  /// A floating, pill-shaped liquid-glass navigation bar (iOS-26 style): the
  /// flanking destinations sit on a translucent, blurred, squircle pill inset
  /// from the screen edges, with a raised circular brand Chat button breaking
  /// out of the pill's center. Content scrolls underneath (extendBody), so the
  /// glass samples real pixels. When the ambient [GlassScope] is off the pill
  /// renders opaque with identical geometry (accessible fallback).
  Widget _buildFloatingNav(BuildContext context) {
    final count = widget.destinations.length;
    final leftCount = count ~/ 2;

    final leftItems = <Widget>[
      for (var i = 0; i < leftCount; i++)
        Expanded(child: _buildBarItem(context, i)),
    ];
    final rightItems = <Widget>[
      for (var i = leftCount; i < count; i++)
        Expanded(child: _buildBarItem(context, i)),
    ];

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          0,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceSm,
        ),
        child: SizedBox(
          height: 72,
          // The Chat button is 64dp and rises above the pill, so the Stack must
          // not clip. The pill is bottom-aligned; the button is centered on top.
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.bottomCenter,
            children: [
              // The glass pill (flanking destinations), height 60, leaving a gap
              // in the middle for the raised Chat button.
              Align(
                alignment: Alignment.bottomCenter,
                child: GlassSurface(
                  blurSigma: GlassTokens.blurNav,
                  radius: GlassTokens.radiusPill,
                  fill: GlassFill.regular,
                  padding: EdgeInsets.zero,
                  child: SizedBox(
                    height: 60,
                    child: Row(
                      children: [
                        const SizedBox(width: ClaraTokens.spaceSm),
                        ...leftItems,
                        const SizedBox(width: kRedesignChatActionDiameter + 8),
                        ...rightItems,
                        const SizedBox(width: ClaraTokens.spaceSm),
                      ],
                    ),
                  ),
                ),
              ),
              // The raised circular Chat action, centered and breaking out the top.
              Align(
                alignment: Alignment.topCenter,
                child: _buildChatAction(context),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// The raised, circular, brand-filled Chat action floating above the nav pill
  /// (Requirement 2.1, 2.2). Always present; always routes to Chat.
  ///
  /// As the app's primary action it stays a high-contrast, opaque semantic
  /// brand surface. Avoid glass highlights and colored glow here: they conflict
  /// with the calm light-mode foundation and make the control render
  /// differently across brightness modes.
  Widget _buildChatAction(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final selected = _isChatSelected;
    return Semantics(
      button: true,
      selected: selected,
      label: widget.chatLabel,
      child: GestureDetector(
        onTap: _selectChat,
        child: Container(
          width: kRedesignChatActionDiameter,
          height: kRedesignChatActionDiameter,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: scheme.primary,
            border: Border.all(
              color: scheme.outlineVariant,
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: scheme.shadow.withValues(alpha: 0.14),
                blurRadius: 8,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: ExcludeSemantics(
            child: Icon(
              widget.chatIcon,
              size: 28,
              color: scheme.onPrimary,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBarItem(BuildContext context, int index) {
    final destination = widget.destinations[index];
    final selected = !_isChatSelected && index == _selectedIndex;
    final scheme = Theme.of(context).colorScheme;
    final color = selected ? scheme.primary : scheme.onSurfaceVariant;

    return Semantics(
      button: true,
      selected: selected,
      label: destination.label,
      child: InkWell(
        onTap: () => _selectDestination(index),
        customBorder: const StadiumBorder(),
        child: MinTapTarget(
          child: ExcludeSemantics(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // A pill highlight behind the selected icon (iOS-26 style).
                AnimatedContainer(
                  duration: A11y.resolveMotionDuration(
                    context,
                    ClaraTokens.motionFast,
                  ),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: selected
                        ? scheme.primary.withValues(alpha: 0.14)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(GlassTokens.radiusPill),
                  ),
                  child: Icon(
                    destination.iconFor(selected: selected),
                    size: 22,
                    color: color,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  destination.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: color,
                        fontWeight:
                            selected ? FontWeight.w600 : FontWeight.w500,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // --- Medium/expanded: navigation rail with Chat first ----------------------

  Widget _buildRailScaffold(BuildContext context) {
    // Rail index 0 is Chat; rail indices 1..n map to destinations[0..n-1].
    final railSelected = _isChatSelected ? 0 : _selectedIndex + 1;

    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            NavigationRail(
              selectedIndex: railSelected,
              onDestinationSelected: (railIndex) {
                if (railIndex == 0) {
                  _selectChat();
                } else {
                  _selectDestination(railIndex - 1);
                }
              },
              labelType: NavigationRailLabelType.all,
              leading: _buildRailChatLeading(context),
              destinations: [
                // Index 0: Chat (kept prominent as the first rail item).
                NavigationRailDestination(
                  icon: _railIcon(widget.chatIcon),
                  selectedIcon: _railIcon(widget.chatIcon),
                  label: Text(widget.chatLabel),
                ),
                for (final destination in widget.destinations)
                  NavigationRailDestination(
                    icon: _railIcon(destination.iconFor(selected: false)),
                    selectedIcon:
                        _railIcon(destination.iconFor(selected: true)),
                    label: Text(destination.label),
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

  /// A small brand mark above the rail items to echo the compact center action.
  Widget _buildRailChatLeading(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
      child: SizedBox(height: 8),
    );
  }

  Widget _railIcon(IconData icon) {
    return MinTapTarget(child: ExcludeSemantics(child: Icon(icon)));
  }
}
