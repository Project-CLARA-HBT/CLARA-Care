/// Versioned, Vietnamese-first terminology shared by CLARA's consumer shells.
///
/// This is deliberately product wording rather than clinical terminology. It
/// must not be used to translate clinical free text, medication names, API
/// errors, a LifeMap truth state, or consent/RBAC decisions. Those values stay
/// canonical and are rendered by their owning safety-aware surfaces.
///
/// The keys in this contract mirror the stable consumer terms in
/// `apps/web/lib/i18n/catalog.ts`. Keeping the public key names identical lets
/// a future catalog generator consume this contract without changing callers.
/// See `docs/architecture/mobile-consumer-terminology-contract-v1.md`.
library;

import 'consumer_terminology.generated.dart';

/// Version of the cross-client terminology contract.
const String kConsumerTerminologyVersion = kConsumerTerminologyContractVersion;

/// Stable terms shared across task-first consumer surfaces.
///
/// Do not rename an existing key: add a new one and retain the old key for the
/// duration of the mobile release window. This keeps an older client safe when
/// it receives a newer server or web deployment.
enum ConsumerTerm {
  actionAskClara,
  actionComplete,
  actionOpen,
  actionRetry,
  navigationToday,
  navigationLifeMap,
  navigationMedicines,
  navigationProfile,
  todayTitle,
  todayOpenLifeMap,
  todayPending,
  todayAccepted,
  todayEpisodes,
  todayConfirmation,
  todayNoDueDate,
  todayDueDate,
  todayEmptyTitle,
  todayEmptyDescription,
  todayUnnamedTask,
  todayProfileRequiredTitle,
  todayProfileRequiredDescription,
  todayCreateProfile,
  todayOfflineStale,
  todayOfflineFresh,
  todayOfflineActionBlocked,
  todayCompleteFailed,
  todayLoadFailed,
  sessionExpired,
}

extension ConsumerTermContractKey on ConsumerTerm {
  /// Key in the cross-client static terminology contract, when this is a
  /// shared product term. Terms not listed here remain mobile-only wording.
  String? get contractKey => switch (this) {
        ConsumerTerm.actionAskClara => 'action.askClara',
        ConsumerTerm.actionComplete => 'action.complete',
        ConsumerTerm.actionOpen => 'action.open',
        ConsumerTerm.actionRetry => 'action.retry',
        ConsumerTerm.navigationToday => 'navigation.today',
        ConsumerTerm.navigationLifeMap => 'navigation.lifeMap',
        ConsumerTerm.navigationMedicines => 'navigation.medicines',
        ConsumerTerm.navigationProfile => 'navigation.profile',
        ConsumerTerm.todayTitle => 'today.title',
        ConsumerTerm.todayOpenLifeMap => 'today.openLifeMap',
        ConsumerTerm.todayPending => 'today.pending',
        ConsumerTerm.todayAccepted => 'today.accepted',
        ConsumerTerm.todayEpisodes => 'today.episodes',
        ConsumerTerm.todayConfirmation => 'today.confirmation',
        ConsumerTerm.todayNoDueDate => 'today.noDueDate',
        ConsumerTerm.todayDueDate => 'today.dueDate',
        ConsumerTerm.todayEmptyTitle => 'today.emptyTitle',
        ConsumerTerm.todayEmptyDescription => 'today.emptyDescription',
        _ => null,
      };
}

/// Resolves static consumer copy for a single locale.
///
/// The resolver intentionally accepts an arbitrary locale string because the
/// persisted preference may be restored before a controller is normalized.
/// Only `en` selects English. Every other value, including null, falls back to
/// Vietnamese so CLARA remains usable and Vietnamese-first at runtime.
class ConsumerTerminology {
  const ConsumerTerminology._(this.locale, this._messages);

  factory ConsumerTerminology.forLocale(String? requestedLocale) {
    final normalized = requestedLocale?.trim().toLowerCase();
    if (normalized == 'en' || normalized?.startsWith('en-') == true) {
      return const ConsumerTerminology._('en', _enMessages);
    }
    return const ConsumerTerminology._('vi', _viMessages);
  }

  /// The normalized resolved locale (`vi` or `en`).
  final String locale;
  final Map<ConsumerTerm, String> _messages;

  /// Returns a complete static message for [term].
  String operator [](ConsumerTerm term) {
    final sharedKey = term.contractKey;
    final shared = sharedKey == null
        ? null
        : kConsumerTerminologyMessages[locale]?[sharedKey];
    return shared ?? _messages[term]!;
  }

  /// Applies simple named placeholders to a static product message.
  ///
  /// Missing values deliberately remain visible (`{name}`) rather than being
  /// silently discarded; that makes a wiring regression obvious without
  /// inventing health content.
  String format(ConsumerTerm term, Map<String, Object?> values) {
    return this[term].replaceAllMapped(RegExp(r'\{(\w+)\}'), (match) {
      final value = values[match.group(1)];
      return value == null ? match.group(0)! : value.toString();
    });
  }

  static const Map<ConsumerTerm, String> _viMessages = {
    ConsumerTerm.todayUnnamedTask: 'Việc chưa đặt tên',
    ConsumerTerm.todayProfileRequiredTitle: 'Hãy tạo hồ sơ sức khỏe trước',
    ConsumerTerm.todayProfileRequiredDescription:
        'Để CLARA gợi ý và theo dõi các việc chăm sóc cá nhân, bạn cần tạo hồ '
            'sơ sức khỏe. Đây là kế hoạch cá nhân, không phải chẩn đoán.',
    ConsumerTerm.todayCreateProfile: 'Tạo hồ sơ sức khỏe',
    ConsumerTerm.todayOfflineStale:
        'Ngoại tuyến · dữ liệu đã cũ · không thể thực hiện thay đổi.',
    ConsumerTerm.todayOfflineFresh:
        'Ngoại tuyến · lưu lúc {timestamp} · không thể thực hiện thay đổi.',
    ConsumerTerm.todayOfflineActionBlocked:
        'Bạn đang ngoại tuyến. Kết nối mạng để hoàn tất việc này.',
    ConsumerTerm.todayCompleteFailed:
        'Không thể hoàn tất việc này. Vui lòng thử lại.',
    ConsumerTerm.todayLoadFailed:
        'Không thể tải lịch hôm nay. Vui lòng thử lại.',
    ConsumerTerm.sessionExpired:
        'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
  };

  static const Map<ConsumerTerm, String> _enMessages = {
    ConsumerTerm.todayUnnamedTask: 'Unnamed task',
    ConsumerTerm.todayProfileRequiredTitle: 'Create your health profile first',
    ConsumerTerm.todayProfileRequiredDescription:
        'To let CLARA suggest and track personal care tasks, create a health '
            'profile first. This is a personal plan, not a diagnosis.',
    ConsumerTerm.todayCreateProfile: 'Create health profile',
    ConsumerTerm.todayOfflineStale:
        'Offline · data is stale · changes are unavailable.',
    ConsumerTerm.todayOfflineFresh:
        'Offline · saved at {timestamp} · changes are unavailable.',
    ConsumerTerm.todayOfflineActionBlocked:
        'You are offline. Connect to complete this task.',
    ConsumerTerm.todayCompleteFailed:
        'We could not complete this task. Try again.',
    ConsumerTerm.todayLoadFailed:
        'We could not load today\'s agenda. Try again.',
    ConsumerTerm.sessionExpired:
        'Your session has expired. Please sign in again.',
  };
}
