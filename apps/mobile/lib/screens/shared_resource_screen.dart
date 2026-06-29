import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../core/api_client.dart';
import '../core/feature_flags.dart';
import '../widgets/end_user_safe_answer.dart' show endUserSafeProjection;
import '../widgets/error_retry_view.dart';

// =============================================================================
// SharedResourceScreen — clara-mobile-feature-parity Task 11.1 (Req 12.1–12.3).
//
//   * 12.1 Opens a shared resource by token via CLARA_API's public read
//          endpoint (`GET /api/v1/phr/shared/{token}`).
//   * 12.2 An invalid / expired / revoked token surfaces a CLEAR, NON-PII,
//          Vietnamese-first error rather than partial content.
//   * 12.3 Shared content is rendered READ-ONLY and only end-user-safe fields
//          are shown — internal runtime fields (RAG/research/fallback mode,
//          retrieval, connector source_errors, policy verdicts, ml, debug) are
//          never rendered, even if a (malicious or future) payload carries them.
//
//   * Gated behind `sharing_mobile_enabled` (Req 12.4 / 15.1) via
//     [MobileFeatureFlagResolver]. When the gate is closed the screen renders a
//     disabled state and performs NO network call.
//
// ----------------------------------------------------------------------------
// api_client.dart is owned by another writer this wave, and it currently has no
// shared-resource GET-by-token method. To stay additive and testable NOW, this
// screen takes an injectable [SharedResourceFetcher] callback. Production wires
// [createHttpSharedResourceFetcher] (a thin GET using the same patterns as
// ApiClient: bounded timeout, ApiException, Vietnamese-first PII-free copy);
// once ApiClient grows a `getSharedResource(token:)` method, the default
// fetcher is the single seam to swap over — no screen changes required.
//
// End-user-safe content: the merged [endUserSafeProjection] (Task 3.3) is
// applied to the raw payload before this screen's whitelist parse, so internal
// runtime fields are stripped at every nesting depth, exactly as on the chat
// surface — then the whitelist below renders only the known PHR fields.
// =============================================================================

/// Fetches the raw shared-resource payload for [token] from CLARA_API.
///
/// Implementations MUST throw an [ApiException] (with a Vietnamese-first,
/// PII-free [ApiException.message]) on any failure — invalid/expired/revoked
/// token, transport error, or timeout — so the screen can render a clean error
/// state. The returned map is the raw server envelope; the screen applies the
/// end-user-safe projection itself.
typedef SharedResourceFetcher = Future<Map<String, dynamic>> Function(
    String token);

/// Vietnamese-first, PII-free copy for a token that cannot be opened. The same
/// message is used for not-found / revoked / expired so the screen never leaks
/// whether a token ever existed (Req 12.2).
const String kSharedResourceUnavailableMessage =
    'Liên kết chia sẻ không hợp lệ, đã hết hạn hoặc đã bị thu hồi.';

/// Copy shown when the sharing feature gate is closed (Req 12.4).
const String kSharingDisabledMessage =
    'Tính năng chia sẻ hiện chưa được bật cho tài khoản của bạn.';

/// Maps a failed HTTP status from the public share endpoint onto a non-PII,
/// Vietnamese-first message. 404 (not found / sharing disabled / record
/// missing) and 410 (revoked / expired) intentionally collapse to one message
/// so the screen does not disclose token existence (Req 12.2).
String shareErrorMessageForStatus(int statusCode) {
  switch (statusCode) {
    case 404:
    case 410:
      return kSharedResourceUnavailableMessage;
    default:
      return 'Không thể mở nội dung được chia sẻ. Vui lòng thử lại.';
  }
}

