// Device-capability probe for CLARA_Mobile (clara-mobile-liquid-glass, R1.5, R6).
//
// A tiny, dependency-light signal used by the liquid-glass system to decide
// whether the expensive translucent material (`BackdropFilter` blur) should be
// rendered at all. It combines two inputs, both fail-safe toward "degrade":
//
//   1. Reduce-transparency / reduce-motion / high-contrast accessibility
//      preference (from the ambient `MediaQueryData`) — when the user asks for
//      less transparency or motion, glass collapses to an opaque fallback.
//   2. A coarse low-end heuristic derived from the physical screen metrics (a
//      stand-in for GPU tier, since we add no platform-channel dependency).
//      Tiny short-side screens are treated as low-end so blur-heavy chrome
//      never janks there.
//
// Two layers are exposed:
//   * Pure `MediaQueryData` resolvers (`*Data`) — trivially unit-testable.
//   * A cached [DeviceCapability.instance] with an async [resolve] returning a
//     [DeviceCapabilitySnapshot], resolved once high in the tree (see
//     `GlassScope`) so descendants share one decision without re-probing.
//
// The async layer takes an optional [MediaQueryData]; when omitted it uses the
// platform dispatcher's primary view metrics so it can run before a widget
// tree exists. It never blocks first paint (the scope seeds glass OFF until it
// completes).

import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/widgets.dart';

/// An immutable snapshot of the resolved device/accessibility capability that
/// gates the glass material. Pure data; produced by [DeviceCapability.resolve].
@immutable
class DeviceCapabilitySnapshot {
  const DeviceCapabilitySnapshot({
    required this.reduceTransparency,
    required this.lowEnd,
  });

  /// The user asked for reduced transparency/motion (or high contrast).
  final bool reduceTransparency;

  /// The device is a constrained/low-end screen where stacked blurs may jank.
  final bool lowEnd;

  /// Whether the glass material can be afforded (neither degrade signal set).
  bool get canAffordGlass => !reduceTransparency && !lowEnd;

  @override
  bool operator ==(Object other) =>
      other is DeviceCapabilitySnapshot &&
      other.reduceTransparency == reduceTransparency &&
      other.lowEnd == lowEnd;

  @override
  int get hashCode => Object.hash(reduceTransparency, lowEnd);
}

/// Pure resolvers + a cached async probe describing whether this device/session
/// can afford the glass material, or should fall back to opaque surfaces (R6).
class DeviceCapability {
  DeviceCapability._();

  /// Shared, cached instance. The first [resolve] computes and memoizes the
  /// snapshot; subsequent calls return the cached value.
  static final DeviceCapability instance = DeviceCapability._();

  DeviceCapabilitySnapshot? _cached;

  /// Devices whose logical short side is below this are treated as low-end for
  /// glass purposes. Deliberately conservative (no native GPU query) so we only
  /// disable glass on genuinely constrained screens.
  static const double _lowEndShortSideLogical = 320.0;

  /// Whether the user has asked to reduce transparency/motion, resolved from a
  /// [MediaQueryData]. Flutter has no dedicated cross-platform
  /// "reduce transparency" flag, so we treat the OS "remove animations" signal,
  /// assistive-navigation, and high-contrast as the reduce-transparency request
  /// — matching the reduced-motion convention used elsewhere in the app.
  static bool prefersReducedTransparencyData(MediaQueryData media) =>
      media.disableAnimations ||
      media.accessibleNavigation ||
      media.highContrast;

  /// Coarse low-end heuristic: a tiny logical short side indicates a
  /// constrained screen where stacked blurs are most likely to drop frames.
  static bool isLowEndData(MediaQueryData media) {
    final size = media.size;
    if (size.isEmpty) {
      // No usable metrics yet — a transient layout state; do not force low-end.
      return false;
    }
    final shortSideLogical = size.shortestSide;
    return shortSideLogical > 0 && shortSideLogical < _lowEndShortSideLogical;
  }

  /// Whether the glass material can be afforded for the given [media].
  static bool canAffordGlassData(MediaQueryData media) =>
      !prefersReducedTransparencyData(media) && !isLowEndData(media);

  /// Builds a [DeviceCapabilitySnapshot] from a [MediaQueryData] (pure).
  static DeviceCapabilitySnapshot snapshotFromData(MediaQueryData media) =>
      DeviceCapabilitySnapshot(
        reduceTransparency: prefersReducedTransparencyData(media),
        lowEnd: isLowEndData(media),
      );

  /// [BuildContext] convenience wrapper. Returns `false` (cannot afford) when no
  /// [MediaQuery] is in scope, so glass fails closed to opaque.
  static bool canAffordGlass(BuildContext context) {
    final media = MediaQuery.maybeOf(context);
    if (media == null) {
      return false;
    }
    return canAffordGlassData(media);
  }

  /// Resolves (and caches) the capability snapshot. When [media] is supplied it
  /// is used directly; otherwise the platform dispatcher's primary view metrics
  /// are read so this can run before a widget tree exists. Best-effort and
  /// non-blocking — any failure resolves to the safe "degrade" snapshot.
  Future<DeviceCapabilitySnapshot> resolve({MediaQueryData? media}) async {
    final cached = _cached;
    if (cached != null) {
      return cached;
    }
    DeviceCapabilitySnapshot snapshot;
    try {
      if (media != null) {
        snapshot = snapshotFromData(media);
      } else {
        snapshot = _snapshotFromPlatform();
      }
    } catch (_) {
      // Fail toward degrade so a probe failure never forces expensive glass.
      snapshot = const DeviceCapabilitySnapshot(
        reduceTransparency: true,
        lowEnd: true,
      );
    }
    _cached = snapshot;
    return snapshot;
  }

  /// Reads capability from the platform dispatcher (no widget tree required).
  static DeviceCapabilitySnapshot _snapshotFromPlatform() {
    final dispatcher = PlatformDispatcher.instance;
    final reduceTransparency =
        dispatcher.accessibilityFeatures.disableAnimations ||
            dispatcher.accessibilityFeatures.highContrast;

    var lowEnd = false;
    final views = dispatcher.views;
    if (views.isNotEmpty) {
      final view = views.first;
      final dpr = view.devicePixelRatio <= 0 ? 1.0 : view.devicePixelRatio;
      final physical = view.physicalSize;
      if (!physical.isEmpty) {
        final shortSideLogical = physical.shortestSide / dpr;
        lowEnd =
            shortSideLogical > 0 && shortSideLogical < _lowEndShortSideLogical;
      }
    }
    return DeviceCapabilitySnapshot(
      reduceTransparency: reduceTransparency,
      lowEnd: lowEnd,
    );
  }

  /// Clears the cached snapshot (tests only).
  @visibleForTesting
  void resetForTest() => _cached = null;
}
