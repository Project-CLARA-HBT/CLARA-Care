// Adaptive Mobile Shell for CLARA_Mobile Spatial Editorial Health
// (Spec v4 Section 40, SEH-050, SEH-051, SEH-140, SEH-141, SEH-142).
//
// Replaces the legacy shell architecture with the unified Spatial Editorial
// Health foundation:
//
//   AdaptiveClaraShell
//   ├── ContextBar (top status, mode switch, breadcrumbs, safety context)
//   ├── DestinationHost (content canvas with editorial page transitions)
//   ├── MorphingDock (5-state floating navigation dock)
//   │   └── ClaraOrb (persistent 7-state interaction object)
//   └── OverlayHost (transient sheets, command palette, toasts)
//
// Responsiveness:
//   * Compact (< 600dp): Floating glass ContextBar at top, flowing content canvas,
//     and floating MorphingDock at bottom.
//   * Expanded (>= 600dp): Spatial NavigationRail with top ContextBar and
//     expanded content canvas.
//
// Invariants:
//   * Selection is preserved across relayout and orientation changes.
//   * All interactive controls meet the ≥48dp touch target threshold (WCAG 2.2 AA).
//   * Non-essential animation collapses to Duration.zero under reduced motion.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../presentation_mode.dart';
import '../redesign_shell.dart' show RedesignDestination;
import 'clara_orb.dart';
import 'morphing_dock.dart';

/// Width (logical px) at and above which the shell adapts from bottom dock
/// to side navigation rail.
const double kSpatialShellRailBreakpoint = 600.0;

/// Top floating or docked context bar for the spatial shell.
class ContextBar extends StatelessWidget {
  const ContextBar({
    super.key,
    this.title,
    this.mode = PresentationMode.personal,
    this.modeController,
    this.languageCode = 'vi',
    this.trailing,
    this.onModeTap,
    this.showBrand = true,
  });

  /// Optional active entity or breadcrumb title.
  final String? title;

  /// Current presentation mode (Personal, Clinical, Research, Admin).
  final PresentationMode mode;

  /// Optional presentation mode controller for role-permitted mode switching.
  final PresentationModeController? modeController;

  /// UI language code ('vi' or 'en').
  final String languageCode;

  /// Optional trailing action widgets.
  final List<Widget>? trailing;

  /// Optional callback when presentation mode pill is tapped.
  final VoidCallback? onModeTap;

  /// Whether to show the CLARA brand mark if no explicit title is provided.
  final bool showBrand;

  @override
  Widget build(BuildContext context) {
    final meta = kPresentationModeMeta[mode];
    final modeLabel = meta?.label(languageCode) ?? 'CLARA';
    final modeIcon = meta?.icon ?? Icons.spa_outlined;
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceXs,
      ),
      child: GlassSurface(
        blurSigma: GlassTokens.blurBar,
        radius: GlassTokens.radiusPill,
        fill: GlassFill.thin,
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceSm,
          vertical: 4,
        ),
        child: Row(
          children: [
            // Mode Badge / Switcher Affordance
            _buildModeBadge(context, modeLabel, modeIcon, colorScheme),

            const SizedBox(width: ClaraTokens.spaceSm),

            // Active Screen Title or Brand Mark
            Expanded(
              child: title != null && title!.isNotEmpty
                  ? Text(
                      title!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.15,
                          ),
                    )
                  : (showBrand
                      ? Text(
                          'CLARA',
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.8,
                                color: colorScheme.primary,
                              ),
                        )
                      : const SizedBox.shrink()),
            ),

