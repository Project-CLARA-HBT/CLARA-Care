// Interactive CLARA Orb object for CLARA_Mobile Spatial Editorial Health
// (Spec v4 Section 9, SEH-054, SEH-055, SEH-056).
//
// The CLARA Orb is the persistent product interaction object replacing generic
// chat-bubble branding for the main assistant action.
//
// SAFETY INVARIANT (INV-ORB):
// The Orb communicates SYSTEM INTERACTION state only (idle, listening,
// processing, ready, attention, error). It MUST NEVER communicate medical
// severity, diagnostic confidence, medication safety, or clinical urgency.
//
// States:
//   * idle: Resting state, calm subtle presence.
//   * hoverFocus: Focused / hover state with illuminated rim.
//   * listening: Active audio/voice input with pulsing acoustic aura.
//   * processing: AI thinking / reasoning / synthesizing with rotating iris shimmer.
//   * ready: Generation / task complete with luminous confirmation.
//   * attention: Follow-up action needed / non-urgent prompt.
//   * error: Non-critical connection/retry error state.
//
// Reduced motion:
//   * Resolves against `A11y.prefersReducedMotion(context)`. Under reduced motion,
//     continuous animations (pulsing, rotation, breathing) are halted and replaced
//     with static, high-contrast, state-appropriate layered visuals.

import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/generated/clara_tokens.g.dart';
import '../../theme/tokens.dart';

/// The 7 distinct interaction states of the CLARA Orb (Spec v4 Section 9).
enum ClaraOrbState {
  idle,
  hoverFocus,
  listening,
  processing,
  ready,
  attention,
  error;

  /// Alias for hover state (spec parity).
  static ClaraOrbState get hover => ClaraOrbState.hoverFocus;

  /// Localized accessible label for screen readers.
  String label({String languageCode = 'vi'}) {
    final isEn = languageCode == 'en';
    switch (this) {
      case ClaraOrbState.idle:
        return isEn ? 'CLARA Orb (Idle)' : 'CLARA Orb (Đang chờ)';
      case ClaraOrbState.hoverFocus:
        return isEn ? 'CLARA Orb (Focused)' : 'CLARA Orb (Tiêu điểm)';
      case ClaraOrbState.listening:
        return isEn ? 'CLARA Orb (Listening)' : 'CLARA Orb (Đang lắng nghe)';
      case ClaraOrbState.processing:
        return isEn ? 'CLARA Orb (Processing)' : 'CLARA Orb (Đang xử lý)';
      case ClaraOrbState.ready:
        return isEn ? 'CLARA Orb (Ready)' : 'CLARA Orb (Sẵn sàng)';
      case ClaraOrbState.attention:
        return isEn ? 'CLARA Orb (Attention)' : 'CLARA Orb (Cần chú ý)';
      case ClaraOrbState.error:
        return isEn ? 'CLARA Orb (Error)' : 'CLARA Orb (Lỗi kết nối)';
    }
  }

  String get labelVi => label(languageCode: 'vi');
  String get labelEn => label(languageCode: 'en');
}

/// An interactive, layered CLARA Orb widget.
class ClaraOrb extends StatefulWidget {
  const ClaraOrb({
    super.key,
    this.state = ClaraOrbState.idle,
    this.size = 56.0,
    this.onTap,
    this.onLongPress,
    this.customLabel,
    this.tooltip,
    this.languageCode = 'vi',
    this.showGlow = true,
    this.animate = true,
    this.heroTag,
  });

  /// The active system interaction state.
  final ClaraOrbState state;

  /// Diameter of the orb in logical pixels (default 56.0).
  final double size;

  /// Tap callback (e.g. opens Ask CLARA / Chat).
  final VoidCallback? onTap;

  /// Long-press callback (e.g. activates voice listening / shortcuts).
  final VoidCallback? onLongPress;

  /// Custom accessibility label override.
  final String? customLabel;

  /// Tooltip message shown on desktop/web hover or long-press.
  final String? tooltip;

  /// UI language code for accessibility announcements ('vi' or 'en').
  final String languageCode;

  /// Whether to render the soft outer halo/glow around the orb.
  final bool showGlow;

  /// Whether active repeating animation is enabled when motion is allowed.
  final bool animate;

  /// Optional Hero tag for fluid page/modal transitions.
  final Object? heroTag;

  @override
  State<ClaraOrb> createState() => _ClaraOrbState();
}