/// Builds the production [SharedResourceFetcher]: a bounded, read-only GET to
/// `/{baseUrl}/api/v1/phr/shared/{token}`. No credentials are sent — the
/// endpoint is intentionally public and read-only. Error mapping mirrors
/// [ApiClient]: timeout/transport/HTTP errors all surface as [ApiException]
/// with Vietnamese-first, PII-free messages.
SharedResourceFetcher createHttpSharedResourceFetcher({
  required String baseUrl,
  http.Client? client,
  Duration requestTimeout = const Duration(seconds: 30),
}) {
  final httpClient = client ?? http.Client();
  final base =
      baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
  return (String token) async {
    final uri =
        Uri.parse('$base/api/v1/phr/shared/${Uri.encodeComponent(token)}');
    final http.Response response;
    try {
      response = await httpClient.get(
        uri,
        headers: const {'Accept': 'application/json'},
      ).timeout(requestTimeout);
    } on TimeoutException {
      throw ApiException(message: 'Hết thời gian chờ phản hồi từ server.');
    } catch (_) {
      throw ApiException(message: 'Không thể kết nối tới server.');
    }

    if (response.statusCode >= 400) {
      throw ApiException(
        statusCode: response.statusCode,
        message: shareErrorMessageForStatus(response.statusCode),
      );
    }

    Object? decoded;
    try {
      decoded = response.body.isEmpty ? null : jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }
    if (decoded is! Map<String, dynamic>) {
      throw ApiException(message: 'Phản hồi không hợp lệ từ server.');
    }
    return decoded;
  };
}

String _str(Object? value) => value == null ? '' : value.toString().trim();

List<Map<String, dynamic>> _objectList(Object? value) {
  if (value is! List) return const [];
  final result = <Map<String, dynamic>>[];
  for (final item in value) {
    if (item is Map) {
      result.add(item.cast<String, dynamic>());
    }
  }
  return result;
}

/// A single labeled section of the read-only shared view (e.g. "Dị ứng").
class SharedResourceSection {
  const SharedResourceSection({required this.title, required this.lines});

  final String title;
  final List<String> lines;

  bool get isEmpty => lines.isEmpty;
}

/// End-user-safe projection of a shared-resource payload (Req 12.3).
///
/// This parser is a strict WHITELIST: it reads only the known user-facing
/// fields of the PHR share envelope (`profile`, `allergies`, `conditions`,
/// `medications`, `emergency_card`, `hedge`). Any other key in the payload —
/// including internal runtime fields such as `mode`, `retrieval`,
/// `source_errors`, `policy`, `ml`, `fallback`, or `debug` — is ignored and
/// therefore never rendered, regardless of the role that minted the token.
///
/// Defense-in-depth: [fromPayload] first runs the raw envelope through the
/// shared [endUserSafeProjection] (Task 3.3) with `isAdmin: false` — shared
/// content is always public / non-admin — so internal runtime keys are stripped
/// at every nesting depth before the whitelist parse, matching the chat /
/// DDI / scribe surfaces (Property P3). When a shared *chat* resource is added
/// server-side, its answer-shaped portion can additionally be routed through
/// `EndUserSafeAnswer` without changing this whitelist.
class SharedResourceView {
  const SharedResourceView({
    required this.scope,
    required this.heading,
    required this.sections,
    required this.disclaimer,
  });

  /// Server-declared scope: `full` or `emergency_card`. Unknown scopes still
  /// render whatever whitelisted sections were present.
  final String scope;

  /// A short, non-PII heading describing the kind of shared resource.
  final String heading;

  /// Ordered, already-sanitized content sections (empty sections omitted).
  final List<SharedResourceSection> sections;

  /// The persistent self-declared / decision-support-only disclaimer (vi).
  final String disclaimer;

  factory SharedResourceView.fromPayload(Map<String, dynamic> rawPayload) {
    // Defense-in-depth: strip internal runtime fields at every nesting depth
    // before whitelisting (shared content is always non-admin) (Req 12.3, P3).
    final payload = endUserSafeProjection(rawPayload, isAdmin: false);
    final scope = _str(payload['scope']);

    if (scope == 'emergency_card' || payload['emergency_card'] is Map) {
      final card = (payload['emergency_card'] as Map?)?.cast<String, dynamic>() ??
          const <String, dynamic>{};
      return SharedResourceView(
        scope: 'emergency_card',
        heading: 'Thẻ khẩn cấp được chia sẻ',
        sections: _emergencyCardSections(card),
        disclaimer: _disclaimerFrom(card['disclaimer']) ??
            _selfDeclaredDisclaimer,
      );
    }

    final record =
        (payload['record'] as Map?)?.cast<String, dynamic>() ?? payload;
    return SharedResourceView(
      scope: 'full',
      heading: 'Hồ sơ sức khỏe được chia sẻ',
      sections: _fullRecordSections(record),
      disclaimer: _selfDeclaredDisclaimer,
    );
  }

