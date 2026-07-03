// Glass capability scope for CLARA_Mobile (clara-mobile-liquid-glass, R1, R6).
//
// A single `InheritedWidget` that resolves — once, near the authenticated root —
// whether the liquid-glass material is active for the current build + device,
// and exposes that decision to every descendant `GlassSurface`.
//
// The decision is a pure AND of three inputs (fail-closed):
//
//   glassEnabled = buildGateOn && !reduceTransparency && !lowEndDevice
//
//   * `buildGateOn`   — `kMobileLiquidGlassEnabled` (`--dart-define`).
//   * `reduceTransparency` / `lowEndDevice` — from the `DeviceCapability` probe
//     (OS "reduce transparency" / low-end or battery-saver heuristic).
//
// When `glassEnabled` is false the app renders the exact same layout with solid,
// opaque surfaces (no `BackdropFilter`) — see `GlassSurface`. This keeps the
// accessible, jank-free path as the automatic default (R6, R11.4).

import 'package:flutter/material.dart';

import '../../core/device_capability.dart';
import '../../core/feature_flags.dart';

/// Inherited glass-capability decision available to all descendants.
///
/// Seed one near the authenticated root (e.g. `redesign_root.dart`). Read it via
/// [GlassScope.of] (defaults to *disabled* when absent, so widgets outside a
/// scope are safe and opaque by construction).
class GlassScope extends InheritedWidget {
  const GlassScope({
    super.key,
    required this.enabled,
    required super.child,
  });

  /// Whether the liquid-glass material should render (build gate AND device
  /// capability). When false, descendants render opaque fallbacks.
  final bool enabled;

  /// Resolves the effective decision from the build gate and a
  /// [DeviceCapabilitySnapshot]. Pure so it is unit-testable without widgets.
  static bool resolveEnabled({
    required bool buildGateOn,
    required DeviceCapabilitySnapshot capability,
  }) {
    if (!buildGateOn) {
      return false;
    }
    if (capability.reduceTransparency || capability.lowEnd) {
      return false;
    }
    return true;
  }

  /// The nearest [GlassScope]'s decision, or `false` when none is in scope
  /// (fail-closed: no scope ⇒ opaque).
  static bool of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<GlassScope>();
    return scope?.enabled ?? false;
  }

  @override
  bool updateShouldNotify(GlassScope oldWidget) => enabled != oldWidget.enabled;
}

/// Convenience builder that resolves the [DeviceCapability] probe once and seeds
/// a [GlassScope] with `kMobileLiquidGlassEnabled && capability`.
///
/// The probe is a cached, best-effort async lookup; until it completes the scope
/// is seeded with the safe default (glass OFF), then flips on if the build gate
/// is set and the device supports it. This never blocks first paint.
class GlassScopeProvider extends StatefulWidget {
  const GlassScopeProvider({
    super.key,
    required this.child,
    this.buildGateOn = kMobileLiquidGlassEnabled,
    this.capability,
  });

  final Widget child;

  /// Build-time gate; overridable for tests.
  final bool buildGateOn;

  /// Optional pre-resolved capability (tests inject this to avoid the probe).
  final DeviceCapabilitySnapshot? capability;

  @override
  State<GlassScopeProvider> createState() => _GlassScopeProviderState();
}

class _GlassScopeProviderState extends State<GlassScopeProvider> {
  DeviceCapabilitySnapshot? _capability;

  @override
  void initState() {
    super.initState();
    final injected = widget.capability;
    if (injected != null) {
      _capability = injected;
    } else if (widget.buildGateOn) {
      // Only probe when the build gate is on — otherwise glass is off anyway.
      DeviceCapability.instance.resolve().then((snapshot) {
        if (mounted) {
          setState(() => _capability = snapshot);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final capability = _capability;
    final enabled = capability == null
        ? false
        : GlassScope.resolveEnabled(
            buildGateOn: widget.buildGateOn,
            capability: capability,
          );
    return GlassScope(enabled: enabled, child: widget.child);
  }
}
