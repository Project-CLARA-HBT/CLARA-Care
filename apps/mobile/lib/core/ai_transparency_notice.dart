/// Versioned AI Transparency Notice for CLARA_Mobile (Requirement 7).
///
/// This is the additive, flag-gated mobile mirror of the web compliance AI
/// transparency notice (web compliance Requirement 1). It records that the user
/// has acknowledged — for the *current notice version* — that they are
/// interacting with an AI medical assistant that does not replace a licensed
/// clinician, **before** medical content is served (Requirement 7.1, 7.2).
///
/// Design constraints honored here:
///
///   * **Versioned re-prompt.** Acknowledgement is keyed by notice [version].
///     Publishing a new version (a new [AiTransparencyNotice.version]) makes a
///     previously-acknowledged user re-acknowledge, because the persisted
///     version no longer matches the current one
///     ([AiTransparencyNoticeStore.needsAcknowledgement]).
///   * **Persisted acknowledgement.** The acknowledged version is stored in the
///     same secure key/value seam the session store uses
///     ([SessionSecureStorage]), so production persists across restarts while
///     tests inject an in-memory implementation without platform channels.
///   * **Default OFF / unchanged when off.** The gate is only consulted when the
///     `transparency_notice_mobile_enabled` flag resolves true (see
///     `feature_flags.dart`). With the flag off the gate widget renders its
///     child unchanged, so behavior is byte-equivalent to today (Requirement
///     15.1, 15.2).
///   * **No PII.** Only an opaque version string is persisted; no user content
///     ever touches this store (Requirement 11.2, 11.5).
///
/// This file is a pure model + persistence seam (no widgets), so the versioning
/// logic can be unit/property tested in isolation. The gate widget lives in
/// `lib/widgets/ai_transparency_notice_gate.dart`.
library;

import 'session_store.dart'
    show SessionSecureStorage, FlutterSecureSessionStorage;

/// The content of a single, versioned AI transparency notice.
///
/// Vietnamese-first copy (Requirement 5.5 / project-wide convention). The
/// [version] is the *only* value persisted on acknowledgement; bumping it
/// re-prompts every user.
class AiTransparencyNotice {
  const AiTransparencyNotice({
    required this.version,
    required this.title,
    required this.body,
    this.acknowledgeLabel = 'Tôi đã hiểu và tiếp tục',
  });

  /// Opaque version identifier. Changing this re-prompts acknowledgement.
  final String version;

  /// Short heading rendered at the top of the notice.
  final String title;

  /// One or more paragraphs/bullets describing the AI-assistant disclosure.
  final List<String> body;

  /// Label for the acknowledgement action.
  final String acknowledgeLabel;
}

/// The current AI transparency notice shown before medical content.
///
/// Mirrors the web compliance notice: the user is interacting with an AI
/// medical assistant that supports — but does not replace — a licensed
/// clinician. Bump [AiTransparencyNotice.version] whenever the disclosure text
/// materially changes so previously-acknowledged users re-acknowledge.
const AiTransparencyNotice kCurrentAiTransparencyNotice = AiTransparencyNotice(
  version: '2026-04-v1',
  title: 'Thông báo minh bạch về AI',
  body: <String>[
    'Bạn đang tương tác với trợ lý y tế AI của CLARA. Đây là phần mềm hỗ trợ '
        'ra quyết định dựa trên dữ liệu bạn tự khai báo — không phải thiết bị y '
        'tế và không thay thế bác sĩ.',
    'Các câu trả lời chỉ mang tính tham khảo. Hãy luôn tham vấn nhân viên y tế '
        'có chuyên môn trước khi đưa ra quyết định về sức khỏe.',
    'Trong trường hợp khẩn cấp, hãy gọi ngay dịch vụ cấp cứu tại địa phương.',
  ],
);

/// English rendering of the same versioned disclosure. It carries the exact
/// same acknowledgement version and safety meaning as the Vietnamese-first
/// default; only presentation changes. This lets a consumer who switches the
/// app language review the disclosure in their selected language without
/// weakening the versioned consent gate.
const AiTransparencyNotice kCurrentAiTransparencyNoticeEn =
    AiTransparencyNotice(
  version: '2026-04-v1',
  title: 'AI transparency notice',
  body: <String>[
    'You are interacting with CLARA\'s AI health assistant. It is '
        'decision-support software based on information you provide — not '
        'a medical device and not a replacement for a doctor.',
    'Answers are for general information only. Always consult a qualified '
        'health professional before making decisions about your health.',
    'In an emergency, call your local emergency service immediately.',
  ],
  acknowledgeLabel: 'I understand and want to continue',
);

/// Resolves the current disclosure in the selected presentation language.
///
/// Acknowledgement remains keyed solely by the shared [AiTransparencyNotice.version],
/// so changing language cannot bypass, reset, or silently alter consent.
AiTransparencyNotice currentAiTransparencyNoticeForLocale(String? locale) {
  final normalized = locale?.trim().toLowerCase();
  if (normalized == 'en' || normalized?.startsWith('en-') == true) {
    return kCurrentAiTransparencyNoticeEn;
  }
  return kCurrentAiTransparencyNotice;
}

/// Persistence seam + versioning logic for AI transparency-notice
/// acknowledgement (Requirement 7.1, 7.2).
///
/// The acknowledged version is stored under a single secure-storage key,
/// reusing the [SessionSecureStorage] abstraction so production is backed by
/// `flutter_secure_storage` while tests inject an in-memory map.
class AiTransparencyNoticeStore {
  AiTransparencyNoticeStore({SessionSecureStorage? storage})
      : _storage = storage ?? FlutterSecureSessionStorage();

  /// Secure-storage key holding the most recently acknowledged notice version.
  static const String acknowledgedVersionKey =
      'clara.transparency_notice.ack_version';

  final SessionSecureStorage _storage;

  /// The notice version the user most recently acknowledged, or `null` when no
  /// acknowledgement has been recorded.
  Future<String?> acknowledgedVersion() async {
    final value = await _storage.read(acknowledgedVersionKey);
    if (value == null || value.isEmpty) {
      return null;
    }
    return value;
  }

  /// Records acknowledgement of [version], persisting it so the user is not
  /// re-prompted until the current notice version changes.
  Future<void> acknowledge(String version) async {
    await _storage.write(acknowledgedVersionKey, version);
  }

  /// Removes any stored acknowledgement (e.g., on sign-out). After this, the
  /// notice is re-shown on next gated access.
  Future<void> clear() async {
    await _storage.delete(acknowledgedVersionKey);
  }

  /// Whether the current notice still needs acknowledgement.
  ///
  /// Returns `true` when:
  ///   * [acknowledgedVersion] is `null` (never acknowledged), or
  ///   * [acknowledgedVersion] differs from [currentVersion] (a new version was
  ///     published — re-prompt).
  ///
  /// Returns `false` only when the persisted version exactly matches the
  /// current one. A blank [currentVersion] is treated as "no notice configured"
  /// and therefore never requires acknowledgement (fail-open is not possible
  /// here because the gate is itself behind a default-off flag).
  static bool needsAcknowledgement({
    required String currentVersion,
    required String? acknowledgedVersion,
  }) {
    if (currentVersion.isEmpty) {
      return false;
    }
    if (acknowledgedVersion == null || acknowledgedVersion.isEmpty) {
      return true;
    }
    return acknowledgedVersion != currentVersion;
  }
}