class _ClaraOrbState extends State<ClaraOrb>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animController;
  bool _isHovered = false;
  bool _isPressed = false;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncAnimation();
  }

  @override
  void didUpdateWidget(covariant ClaraOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state ||
        oldWidget.animate != widget.animate) {
      _syncAnimation();
    }
  }

  void _syncAnimation() {
    if (!mounted) return;
    final reducedMotion = A11y.prefersReducedMotion(context);
    if (!widget.animate || reducedMotion) {
      if (_animController.isAnimating) _animController.stop();
      _animController.value = 0.0;
      return;
    }

    switch (widget.state) {
      case ClaraOrbState.idle:
      case ClaraOrbState.ready:
      case ClaraOrbState.hoverFocus:
      case ClaraOrbState.attention:
      case ClaraOrbState.error:
        if (_animController.isAnimating) _animController.stop();
        _animController.value = 0.0;
        break;
      case ClaraOrbState.listening:
        _animController.duration = const Duration(milliseconds: 1000);
        if (!_animController.isAnimating) _animController.repeat(reverse: true);
        break;
      case ClaraOrbState.processing:
        _animController.duration = const Duration(milliseconds: 2000);
        if (!_animController.isAnimating) _animController.repeat();
        break;
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  ClaraOrbState get _effectiveState {
    if (_isHovered && widget.state == ClaraOrbState.idle) {
      return ClaraOrbState.hoverFocus;
    }
    return widget.state;
  }

  @override
  Widget build(BuildContext context) {
    _syncAnimation();

    final effectiveState = _effectiveState;
    final reducedMotion = A11y.prefersReducedMotion(context);
    final accessibleLabel = widget.customLabel ??
        effectiveState.label(languageCode: widget.languageCode);

    Widget orbContent = AnimatedBuilder(
      animation: _animController,
      builder: (context, _) {
        final animValue = reducedMotion ? 0.0 : _animController.value;
        return _buildOrbLayers(context, effectiveState, animValue);
      },
    );

    if (widget.heroTag != null) {
      orbContent = Hero(tag: widget.heroTag!, child: orbContent);
    }

    final interactiveOrb = MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTapDown: (_) => setState(() => _isPressed = true),
        onTapUp: (_) => setState(() => _isPressed = false),
        onTapCancel: () => setState(() => _isPressed = false),
        onTap: widget.onTap,
        onLongPress: widget.onLongPress,
        child: AnimatedScale(
          scale: _isPressed ? 0.94 : (_isHovered ? 1.05 : 1.0),
          duration:
              A11y.resolveMotionDuration(context, ClaraTokens.motionFast),
          curve: Curves.easeOutCubic,
          child: orbContent,
        ),
      ),
    );

    return Semantics(
      button: true,
      enabled: widget.onTap != null || widget.onLongPress != null,
      label: accessibleLabel,
      tooltip: widget.tooltip,
      child: MinTapTarget(
        minSize: A11y.minTapTargetDimension,
        child: widget.tooltip != null
            ? Tooltip(message: widget.tooltip!, child: interactiveOrb)
            : interactiveOrb,
      ),
    );
  }

  Widget _buildOrbLayers(
    BuildContext context,
    ClaraOrbState state,
    double animValue,
  ) {
    final size = widget.size;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final colors = _resolveStateColors(state, isDark);

    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        clipBehavior: Clip.none,
        children: [
          // Outer Glow / Halo
          if (widget.showGlow)
            Positioned.fill(
              child: Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: colors.glow.withValues(
                        alpha: (0.35 + (0.15 * math.sin(animValue * math.pi)))
                            .clamp(0.0, 1.0),
                      ),
                      blurRadius: size * (0.35 + 0.1 * animValue),
                      spreadRadius: size * 0.05,
                    ),
                  ],
                ),
              ),
            ),

          // Outer Concentric Ring / Specular Rim
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: SweepGradient(
                transform: GradientRotation(
                  state == ClaraOrbState.processing
                      ? animValue * 2 * math.pi
                      : 0.0,
                ),
                colors: [
                  colors.primary,
                  colors.secondary,
                  colors.accent,
                  colors.primary,
                ],
              ),
              border: Border.all(
                color: colors.border.withValues(alpha: 0.8),
                width: 1.5,
              ),
            ),
          ),

          // Inner Spherical Gradient Core
          Container(
            width: size * 0.82,
            height: size * 0.82,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                center: const Alignment(-0.25, -0.35),
                radius: 0.85,
                colors: [
                  colors.coreHighlight,
                  colors.primary,
                  colors.coreDeep,
                ],
                stops: const [0.0, 0.55, 1.0],
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
          ),

          // Center Glyph / Status Indicator
          Center(
            child: _buildStateIcon(state, size * 0.44, colors.iconColor),
          ),
        ],
      ),
    );
  }

  Widget _buildStateIcon(ClaraOrbState state, double iconSize, Color color) {
    switch (state) {
      case ClaraOrbState.idle:
      case ClaraOrbState.hoverFocus:
        return Icon(
          Icons.auto_awesome,
          size: iconSize,
          color: color,
        );
      case ClaraOrbState.listening:
        return Icon(
          Icons.mic,
          size: iconSize,
          color: color,
        );
      case ClaraOrbState.processing:
        return Icon(
          Icons.lens_blur_rounded,
          size: iconSize,
          color: color,
        );
      case ClaraOrbState.ready:
        return Icon(
          Icons.check_rounded,
          size: iconSize,
          color: color,
        );
      case ClaraOrbState.attention:
        return Icon(
          Icons.priority_high_rounded,
          size: iconSize,
          color: color,
        );
      case ClaraOrbState.error:
        return Icon(
          Icons.sync_problem_rounded,
          size: iconSize,
          color: color,
        );
    }
  }

  _OrbColorPalette _resolveStateColors(ClaraOrbState state, bool isDark) {
    switch (state) {
      case ClaraOrbState.idle:
        return _OrbColorPalette(
          primary: ClaraGeneratedTokens.iris600,
          secondary: ClaraGeneratedTokens.brand600,
          accent: ClaraGeneratedTokens.mint500,
          coreHighlight: const Color(0xFFC4B5FD),
          coreDeep: const Color(0xFF3B2F8F),
          border: const Color(0xFFDDD6FE),
          glow: ClaraGeneratedTokens.iris500,
          iconColor: Colors.white,
        );

      case ClaraOrbState.hoverFocus:
        return _OrbColorPalette(
          primary: ClaraGeneratedTokens.iris500,
          secondary: ClaraGeneratedTokens.brand400,
          accent: Colors.white,
          coreHighlight: Colors.white,
          coreDeep: const Color(0xFF4C1D95),
          border: Colors.white,
          glow: ClaraGeneratedTokens.iris300,
          iconColor: Colors.white,
        );

      case ClaraOrbState.listening:
        return _OrbColorPalette(
          primary: ClaraGeneratedTokens.mint500,
          secondary: const Color(0xFF10B981),
          accent: const Color(0xFF6EE7B7),
          coreHighlight: const Color(0xFFA7F3D0),
          coreDeep: const Color(0xFF064E3B),
          border: const Color(0xFFD1FAE5),
          glow: const Color(0xFF10B981),
          iconColor: Colors.white,
        );

      case ClaraOrbState.processing:
        return _OrbColorPalette(
          primary: ClaraGeneratedTokens.iris600,
          secondary: ClaraGeneratedTokens.brand500,
          accent: const Color(0xFFF472B6),
          coreHighlight: const Color(0xFFDDD6FE),
          coreDeep: const Color(0xFF2E1065),
          border: const Color(0xFFE9D5FF),
          glow: ClaraGeneratedTokens.iris500,
          iconColor: Colors.white,
        );

      case ClaraOrbState.ready:
        return _OrbColorPalette(
          primary: const Color(0xFF059669),
          secondary: ClaraGeneratedTokens.mint500,
          accent: const Color(0xFF34D399),
          coreHighlight: const Color(0xFFD1FAE5),
          coreDeep: const Color(0xFF064E3B),
          border: const Color(0xFFA7F3D0),
          glow: const Color(0xFF10B981),
          iconColor: Colors.white,
        );

      case ClaraOrbState.attention:
        return _OrbColorPalette(
          primary: const Color(0xFFD97706),
          secondary: const Color(0xFFF59E0B),
          accent: const Color(0xFFFDE68A),
          coreHighlight: const Color(0xFFFEF3C7),
          coreDeep: const Color(0xFF78350F),
          border: const Color(0xFFFDE68A),
          glow: const Color(0xFFF59E0B),
          iconColor: Colors.white,
        );

      case ClaraOrbState.error:
        return _OrbColorPalette(
          primary: const Color(0xFFDC2626),
          secondary: const Color(0xFFEF4444),
          accent: const Color(0xFFFCA5A5),
          coreHighlight: const Color(0xFFFEE2E2),
          coreDeep: const Color(0xFF7F1D1D),
          border: const Color(0xFFFECACA),
          glow: const Color(0xFFEF4444),
          iconColor: Colors.white,
        );
    }
  }
}

class _OrbColorPalette {
  const _OrbColorPalette({
    required this.primary,
    required this.secondary,
    required this.accent,
    required this.coreHighlight,
    required this.coreDeep,
    required this.border,
    required this.glow,
    required this.iconColor,
  });

  final Color primary;
  final Color secondary;
  final Color accent;
  final Color coreHighlight;
  final Color coreDeep;
  final Color border;
  final Color glow;
  final Color iconColor;
}