  static const String _selfDeclaredDisclaimer =
      'Nội dung này dựa trên thông tin tự khai, chỉ hỗ trợ quyết định, '
      'không phải bệnh án điện tử (EMR/EHR) và không có giá trị pháp lý. '
      'Hãy trao đổi với bác sĩ có chuyên môn.';

  static String? _disclaimerFrom(Object? value) {
    if (value is Map) {
      final vi = _str(value['vi']);
      if (vi.isNotEmpty) return vi;
    }
    return null;
  }

  static List<SharedResourceSection> _fullRecordSections(
      Map<String, dynamic> record) {
    final sections = <SharedResourceSection>[];

    final profile =
        (record['profile'] as Map?)?.cast<String, dynamic>() ?? const {};
    final profileLines = <String>[
      if (_str(profile['full_name']).isNotEmpty)
        'Họ tên: ${_str(profile['full_name'])}',
      if (_str(profile['gender']).isNotEmpty)
        'Giới tính: ${_str(profile['gender'])}',
      if (_str(profile['blood_type']).isNotEmpty)
        'Nhóm máu: ${_str(profile['blood_type'])}',
      if (_str(profile['date_of_birth']).isNotEmpty)
        'Ngày sinh: ${_str(profile['date_of_birth'])}',
    ];
    if (profileLines.isNotEmpty) {
      sections.add(SharedResourceSection(title: 'Hồ sơ', lines: profileLines));
    }

    sections.add(SharedResourceSection(
      title: 'Dị ứng',
      lines: _allergyLines(record['allergies']),
    ));
    sections.add(SharedResourceSection(
      title: 'Bệnh lý',
      lines: _conditionLines(record['conditions']),
    ));
    sections.add(SharedResourceSection(
      title: 'Thuốc đang dùng',
      lines: _medicationLines(record['medications']),
    ));

    return sections.where((s) => !s.isEmpty).toList();
  }

  static List<SharedResourceSection> _emergencyCardSections(
      Map<String, dynamic> card) {
    final sections = <SharedResourceSection>[
      SharedResourceSection(
        title: 'Dị ứng',
        lines: _allergyLines(card['allergies']),
      ),
      SharedResourceSection(
        title: 'Thuốc đang dùng',
        lines: _medicationLines(card['current_medications']),
      ),
      SharedResourceSection(
        title: 'Bệnh lý',
        lines: _conditionLines(card['conditions']),
      ),
    ];

    final bloodType = _str(card['blood_type']);
    if (bloodType.isNotEmpty) {
      sections.add(SharedResourceSection(
        title: 'Nhóm máu',
        lines: [bloodType],
      ));
    }

    final contact =
        (card['emergency_contact'] as Map?)?.cast<String, dynamic>();
    if (contact != null) {
      final name = _str(contact['name']);
      final phone = _str(contact['phone']);
      final line = [name, phone].where((s) => s.isNotEmpty).join(' • ');
      if (line.isNotEmpty) {
        sections.add(SharedResourceSection(
          title: 'Liên hệ khẩn cấp',
          lines: [line],
        ));
      }
    }

    return sections.where((s) => !s.isEmpty).toList();
  }

  static List<String> _allergyLines(Object? value) {
    return _objectList(value)
        .map((a) {
          final name = _str(a['name']).isNotEmpty
              ? _str(a['name'])
              : _str(a['substance']);
          final severity = _str(a['severity']);
          final reaction = _str(a['reaction']);
          final extras = [
            if (severity.isNotEmpty && severity != 'unknown') severity,
            if (reaction.isNotEmpty) reaction,
          ].join(' • ');
          if (name.isEmpty) return '';
          return extras.isEmpty ? name : '$name ($extras)';
        })
        .where((s) => s.isNotEmpty)
        .toList();
  }

