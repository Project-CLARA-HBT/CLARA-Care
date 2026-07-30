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
  onboardingStepWelcome,
  onboardingStepBasics,
  onboardingStepPersonalization,
  onboardingWelcomeTitle,
  onboardingWelcomeDescription,
  onboardingStart,
  onboardingSkip,
  onboardingBasicsTitle,
  onboardingBasicsDescription,
  onboardingDisplayName,
  onboardingGender,
  onboardingPreferNotToSay,
  onboardingGenderFemale,
  onboardingGenderMale,
  onboardingGenderOther,
  onboardingBloodType,
  onboardingBloodTypeUnknown,
  onboardingHeight,
  onboardingWeight,
  onboardingContinue,
  onboardingBack,
  onboardingPersonalizationTitle,
  onboardingPersonalizationDescription,
  onboardingPersonalizationAllow,
  onboardingPersonalizationAllowDescription,
  onboardingSelfDeclaredNotice,
  onboardingSaveFailed,
  lifeMapProfileRequiredTitle,
  lifeMapProfileRequiredDescription,
  lifeMapPersonalPlanNotice,
  lifeMapCareJourneys,
  lifeMapCreateJourney,
  lifeMapCloseForm,
  lifeMapEmptyJourneysTitle,
  lifeMapEmptyJourneysDescription,
  lifeMapAcceptedTasks,
  lifeMapAddTask,
  lifeMapEmptyTasksTitle,
  lifeMapEmptyTasksDescription,
  lifeMapJourneyName,
  lifeMapJourneyNameHint,
  lifeMapGoal,
  lifeMapGoalHint,
  lifeMapPriority,
  lifeMapPriorityRoutine,
  lifeMapPrioritySoon,
  lifeMapPriorityUrgent,
  lifeMapJourneyRequired,
  lifeMapCreateJourneyFailed,
  lifeMapJourneyRequiredForTask,
  lifeMapTaskNameRequired,
  lifeMapAddTaskFailed,
  lifeMapTaskJourney,
  lifeMapUnnamedJourney,
  lifeMapTaskName,
  lifeMapTaskNameHint,
  lifeMapUnnamedTask,
  lifeMapOneQuestion,
  lifeMapViewHistory,
  lifeMapLoadFailed,
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
    // Onboarding copy is deliberately mobile-local rather than shared through
    // the cross-client navigation contract: it describes optional profile
    // fields and consent, not a reusable product-navigation term.
    ConsumerTerm.onboardingStepWelcome: 'Chào mừng',
    ConsumerTerm.onboardingStepBasics: 'Thông tin cơ bản',
    ConsumerTerm.onboardingStepPersonalization: 'Cá nhân hoá',
    ConsumerTerm.onboardingWelcomeTitle: 'Chào mừng bạn đến với CLARA',
    ConsumerTerm.onboardingWelcomeDescription:
        'CLARA là trợ lý sức khoẻ đồng hành cùng bạn theo thời gian — ghi nhớ, '
            'nhắc nhở và giúp bạn chuẩn bị tốt hơn cho mỗi lần khám. CLARA không '
            'thay thế bác sĩ và luôn để bạn nắm quyền kiểm soát dữ liệu của mình.',
    ConsumerTerm.onboardingStart: 'Bắt đầu',
    ConsumerTerm.onboardingSkip: 'Bỏ qua, để sau',
    ConsumerTerm.onboardingBasicsTitle: 'Một vài thông tin cơ bản',
    ConsumerTerm.onboardingBasicsDescription:
        'Tất cả đều không bắt buộc. Bạn có thể bỏ trống và cập nhật bất cứ lúc '
            'nào trong Hồ sơ.',
    ConsumerTerm.onboardingDisplayName: 'Tên hiển thị (không bắt buộc)',
    ConsumerTerm.onboardingGender: 'Giới tính',
    ConsumerTerm.onboardingPreferNotToSay: 'Không muốn nói',
    ConsumerTerm.onboardingGenderFemale: 'Nữ',
    ConsumerTerm.onboardingGenderMale: 'Nam',
    ConsumerTerm.onboardingGenderOther: 'Khác',
    ConsumerTerm.onboardingBloodType: 'Nhóm máu',
    ConsumerTerm.onboardingBloodTypeUnknown: 'Chưa rõ',
    ConsumerTerm.onboardingHeight: 'Chiều cao (cm)',
    ConsumerTerm.onboardingWeight: 'Cân nặng (kg)',
    ConsumerTerm.onboardingContinue: 'Tiếp tục',
    ConsumerTerm.onboardingBack: 'Quay lại',
    ConsumerTerm.onboardingPersonalizationTitle: 'Cá nhân hoá gợi ý cho bạn',
    ConsumerTerm.onboardingPersonalizationDescription:
        'Bạn có thể cho phép CLARA dùng hồ sơ của bạn để cá nhân hoá câu trả '
            'lời và cảnh báo an toàn. Bạn có thể thay đổi lựa chọn này bất cứ lúc nào.',
    ConsumerTerm.onboardingPersonalizationAllow: 'Cho phép cá nhân hoá',
    ConsumerTerm.onboardingPersonalizationAllowDescription:
        'Dùng hồ sơ sức khoẻ để gợi ý phù hợp hơn. Không bắt buộc.',
    ConsumerTerm.onboardingSelfDeclaredNotice:
        'Thông tin bạn nhập là tự khai báo, không phải chẩn đoán y tế. CLARA '
            'hỗ trợ tham khảo và không thay thế tư vấn của bác sĩ.',
    ConsumerTerm.onboardingSaveFailed: 'Không thể lưu. Vui lòng thử lại.',
    ConsumerTerm.lifeMapProfileRequiredTitle: 'Hãy tạo hồ sơ sức khỏe trước',
    ConsumerTerm.lifeMapProfileRequiredDescription:
        'Bạn cần tạo hồ sơ sức khỏe trước khi lập kế hoạch chăm sóc trong '
            'LifeMap. Đây là kế hoạch cá nhân, không phải chẩn đoán.',
    ConsumerTerm.lifeMapPersonalPlanNotice:
        'Đây là kế hoạch cá nhân, không phải chẩn đoán.',
    ConsumerTerm.lifeMapCareJourneys: 'Hành trình chăm sóc',
    ConsumerTerm.lifeMapCreateJourney: 'Tạo hành trình',
    ConsumerTerm.lifeMapCloseForm: 'Đóng',
    ConsumerTerm.lifeMapEmptyJourneysTitle: 'Chưa có hành trình nào',
    ConsumerTerm.lifeMapEmptyJourneysDescription:
        'Tạo một hành trình chăm sóc để nhóm các việc bạn muốn theo dõi. '
            'Đây là kế hoạch cá nhân, không phải chẩn đoán.',
    ConsumerTerm.lifeMapAcceptedTasks: 'Việc đã chấp nhận',
    ConsumerTerm.lifeMapAddTask: 'Thêm việc',
    ConsumerTerm.lifeMapEmptyTasksTitle: 'Chưa có việc nào',
    ConsumerTerm.lifeMapEmptyTasksDescription:
        'Thêm một việc dưới một hành trình. Sau khi chấp nhận, việc sẽ xuất '
            'hiện trong mục Hôm nay để bạn hoàn tất.',
    ConsumerTerm.lifeMapJourneyName: 'Tên hành trình',
    ConsumerTerm.lifeMapJourneyNameHint: 'Ví dụ: Theo dõi huyết áp',
    ConsumerTerm.lifeMapGoal: 'Mục tiêu (không bắt buộc)',
    ConsumerTerm.lifeMapGoalHint: 'Điều bạn mong muốn đạt được',
    ConsumerTerm.lifeMapPriority: 'Mức ưu tiên',
    ConsumerTerm.lifeMapPriorityRoutine: 'Khi thuận tiện',
    ConsumerTerm.lifeMapPrioritySoon: 'Sớm',
    ConsumerTerm.lifeMapPriorityUrgent: 'Cần ưu tiên',
    ConsumerTerm.lifeMapJourneyRequired: 'Vui lòng nhập tên hành trình.',
    ConsumerTerm.lifeMapCreateJourneyFailed:
        'Không thể tạo hành trình. Vui lòng thử lại.',
    ConsumerTerm.lifeMapJourneyRequiredForTask: 'Vui lòng chọn một hành trình.',
    ConsumerTerm.lifeMapTaskNameRequired: 'Vui lòng nhập tên việc.',
    ConsumerTerm.lifeMapAddTaskFailed: 'Không thể thêm việc. Vui lòng thử lại.',
    ConsumerTerm.lifeMapTaskJourney: 'Thuộc hành trình',
    ConsumerTerm.lifeMapUnnamedJourney: 'Hành trình chưa đặt tên',
    ConsumerTerm.lifeMapTaskName: 'Tên việc',
    ConsumerTerm.lifeMapTaskNameHint: 'Ví dụ: Đo huyết áp buổi sáng',
    ConsumerTerm.lifeMapUnnamedTask: 'Việc chưa đặt tên',
    ConsumerTerm.lifeMapOneQuestion: 'Một câu hỏi',
    ConsumerTerm.lifeMapViewHistory: 'Xem lịch sử',
    ConsumerTerm.lifeMapLoadFailed: 'Không thể tải LifeMap. Vui lòng thử lại.',
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
    ConsumerTerm.onboardingStepWelcome: 'Welcome',
    ConsumerTerm.onboardingStepBasics: 'Basic details',
    ConsumerTerm.onboardingStepPersonalization: 'Personalization',
    ConsumerTerm.onboardingWelcomeTitle: 'Welcome to CLARA',
    ConsumerTerm.onboardingWelcomeDescription:
        'CLARA is a health assistant that stays with you over time — helping '
            'you remember, prepare, and make the most of each visit. CLARA does '
            'not replace a doctor, and you remain in control of your data.',
    ConsumerTerm.onboardingStart: 'Get started',
    ConsumerTerm.onboardingSkip: 'Skip for now',
    ConsumerTerm.onboardingBasicsTitle: 'A few basic details',
    ConsumerTerm.onboardingBasicsDescription:
        'Everything is optional. You can leave it blank and update it anytime '
            'in Profile.',
    ConsumerTerm.onboardingDisplayName: 'Display name (optional)',
    ConsumerTerm.onboardingGender: 'Gender',
    ConsumerTerm.onboardingPreferNotToSay: 'Prefer not to say',
    ConsumerTerm.onboardingGenderFemale: 'Female',
    ConsumerTerm.onboardingGenderMale: 'Male',
    ConsumerTerm.onboardingGenderOther: 'Other',
    ConsumerTerm.onboardingBloodType: 'Blood type',
    ConsumerTerm.onboardingBloodTypeUnknown: 'Unknown',
    ConsumerTerm.onboardingHeight: 'Height (cm)',
    ConsumerTerm.onboardingWeight: 'Weight (kg)',
    ConsumerTerm.onboardingContinue: 'Continue',
    ConsumerTerm.onboardingBack: 'Back',
    ConsumerTerm.onboardingPersonalizationTitle: 'Personalize your guidance',
    ConsumerTerm.onboardingPersonalizationDescription:
        'You can let CLARA use your profile to tailor answers and safety '
            'warnings. You can change this choice at any time.',
    ConsumerTerm.onboardingPersonalizationAllow: 'Allow personalization',
    ConsumerTerm.onboardingPersonalizationAllowDescription:
        'Use your health profile for more relevant guidance. This is optional.',
    ConsumerTerm.onboardingSelfDeclaredNotice:
        'The information you enter is self-declared and is not a medical '
            'diagnosis. CLARA offers general support and does not replace your doctor.',
    ConsumerTerm.onboardingSaveFailed:
        'We could not save this. Please try again.',
    ConsumerTerm.lifeMapProfileRequiredTitle: 'Create your health profile first',
    ConsumerTerm.lifeMapProfileRequiredDescription:
        'Create your health profile before making a care plan in LifeMap. '
            'This is a personal plan, not a diagnosis.',
    ConsumerTerm.lifeMapPersonalPlanNotice:
        'This is a personal plan, not a diagnosis.',
    ConsumerTerm.lifeMapCareJourneys: 'Care journeys',
    ConsumerTerm.lifeMapCreateJourney: 'Create journey',
    ConsumerTerm.lifeMapCloseForm: 'Close',
    ConsumerTerm.lifeMapEmptyJourneysTitle: 'No care journeys yet',
    ConsumerTerm.lifeMapEmptyJourneysDescription:
        'Create a care journey to group the things you want to track. This is '
            'a personal plan, not a diagnosis.',
    ConsumerTerm.lifeMapAcceptedTasks: 'Accepted tasks',
    ConsumerTerm.lifeMapAddTask: 'Add task',
    ConsumerTerm.lifeMapEmptyTasksTitle: 'No tasks yet',
    ConsumerTerm.lifeMapEmptyTasksDescription:
        'Add a task to a care journey. Once accepted, it appears in Today for '
            'you to complete.',
    ConsumerTerm.lifeMapJourneyName: 'Journey name',
    ConsumerTerm.lifeMapJourneyNameHint: 'For example: Track blood pressure',
    ConsumerTerm.lifeMapGoal: 'Goal (optional)',
    ConsumerTerm.lifeMapGoalHint: 'What would you like to achieve?',
    ConsumerTerm.lifeMapPriority: 'Priority',
    ConsumerTerm.lifeMapPriorityRoutine: 'When convenient',
    ConsumerTerm.lifeMapPrioritySoon: 'Soon',
    ConsumerTerm.lifeMapPriorityUrgent: 'Needs priority',
    ConsumerTerm.lifeMapJourneyRequired: 'Enter a journey name.',
    ConsumerTerm.lifeMapCreateJourneyFailed:
        'We could not create the journey. Try again.',
    ConsumerTerm.lifeMapJourneyRequiredForTask: 'Choose a care journey.',
    ConsumerTerm.lifeMapTaskNameRequired: 'Enter a task name.',
    ConsumerTerm.lifeMapAddTaskFailed: 'We could not add the task. Try again.',
    ConsumerTerm.lifeMapTaskJourney: 'Care journey',
    ConsumerTerm.lifeMapUnnamedJourney: 'Unnamed care journey',
    ConsumerTerm.lifeMapTaskName: 'Task name',
    ConsumerTerm.lifeMapTaskNameHint: 'For example: Measure blood pressure in the morning',
    ConsumerTerm.lifeMapUnnamedTask: 'Unnamed task',
    ConsumerTerm.lifeMapOneQuestion: 'One question',
    ConsumerTerm.lifeMapViewHistory: 'View history',
    ConsumerTerm.lifeMapLoadFailed:
        'We could not load LifeMap. Try again.',
  };
}