            // Trailing Actions
            if (trailing != null) ...trailing!,
          ],
        ),
      ),
    );
  }

  Widget _buildModeBadge(
    BuildContext context,
    String modeLabel,
    IconData modeIcon,
    ColorScheme colorScheme,
  ) {
    final controller = modeController;
    final canSwitch = controller != null && controller.canSwitchModes;

    final badge = Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: colorScheme.primaryContainer.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(ClaraTokens.radiusPill),
        border: Border.all(
          color: colorScheme.primary.withValues(alpha: 0.25),
          width: 0.8,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(modeIcon, size: 14, color: colorScheme.primary),
          const SizedBox(width: 4),
          Text(
            modeLabel,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w700,
                  fontSize: 11,
                ),
          ),
          if (canSwitch) ...[
            const SizedBox(width: 2),
            Icon(
              Icons.unfold_more_rounded,
              size: 14,
              color: colorScheme.primary,
            ),
          ],
        ],
      ),
    );

    if (canSwitch || onModeTap != null) {
      return MinTapTarget(
        minSize: A11y.minTapTargetDimension,
        child: Semantics(
          button: true,
          label: languageCode == 'en'
              ? 'Switch workspace mode ($modeLabel)'
              : 'Đổi không gian làm việc ($modeLabel)',
          child: InkWell(
            borderRadius: BorderRadius.circular(ClaraTokens.radiusPill),
            onTap: onModeTap ?? () => _showModeSheet(context, controller!),
            child: badge,
          ),
        ),
      );
    }

    return badge;
  }

  void _showModeSheet(
    BuildContext context,
    PresentationModeController controller,
  ) {
    showModalBottomSheet<void>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(ClaraTokens.spaceMd),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  languageCode == 'en'
                      ? 'Select Workspace Mode'
                      : 'Chọn không gian làm việc',
                  style: Theme.of(sheetContext).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
                for (final m in controller.permittedModes) ...[
                  ListTile(
                    leading: Icon(kPresentationModeMeta[m]?.icon ?? Icons.circle),
                    title: Text(
                      kPresentationModeMeta[m]?.label(languageCode) ?? m.name,
                    ),
                    selected: controller.mode == m,
                    onTap: () {
                      controller.setMode(m);
                      Navigator.of(sheetContext).pop();
                    },
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

/// The modern adaptive spatial shell widget for CLARA Mobile.
class AdaptiveClaraShell extends StatefulWidget {
  const AdaptiveClaraShell({
    super.key,
    required this.destinations,
    required this.chatBody,
    this.chatLabel = 'Hỏi CLARA',
    this.chatIcon = Icons.forum_rounded,
    this.initialIndex = 0,
    this.presentationMode = PresentationMode.personal,
    this.presentationModeController,
    this.languageCode = 'vi',
    this.initialMorphState = DockMorphState.expanded,
    this.contextualChild,
    this.animateOrb = true,
    this.onDestinationChanged,
  }) : assert(
          destinations.length > 0,
          'AdaptiveClaraShell needs at least one destination',
        );

  /// The primary destinations in display order.
  final List<RedesignDestination> destinations;

  /// The Chat / Assistant surface body widget.
  final Widget chatBody;

  /// Label for the Chat / Assistant surface.
  final String chatLabel;

  /// Icon for the Chat / Assistant surface.
  final IconData chatIcon;

  /// Initial destination index (0-based).
  final int initialIndex;

  /// Active presentation mode.
  final PresentationMode presentationMode;

  /// Optional presentation mode controller.
  final PresentationModeController? presentationModeController;

  /// Language code ('vi' or 'en').
  final String languageCode;

  /// Initial morph state of the dock.
  final DockMorphState initialMorphState;

  /// Contextual content shown when dock is in [DockMorphState.contextual].
  final Widget? contextualChild;

  /// Whether active repeating animation is enabled for the Orb.
  final bool animateOrb;

  /// Callback when destination selection changes.
  final ValueChanged<int>? onDestinationChanged;

  @override
  State<AdaptiveClaraShell> createState() => _AdaptiveClaraShellState();
}

class _AdaptiveClaraShellState extends State<AdaptiveClaraShell> {
  late int _selectedIndex;
  late DockMorphState _dockMorphState;

  /// Sentinel index representing the center Chat / Orb active state.
  static const int _chatIndex = -1;

  @override
  void initState() {
    super.initState();
    _selectedIndex = _clampIndex(widget.initialIndex);
    _dockMorphState = widget.initialMorphState;
  }

  @override
  void didUpdateWidget(covariant AdaptiveClaraShell oldWidget) {
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
    if (next == _selectedIndex && !_isChatSelected) {
      return;
    }
    setState(() {
      _selectedIndex = next;
    });
    widget.onDestinationChanged?.call(next);
  }

  void _selectChat() {
    if (_isChatSelected) {
      return;
    }
    setState(() {
      _selectedIndex = _chatIndex;
    });
    widget.onDestinationChanged?.call(_chatIndex);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final useRail = constraints.maxWidth >= kSpatialShellRailBreakpoint;
        return useRail
            ? _buildRailScaffold(context)
            : _buildMobileScaffold(context);
      },
    );
  }

  // --- Mobile Layout (< 600dp) -----------------------------------------------

  Widget _buildMobileScaffold(BuildContext context) {
    return Scaffold(
      extendBody: true,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(52),
        child: SafeArea(
          bottom: false,
          child: ContextBar(
            mode: widget.presentationMode,
            modeController: widget.presentationModeController,
            languageCode: widget.languageCode,
          ),
        ),
      ),
      body: SafeArea(
        bottom: false,
        child: _buildBody(context),
      ),
      bottomNavigationBar: MorphingDock(
        destinations: widget.destinations,
        selectedIndex: _selectedIndex,
        isChatActive: _isChatSelected,
        morphState: _dockMorphState,
        orbState: _isChatSelected ? ClaraOrbState.ready : ClaraOrbState.idle,
        onDestinationSelected: _selectDestination,
        onOrbTap: _selectChat,
        orbLabel: widget.chatLabel,
        languageCode: widget.languageCode,
        contextualChild: widget.contextualChild,
        animateOrb: widget.animateOrb,
        onToggleMorph: (state) => setState(() => _dockMorphState = state),
      ),
    );
  }

  // --- Tablet / Desktop Rail Layout (>= 600dp) --------------------------------

  Widget _buildRailScaffold(BuildContext context) {
    final railSelected = _isChatSelected ? 0 : _selectedIndex + 1;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            ContextBar(
              mode: widget.presentationMode,
              modeController: widget.presentationModeController,
              languageCode: widget.languageCode,
            ),
            Expanded(
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
          ],
        ),
      ),
    );
  }

  Widget _buildRailChatLeading(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: ClaraTokens.spaceSm),
      child: SizedBox(height: 8),
    );
  }

  Widget _railIcon(IconData icon) {
    return MinTapTarget(
      minSize: A11y.minTapTargetDimension,
      child: ExcludeSemantics(child: Icon(icon)),
    );
  }

  // --- Content Canvas Body ---------------------------------------------------

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
}