  static List<String> _conditionLines(Object? value) {
    return _objectList(value)
        .map((c) {
          final name = _str(c['name']);
          final status = _str(c['status']);
          if (name.isEmpty) return '';
          return (status.isEmpty || status == 'unknown')
              ? name
              : '$name ($status)';
        })
        .where((s) => s.isNotEmpty)
        .toList();
  }

  static List<String> _medicationLines(Object? value) {
    return _objectList(value)
        .map((m) {
          final name = _str(m['name']);
          final dose = _str(m['dose']).isNotEmpty
              ? _str(m['dose'])
              : _str(m['dosage']);
          if (name.isEmpty) return '';
          return dose.isEmpty ? name : '$name — $dose';
        })
        .where((s) => s.isNotEmpty)
        .toList();
  }
}

/// Read-only viewer for a shared CLARA resource opened by token (Req 12).
class SharedResourceScreen extends StatefulWidget {
  const SharedResourceScreen({
    super.key,
    required this.token,
    required this.fetcher,
    required this.flags,
  });

  /// The opaque share token from the deep link.
  final String token;

  /// Injectable fetch seam (see [createHttpSharedResourceFetcher]).
  final SharedResourceFetcher fetcher;

  /// Resolved mobile feature gates; sharing must be enabled to render content.
  final MobileFeatureFlagResolver flags;

  @override
  State<SharedResourceScreen> createState() => _SharedResourceScreenState();
}

class _SharedResourceScreenState extends State<SharedResourceScreen> {
  bool _loading = false;
  String? _error;
  SharedResourceView? _view;

  @override
  void initState() {
    super.initState();
    if (widget.flags.sharingEnabled) {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _view = null;
    });
    try {
      final payload = await widget.fetcher(widget.token);
      if (!mounted) return;
      setState(() => _view = SharedResourceView.fromPayload(payload));
    } on ApiException catch (error) {
      // ApiException messages are Vietnamese-first and PII-free by contract.
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      // Contain any unexpected error within the screen; never leak a stack
      // trace to the user (Req 11.4).
      if (!mounted) return;
      setState(() => _error = kSharedResourceUnavailableMessage);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nội dung được chia sẻ')),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    // Feature gate (Req 12.4): closed gate renders a disabled state and made
    // no network call.
    if (!widget.flags.sharingEnabled) {
      return const Center(
        child: Padding(
          key: Key('sharing-disabled'),
          padding: EdgeInsets.all(24),
          child: Text(
            kSharingDisabledMessage,
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return ErrorRetryView(message: _error!, onRetry: _load);
    }

    final view = _view;
    if (view == null) {
      return const SizedBox.shrink();
    }

    return _SharedResourceBody(view: view);
  }
}

/// Stateless read-only rendering of the safe projection.
class _SharedResourceBody extends StatelessWidget {
  const _SharedResourceBody({required this.view});

  final SharedResourceView view;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      key: const Key('shared-resource-body'),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        // Read-only badge (status by text, not color alone — Req 10.5).
        Semantics(
          label: 'Chế độ chỉ xem',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock_outline, size: 18),
              const SizedBox(width: 6),
              Text('Chỉ xem', style: theme.textTheme.labelLarge),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Text(view.heading, style: theme.textTheme.titleLarge),
        const SizedBox(height: 16),
        for (final section in view.sections) ...[
          _SectionCard(section: section),
          const SizedBox(height: 12),
        ],
        const SizedBox(height: 4),
        // Persistent self-declared / decision-support-only disclaimer.
        Card(
          color: theme.colorScheme.surfaceContainerHighest,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Semantics(
              label: view.disclaimer,
              child: Text(
                view.disclaimer,
                style: theme.textTheme.bodySmall,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.section});

  final SharedResourceSection section;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(section.title, style: theme.textTheme.titleSmall),
            const SizedBox(height: 6),
            for (final line in section.lines)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('• $line'),
              ),
          ],
        ),
      ),
    );
  }
}
