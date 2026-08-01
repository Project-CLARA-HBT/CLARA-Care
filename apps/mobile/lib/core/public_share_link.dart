/// Safe Android deep-link intake for public, read-only PHR shares.
///
/// A PHR share token is a bearer capability. This module deliberately accepts
/// only the canonical HTTPS URL on the public CLARA domain, keeps the token in
/// memory, and never logs, persists, or places it in analytics. The viewer and
/// API remain responsible for feature gating, expiry, revocation and strict
/// content projection.
import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

const String _publicShareChannelName = 'clara/public_share_link';
const Set<String> _publicShareHosts = <String>{
  'theclaracare.com',
  'www.theclaracare.com',
};

/// Extracts an opaque PHR share capability from the only supported link shape:
/// `https://theclaracare.com/phr/shared/{token}`.
///
/// Relative paths are also accepted because Flutter can supply an Android
/// initial route as a path rather than a full URI. Empty, oversized, malformed,
/// non-HTTPS, foreign-host and non-PHR-share routes all fail closed with null.
String? phrShareTokenFromLink(String? rawLink) {
  if (rawLink == null || rawLink.isEmpty || rawLink.length > 2048) {
    return null;
  }

  final uri = Uri.tryParse(rawLink);
  if (uri == null ||
      (uri.hasScheme && uri.scheme.toLowerCase() != 'https') ||
      (uri.host.isNotEmpty &&
          !_publicShareHosts.contains(uri.host.toLowerCase()))) {
    return null;
  }

  final segments = uri.pathSegments;
  if (segments.length != 3 || segments[0] != 'phr' || segments[1] != 'shared') {
    return null;
  }

  final token = segments[2];
  // The bound prevents a malicious intent from turning a public capability
  // route into an oversized request URL. The server remains authoritative for
  // validity, revocation and expiry.
  return token.isEmpty || token.length > 512 ? null : token;
}

/// In-memory bridge for cold-start and warm Android public-share intents.
///
/// Android owns the platform implementation. Other platforms simply return no
/// link (via [MissingPluginException]) until they gain an equivalent, reviewed
/// implementation. This is safer than treating an unknown platform route as a
/// valid capability.
class PublicShareLinkController extends ChangeNotifier {
  PublicShareLinkController({MethodChannel? channel})
      : _channel = channel ?? const MethodChannel(_publicShareChannelName);

  /// Test-only construction seam for exercising app-level public routing
  /// without a platform channel or a live URL intent.
  PublicShareLinkController.withInitialLink(
    String? initialLink, {
    MethodChannel? channel,
  })  : _channel = channel ?? const MethodChannel(_publicShareChannelName),
        _token = phrShareTokenFromLink(initialLink);

  final MethodChannel _channel;
  String? _token;
  bool _started = false;

  /// The current in-memory token, if a valid canonical link was received.
  String? get token => _token;

  /// Connects the native bridge and obtains a cold-start link once.
  Future<void> start() async {
    if (_started) return;
    _started = true;
    _channel.setMethodCallHandler(_onMethodCall);
    try {
      _setFromRawLink(await _channel.invokeMethod<String>('initialLink'));
    } on MissingPluginException {
      // No reviewed native bridge on this platform: remain closed.
    } on PlatformException {
      // Platform failures carry no user-visible diagnostic or token state.
    }
  }

  Future<void> _onMethodCall(MethodCall call) async {
    if (call.method == 'link') {
      _setFromRawLink(call.arguments as String?);
    }
  }

  void _setFromRawLink(String? rawLink) {
    final next = phrShareTokenFromLink(rawLink);
    if (next == _token) return;
    _token = next;
    notifyListeners();
  }

  /// Drops the capability immediately when the viewer is closed.
  void clear() {
    if (_token == null) return;
    _token = null;
    notifyListeners();
  }

  @override
  void dispose() {
    if (_started) {
      _channel.setMethodCallHandler(null);
    }
    _token = null;
    super.dispose();
  }
}
