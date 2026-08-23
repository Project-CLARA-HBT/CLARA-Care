// Morphing Primary Dock for CLARA_Mobile Spatial Editorial Health
// (Spec v4 Section 5 & 6, SEH-052, SEH-053, SEH-057, SEH-058).
//
// The MorphingDock is the primary floating visual signature of the spatial shell.
// It is centered, role-adaptive, compact, content-aware, and capable of safe morphing
// across 5 distinct presentation states:
//
//   1. expanded: Full navigation dock with flanking destinations and center CLARA Orb.
//   2. compact: Condensed icon-only bar with minimal footprint.
//   3. orbOnly: Floating standalone CLARA Orb (e.g. during deep scroll).
//   4. contextual: Dedicated contextual controls (e.g. Scribe recording, custom bar).
//   5. hidden: Safely translated off-screen with escape/reveal affordance.
//
// Invariants:
//   * All interactive elements meet the ≥48dp touch target standard (WCAG 2.2 AA).
//   * State transitions honor reduced motion via `A11y.resolveMotionDuration`.
//   * Glassmorphism utilizes `GlassSurface` with automatic opaque fallback.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../redesign_shell.dart' show RedesignDestination;
import 'clara_orb.dart';

/// The 5 named presentation morph states of the dock (Spec v4 Section 6).
enum DockMorphState {
  /// Full navigation dock with all flanking destinations and the center CLARA Orb.
  expanded,

  /// Compact bar with condensed icon-only navigation.
  compact,

  /// Collapsed to the standalone CLARA Orb (e.g. deep scrolling).
  orbOnly,

  /// Specialized contextual controls replacing standard navigation.
  contextual,

  /// Dock translated off-screen with an accessible escape/restore affordance.
  hidden,
}

/// A floating, morphing navigation dock widget.
class MorphingDock extends StatelessWidget {
  const MorphingDock({
    super.key,
    required this.destinations,
    required this.selectedIndex,
    required this.onDestinationSelected,
    this.morphState = DockMorphState.expanded,
    this.orbState = ClaraOrbState.idle,
    this.onOrbTap,
    this.onOrbLongPress,
    this.orbLabel,
    this.contextualChild,
    this.onContextualClose,
    this.onToggleMorph,
    this.languageCode = 'vi',
    this.isChatActive = false,
    this.animateOrb = true,
  });

  /// The primary destinations in display order.
  final List<RedesignDestination> destinations;

  /// The active destination index (0..n-1).
  final int selectedIndex;

  /// Callback when a flanking destination is tapped.
  final ValueChanged<int> onDestinationSelected;

  /// Active morph state of the dock.
  final DockMorphState morphState;

  /// Current interaction state of the CLARA Orb.
  final ClaraOrbState orbState;

  /// Callback when the CLARA Orb is tapped.
  final VoidCallback? onOrbTap;

  /// Callback when the CLARA Orb is long-pressed.
  final VoidCallback? onOrbLongPress;

  /// Label for the CLARA Orb (defaults to 'Hỏi CLARA' / 'Ask CLARA').
  final String? orbLabel;

  /// Custom contextual widget displayed in [DockMorphState.contextual].
  final Widget? contextualChild;

  /// Callback to dismiss or close contextual mode.
  final VoidCallback? onContextualClose;

  /// Callback when a user triggers morph state toggle.
  final ValueChanged<DockMorphState>? onToggleMorph;

  /// UI language code for accessibility announcements.
  final String languageCode;

  /// Whether the center Chat/Orb is currently the active view.
  final bool isChatActive;

  /// Whether active repeating animation is enabled for the Orb.
  final bool animateOrb;

  @override
  Widget build(BuildContext context) {
    final motionDuration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionMedium);

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          0,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceSm,
        ),
        child: AnimatedSwitcher(
          duration: motionDuration,
          switchInCurve: Curves.easeOutCubic,
          switchOutCurve: Curves.easeInCubic,
          transitionBuilder: (child, animation) {
            return FadeTransition(
              opacity: animation,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, 0.15),
                  end: Offset.zero,
                ).animate(animation),
                child: child,
              ),
            );
          },
          child: _buildMorphContent(context),
        ),
      ),
    );
  }

  Widget _buildMorphContent(BuildContext context) {
    switch (morphState) {
      case DockMorphState.expanded:
        return KeyedSubtree(
          key: const ValueKey<String>('dock_expanded'),
          child: _buildExpandedDock(context),
        );

      case DockMorphState.compact:
        return KeyedSubtree(
          key: const ValueKey<String>('dock_compact'),
          child: _buildCompactDock(context),
        );

      case DockMorphState.orbOnly:
        return KeyedSubtree(
          key: const ValueKey<String>('dock_orb_only'),
          child: _buildOrbOnly(context),
        );

      case DockMorphState.contextual:
        return KeyedSubtree(
          key: const ValueKey<String>('dock_contextual'),
          child: _buildContextualDock(context),
        );

      case DockMorphState.hidden:
        return KeyedSubtree(
          key: const ValueKey<String>('dock_hidden'),
          child: _buildHiddenAffordance(context),
        );
    }
  }

  // --- 1. Expanded Dock ------------------------------------------------------

  Widget _buildExpandedDock(BuildContext context) {
    final count = destinations.length;
    final leftCount = count ~/ 2;

    final leftItems = <Widget>[
      for (var i = 0; i < leftCount; i++)
        Expanded(child: _buildDestinationItem(context, i, compact: false)),
    ];
    final rightItems = <Widget>[
      for (var i = leftCount; i < count; i++)
        Expanded(child: _buildDestinationItem(context, i, compact: false)),
    ];

    const orbDiameter = 58.0;

    return SizedBox(
      height: 72,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.bottomCenter,
        children: [
          // Glass Surface Pill
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
                    const SizedBox(width: orbDiameter + 10),
                    ...rightItems,
                    const SizedBox(width: ClaraTokens.spaceSm),
                  ],
                ),
              ),
            ),
          ),

          // Raised Center CLARA Orb
          Align(
            alignment: Alignment.topCenter,
            child: _buildOrbAction(context, size: orbDiameter),
          ),
        ],
      ),
    );
  }

  // --- 2. Compact Dock -------------------------------------------------------

  Widget _buildCompactDock(BuildContext context) {
    final count = destinations.length;
    final leftCount = count ~/ 2;

    final leftItems = <Widget>[
      for (var i = 0; i < leftCount; i++)
        _buildDestinationItem(context, i, compact: true),
    ];
    final rightItems = <Widget>[
      for (var i = leftCount; i < count; i++)
        _buildDestinationItem(context, i, compact: true),
    ];

    return Center(
      child: GlassSurface(
        blurSigma: GlassTokens.blurNav,
        radius: GlassTokens.radiusPill,
        fill: GlassFill.regular,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ...leftItems,
            const SizedBox(width: 8),
            _buildOrbAction(context, size: 44.0),
            const SizedBox(width: 8),
            ...rightItems,
          ],
        ),
      ),
    );
  }

  // --- 3. Orb Only -----------------------------------------------------------

  Widget _buildOrbOnly(BuildContext context) {
    return Center(
      child: _buildOrbAction(context, size: 60.0),
    );
  }

  // --- 4. Contextual Dock ----------------------------------------------------

  Widget _buildContextualDock(BuildContext context) {
    return Center(
      child: GlassSurface(
        blurSigma: GlassTokens.blurNav,
        radius: GlassTokens.radiusPill,
        fill: GlassFill.thick,
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (contextualChild != null)
              Flexible(child: contextualChild!)
            else
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const ClaraOrb(
                    size: 32,
                    state: ClaraOrbState.processing,
                    showGlow: false,
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  Text(
                    languageCode == 'en'
                        ? 'CLARA active task'
                        : 'Nhiệm vụ đang thực hiện',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
              ),
            if (onContextualClose != null) ...[
              const SizedBox(width: ClaraTokens.spaceSm),
              IconButton(
                icon: const Icon(Icons.close, size: 20),
                tooltip: languageCode == 'en' ? 'Close' : 'Đóng',
                onPressed: onContextualClose,
              ),
            ],
          ],
        ),
      ),
    );
  }

  // --- 5. Hidden Escape Affordance -------------------------------------------

  Widget _buildHiddenAffordance(BuildContext context) {
    return Center(
      child: MinTapTarget(
        minSize: A11y.minTapTargetDimension,
        child: GestureDetector(
          onTap: () => onToggleMorph?.call(DockMorphState.expanded),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.8),
              borderRadius: BorderRadius.circular(ClaraTokens.radiusPill),
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.keyboard_arrow_up,
                  size: 18,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
                const SizedBox(width: 4),
                Text(
                  languageCode == 'en' ? 'Show navigation' : 'Hiện thanh điều hướng',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // --- Destination Item Builder ----------------------------------------------

  Widget _buildDestinationItem(
    BuildContext context,
    int index, {
    required bool compact,
  }) {
    final destination = destinations[index];
    final isSelected = (!isChatActive) && selectedIndex == index;
    final colorScheme = Theme.of(context).colorScheme;

    final color = isSelected
        ? colorScheme.primary
        : colorScheme.onSurfaceVariant.withValues(alpha: 0.85);

    final iconData = destination.iconFor(selected: isSelected);

    if (compact) {
      return MinTapTarget(
        minSize: A11y.minTapTargetDimension,
        child: IconButton(
          icon: Icon(iconData, color: color, size: 22),
          tooltip: destination.label,
          onPressed: () => onDestinationSelected(index),
        ),
      );
    }

    return Semantics(
      button: true,
      selected: isSelected,
      label: destination.label,
      child: MinTapTarget(
        minSize: A11y.minTapTargetDimension,
        child: InkResponse(
          onTap: () => onDestinationSelected(index),
          radius: 28,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(iconData, color: color, size: 22),
              const SizedBox(height: 2),
              Text(
                destination.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: color,
                      fontSize: 10.5,
                      fontWeight:
                          isSelected ? FontWeight.w700 : FontWeight.w500,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOrbAction(BuildContext context, {required double size}) {
    final defaultOrbLabel =
        languageCode == 'en' ? 'Ask CLARA' : 'Hỏi CLARA';
    final effectiveOrbLabel = orbLabel ?? defaultOrbLabel;

    return ClaraOrb(
      state: isChatActive ? ClaraOrbState.ready : orbState,
      size: size,
      customLabel: effectiveOrbLabel,
      tooltip: effectiveOrbLabel,
      languageCode: languageCode,
      animate: animateOrb,
      onTap: onOrbTap,
      onLongPress: onOrbLongPress,
    );
  }
}
