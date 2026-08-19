/// Versioned, Vietnamese-first terminology shared by CLARA's consumer shells.
///
/// This is deliberately product wording rather than clinical terminology. It
/// must not be used to translate clinical free text, medication names, API
/// errors, a LifeMap truth state, or consent/RBAC decisions. Those values stay
/// canonical and are rendered by their owning safety-aware surfaces.
///
/// The keys in this contract mirror the stable consumer terms in
/// `apps/web/lib/i18n/catalog.ts`. The checked-in web and Flutter projections
/// are generated from one JSON source without changing callers.
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
  navigationMore,
  homeScreenToolsTitle,
  homeScreenToolsLoadFailed,
  homeScreenRecentTitle,
  homeScreenNoRecentTitle,
  homeScreenNoRecentDescription,
  homeNextActionTitle,
  homeSeverityCritical,
  homeSeverityUrgent,
  homeSeverityAttention,
  homeSeverityNormal,
  homeSeverityRoutine,
  homeAskPlaceholder,
  homeAskCamera,
  homeAskVoice,
  homeAskText,
  homeScheduleTitle,
  homeScheduleEmpty,
  homeScheduleMedication,
  homeScheduleVisit,
  homeScheduleTask,
  homeRecentChangesTitle,
  homeRecentChangesEmpty,
  homeRecentChangesRealSourceNotice,
  homeCaughtUpTitle,
  homeCaughtUpDescription,
  homeProfessionalTools,
  homeProfessionalDrawer,
  profileHubToolsAndPrivacy,
  profileHubVisitsTitle,
  profileHubVisitsDescription,
  profileHubFamilyTitle,
  profileHubFamilyDescription,
  profileHubEvidenceTitle,
  profileHubEvidenceDescription,
  profileHubCommunityTitle,
  profileHubCommunityDescription,
  profileHubHealthDataTitle,
  profileHubHealthDataDescription,
  profileHubClinicalNotesTitle,
  profileHubClinicalNotesDescription,
  profileHubCaseConsultationTitle,
  profileHubCaseConsultationDescription,
  profileHubConsentTitle,
  profileHubConsentDescription,
  profileHubDataRightsTitle,
  profileHubDataRightsDescription,
  profileHubSettingsTitle,
  profileHubSettingsDescription,
  todayTitle,
  todayStartHereTitle,
  todayStartHereDescription,
  todayAskHealthTitle,
  todayAskHealthDescription,
  todayCheckMedicineTitle,
  todayCheckMedicineDescription,
  todaySaveHealthInfoTitle,
  todaySaveHealthInfoDescription,
  todayPrepareVisitTitle,
  todayPrepareVisitDescription,
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
  // Authentication is mobile-local chrome. It must not translate server error
  // payloads, account identity, or consent/RBAC decisions.
  loginSafetyTagline,
  loginEmail,
  loginPassword,
  loginShowPassword,
  loginHidePassword,
  loginSubmit,
  loginCreateAccount,
  loginForgotPassword,
  loginEmailRequired,
  loginPasswordRequired,
  loginUnauthorized,
  loginFailed,
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
  lifeMapReplayLabel,
  lifeMapReplayFallbackTitle,
  lifeMapReplayDescription,
  lifeMapReplayStale,
  lifeMapReplayEmptyTitle,
  lifeMapReplayEmptyDescription,
  lifeMapReplayVersion,
  lifeMapReplayWhy,
  lifeMapReplayEdit,
  lifeMapReplayDispute,
  lifeMapReplayLoadFailed,
  lifeMapCorrectionTitle,
  lifeMapCorrectionNotice,
  lifeMapCorrectionLabel,
  lifeMapCorrectionSave,
  lifeMapCorrectionSaved,
  lifeMapMutationOffline,
  lifeMapDisputeTitle,
  lifeMapDisputeNotice,
  lifeMapDisputeLabel,
  lifeMapDisputeSubmit,
  lifeMapDisputeSubmitted,
  lifeMapDisputeQueueTitle,
  lifeMapDisputeQueueNotice,
  lifeMapDisputeQueueVersion,
  lifeMapDisputeQueueOpen,
  lifeMapDisputeQueueResolved,
  lifeMapDisputeQueueClinicalReview,
  lifeMapDisputeQueueResolve,
  lifeMapSummarySectionTitle,
  lifeMapSummaryDescription,
  lifeMapSummaryScope,
  lifeMapSummaryDay,
  lifeMapSummaryWeek,
  lifeMapSummarySelectedJourney,
  lifeMapSummaryCreate,
  lifeMapSummaryEmpty,
  lifeMapSummaryCitation,
  lifeMapSummarySafetyNotice,
  lifeMapSummaryLoadFailed,
  lifeMapReviewSectionTitle,
  lifeMapReviewDescription,
  lifeMapReviewCheck,
  lifeMapReviewPossibleContradiction,
  lifeMapReviewPossibleDuplicate,
  lifeMapReviewNeedsMoreInformation,
  lifeMapReviewBasedOnSavedRecords,
  lifeMapReviewResolved,
  lifeMapReviewDismiss,
  lifeMapReviewRecorded,
  lifeMapReviewLoadFailed,
  lifeMapCaptureSectionTitle,
  lifeMapCaptureCreateDescription,
  lifeMapCaptureInputLabel,
  lifeMapCaptureInputHint,
  lifeMapCaptureCreate,
  lifeMapCaptureArtifactTitle,
  lifeMapCaptureArtifactDescription,
  lifeMapCaptureSourceType,
  lifeMapCaptureMedicationLabel,
  lifeMapCaptureVisitDocument,
  lifeMapCaptureTakePhoto,
  lifeMapCaptureChoosePhoto,
  lifeMapCaptureCreateFailed,
  lifeMapCaptureImageInvalid,
  lifeMapCaptureUploading,
  lifeMapCaptureReading,
  lifeMapCaptureUploadFailed,
  lifeMapCaptureReadingFailed,
  lifeMapCaptureJobPending,
  lifeMapCaptureRefreshFailed,
  lifeMapCaptureConfirmFailed,
  lifeMapCaptureAbandonOffline,
  lifeMapCaptureEmergencyFallback,
  lifeMapCaptureDeleteSourceDraft,
  lifeMapCaptureDraft,
  lifeMapCaptureRejected,
  lifeMapCaptureConfirmed,
  lifeMapCaptureOnlineNotice,
  lifeMapCaptureLowConfidence,
  lifeMapCaptureMissingFields,
  lifeMapCaptureUnsafe,
  lifeMapCaptureNormalizeTitle,
  lifeMapCaptureNormalizeLoading,
  lifeMapCaptureNormalizeUnavailable,
  lifeMapCaptureNormalizeProposal,
  lifeMapCaptureNormalizeUseCode,
  lifeMapCaptureNormalizeUseCodeNotice,
  lifeMapCaptureEdit,
  lifeMapCaptureReject,
  lifeMapCaptureConfirm,
  lifeMapCaptureAbandon,
  lifeMapCaptureProcessing,
  lifeMapCaptureCheckResult,
  lifeMapCaptureEditTitle,
  lifeMapCaptureEditSave,
  lifeMapCaptureSourceImageLabel,
  lifeMapCaptureSourcePreviewError,
  lifeMapCaptureSourcePreview,
  lifeMapCaptureSourceUncached,
  lifeMapAskSectionTitle,
  lifeMapAskSafetyNotice,
  lifeMapAskInputLabel,
  lifeMapAskInputHint,
  lifeMapAskInputHelp,
  lifeMapAskSubmit,
  lifeMapAskCitation,
  lifeMapAskAnswerSafetyNotice,
  lifeMapAskLoadFailed,
  lifeMapQuestionNoneNeeded,
  lifeMapQuestionWhy,
  lifeMapQuestionAnswerLabel,
  lifeMapQuestionAnswerHelp,
  lifeMapQuestionLater,
  lifeMapQuestionCreateDraft,
  lifeMapQuestionDraftCreated,
  lifeMapQuestionLoadFailed,
  lifeMapBaselineSectionTitle,
  lifeMapBaselineNotice,
  lifeMapBaselineSamples,
  lifeMapBaselineInsufficientData,
  medicinesMyMedicines,
  medicinesCabinet,
  medicinesSafety,
  medicinesLoginRequired,
  medicinesLoadFailed,
  medicinesProfileRequiredTitle,
  medicinesProfileRequiredDescription,
  medicinesReload,
  medicinesEmptyTitle,
  medicinesEmptyDescription,
  medicinesAdd,
  medicinesUnnamed,
  medicinesEnded,
  medicinesActive,
  medicinesSourceMatched,
  medicinesUnverified,
  medicinesActionsTooltip,
  medicinesEditNewVersion,
  medicinesEndCourse,
  medicinesEndConfirmTitle,
  medicinesEndConfirmDescription,
  medicinesEndAuditReason,
  medicinesCancel,
  medicinesConfirm,
  medicinesNameRequired,
  medicinesLoginToAdd,
  medicinesEditReasonRequired,
  medicinesSaveFailed,
  medicinesAddTitle,
  medicinesEditTitle,
  medicinesNameLabel,
  medicinesNameHint,
  medicinesDoseLabel,
  medicinesDoseHint,
  medicinesScheduleLabel,
  medicinesScheduleHint,
  medicinesRouteLabel,
  medicinesRouteHint,
  medicinesFormLabel,
  medicinesFormHint,
  medicinesEditReasonLabel,
  medicinesEditReasonHint,
  medicinesSave,
  medicinesSaveNewVersion,
  medicinesSafetyTitle,
  medicinesSafetyDescription,
  medicinesOpenCabinet,
  medicinesSafetyNotice,
  visitsTitle,
  visitsCreate,
  visitsClose,
  visitsProfileRequiredTitle,
  visitsProfileRequiredDescription,
  visitsEmptyTitle,
  visitsEmptyDescription,
  visitsSafetyLabel,
  visitsSafetyNotice,
  visitsNameLabel,
  visitsNameHint,
  visitsReasonLabel,
  visitsReasonHint,
  visitsUnnamed,
  visitsPreparationTitle,
  visitsOpenPreparation,
  visitsNoSchedule,
  visitsScheduledDate,
  visitsNameRequired,
  visitsLoadFailed,
  visitsCreateFailed,
  visitDraftTitle,
  visitDraftDescription,
  visitDraftGoalLabel,
  visitDraftGoalHint,
  visitDraftCreate,
  visitDraftCreating,
  visitDraftReviewNotice,
  visitDraftImportantNow,
  visitDraftSources,
  visitDraftNoSources,
  visitDraftUncertainty,
  visitDraftNoUncertainty,
  visitDraftNextStep,
  visitDraftUrgentHelp,
  visitDraftQuestions,
  visitDraftNoQuestions,
  visitDraftCopy,
  visitDraftCopied,
  visitDraftCreateFailed,
  visitDetailPreparationNotice,
  visitDetailConcernsTitle,
  visitDetailConcernLabel,
  visitDetailSaveConcern,
  visitDetailDocumentsTitle,
  visitDetailDocumentsDescription,
  visitDetailDocumentTitle,
  visitDetailDocumentContent,
  visitDetailSaveDocument,
  visitDetailInactiveDocument,
  visitDetailControlledDocument,
  visitDetailCheckPlan,
  visitDetailWithdrawDocument,
  visitDetailDeleteDocument,
  visitDetailReviewTitle,
  visitDetailNoEvidence,
  visitDetailReviewGuidance,
  visitDetailSource,
  visitDetailUnconfirmableCandidate,
  visitDetailConfirmSelected,
  visitDetailWithdrawDraft,
  visitDetailPackTitle,
  visitDetailPackNotice,
  visitDetailNoMatchingItems,
  visitDetailPackConcerns,
  visitDetailPackMedications,
  visitDetailPackEpisodes,
  visitDetailPackEvents,
  visitDetailPackInstructions,
  visitDetailCreatePack,
  visitDetailCreateNewPackVersion,
  visitDetailApprovedPackVersion,
  visitDetailCreateShare,
  visitDetailRevokeShare,
  visitDetailScribeConsentTitle,
  visitDetailScribeConsentDescription,
  visitDetailScribeConsentGranted,
  visitDetailScribeConsentNotGranted,
  visitDetailLoadFailed,
  visitDetailActionFailed,
  visitDetailConcernRequired,
  visitDetailDocumentRequired,
  familyTitle,
  familySupporter,
  familyNewNotification,
  familyAccessGrant,
  familyInvite,
  familyClose,
  familySharingNoteSemanticLabel,
  familySharingNote,
  familySharedWith,
  familyEmptyTitle,
  familyEmptyDescription,
  familyNotifications,
  familyActiveGrants,
  familyAccessLog,
  familyAccessLogActorOwner,
  familyAccessLogActorSupporter,
  familyAccessLogActorSystem,
  familyAccessLogActorOther,
  familyAccessLogActionView,
  familyAccessLogActionAddObservation,
  familyAccessLogActionCompleteTask,
  familyAccessLogActionInvitationAccept,
  familyAccessLogActionGrantRevoke,
  familyAccessLogActionGrantRenewalInvited,
  familyAccessLogActionNotificationAcknowledged,
  familyAccessLogActionOther,
  familyAccessLogOutcomeAllowed,
  familyAccessLogOutcomeDenied,
  familyAccessLogOutcomeFailed,
  familyAccessLogOutcomeUnknown,
  familyEmailLabel,
  familyEmailHint,
  familyScopeLabel,
  familyScopeJourney,
  familyScopeVisit,
  familySharedItemLabel,
  familyPurposeLabel,
  familyPurposeCareCoordination,
  familyPurposeVisitSupport,
  familySendInvitation,
  familyInvitationTokenNotice,
  familyAcknowledge,
  familyExpiresAt,
  familyRenew,
  familyRevoke,
  familyRevokeConfirmTitle,
  familyRevokeConfirmDescription,
  familyCancel,
  familyEmailRequired,
  familySharedItemRequired,
  familyInvitationCreated,
  familyInvitationFailed,
  familyNotificationUnavailable,
  familyAcknowledgeFailed,
  familyGrantUnavailable,
  familyRevoked,
  familyRevokeFailed,
  familyRenewed,
  familyRenewFailed,
  familyLoadFailed,
  familyUseInvitationCode,
  familyInvitationAcceptTitle,
  familyInvitationAcceptDescription,
  familyInvitationCodeLabel,
  familyInvitationCodeHint,
  familyInvitationCodeRequired,
  familyPreviewInvitation,
  familyPreviewingInvitation,
  familyInvitationPreviewTitle,
  familyInvitationPreviewNotice,
  familyInvitationScopeLabel,
  familyInvitationActionsLabel,
  familyInvitationExpiryUnavailable,
  familyInvitationScopeCareTask,
  familyInvitationActionView,
  familyInvitationActionAddObservation,
  familyInvitationActionCompleteTask,
  familyInvitationActionOther,
  familyInvitationPreviewFailed,
  familyInvitationAccept,
  familyAcceptingInvitation,
  familyInvitationAccepted,
  familyInvitationAcceptFailed,
  connectedHealthTitle,
  connectedHealthIntroTitle,
  connectedHealthIntroDescription,
  connectedHealthSourcesTitle,
  connectedHealthBeforeConnectingTitle,
  connectedHealthChooseDataTitle,
  connectedHealthChooseDataDescription,
  connectedHealthPrivateDataTitle,
  connectedHealthPrivateDataDescription,
  connectedHealthEmptyTitle,
  connectedHealthEmptyDescription,
  connectedHealthFallbackSourceTitle,
  connectedHealthAllowedData,
  connectedHealthPause,
  connectedHealthResume,
  connectedHealthDisconnect,
  connectedHealthDeleteImportedData,
  connectedHealthStatusHealthy,
  connectedHealthStatusConnected,
  connectedHealthStatusPaused,
  connectedHealthStatusNeedsReauth,
  connectedHealthStatusDisconnected,
  connectedHealthStatusUnknown,
  connectedHealthLoadFailedTitle,
  connectedHealthDisconnectConfirmTitle,
  connectedHealthDisconnectConfirmDescription,
  connectedHealthDisconnectConfirmAction,
  connectedHealthDeleteConfirmTitle,
  connectedHealthDeleteConfirmDescription,
  connectedHealthDeleteConfirmAction,
  connectedHealthDeleteSuccess,
  connectedHealthCancel,
  livingEvidenceTitle,
  livingEvidenceSafetyNotice,
  livingEvidenceReviewedChanges,
  livingEvidenceNotificationSemanticLabel,
  livingEvidenceRead,
  livingEvidenceMarkRead,
  livingEvidenceSubscriptions,
  livingEvidenceEmptyTitle,
  livingEvidenceEmptyDescription,
  livingEvidenceNewQuestion,
  livingEvidenceJourneyLabel,
  livingEvidenceQuestionLabel,
  livingEvidenceContextLabel,
  livingEvidenceCreateAndFollow,
  livingEvidenceLoadFailed,
  livingEvidenceRunIncomplete,
  livingEvidenceCreateFailed,
  livingEvidenceIntervalFailed,
  livingEvidenceStopFailed,
  livingEvidenceSubscriptionTitle,
  livingEvidenceApplicabilityPending,
  livingEvidenceNoContradictions,
  livingEvidenceContradictionsCount,
  livingEvidenceIntervalLabel,
  livingEvidenceEveryDay,
  livingEvidenceEveryWeek,
  livingEvidenceEveryThirtyDays,
  livingEvidenceStopFollowing,
  // Community wording is mobile-local static UI copy. It never translates
  // member posts, moderation results, or any health/PHR data from the API.
  socialSessionExpired,
  socialLoadFailed,
  socialNoCommunities,
  socialConsentTitle,
  socialConsentDescription,
  socialConsentAgree,
  socialLater,
  socialTitle,
  socialProfileTooltip,
  socialPost,
  socialConsentCardSemanticLabel,
  socialConsentCardTitle,
  socialConsentCardDescription,
  socialJoin,
  socialCommunities,
  socialFeed,
  socialEmptyFeed,
  socialReactionSent,
  socialReactionHelpful,
  socialAnonymous,
  socialDisclaimer,
  socialMembers,
  socialJoined,
  socialUnavailableTitle,
  socialUnavailableDescription,
  socialComposeTitle,
  socialCommunityLabel,
  socialPostTitleLabel,
  socialPostBodyLabel,
  socialComposeRequired,
  socialComments,
  socialEmptyComments,
  socialCommentLabel,
  socialCommentJoinRequired,
  socialModerationBlocked,
  socialReportTitle,
  socialReportDescription,
  socialCancel,
  socialReport,
  socialReportSent,
  socialClose,
  socialProfileTitle,
  socialDisplayNameLabel,
  socialBioLabel,
  socialSaveProfile,
  socialProfileSaved,
  socialDoctor,
  socialResearcher,
  // Settings and More are mobile-owned navigation and safety-copy surfaces.
  // These strings never translate identity, health, consent or model data
  // supplied by the API; those values remain canonical.
  moreTitle,
  moreOtherToolsTitle,
  settingsTitle,
  settingsAppearanceTitle,
  settingsThemeLight,
  settingsThemeDark,
  settingsThemeSystem,
  settingsLanguageTitle,
  settingsSelected,
  settingsNotSelected,
  settingsAccountTitle,
  settingsEmailLabel,
  settingsRoleLabel,
  settingsNoInformation,
  settingsRoleConsumer,
  settingsRoleResearcher,
  settingsRoleDoctor,
  settingsRoleAdmin,
  settingsSignOut,
  settingsSignOutConfirmTitle,
  settingsSignOutConfirmDescription,
  settingsCancel,
  settingsPrivacyTitle,
  settingsPrivacyDescription,
  settingsTransparencyTitle,
  settingsAiModelLabel,
  settingsAiModelGovernedRoute,
  settingsAboutTitle,
  settingsVersion,
  settingsAboutDescription,
  settingsHelpTitle,
  settingsHelpDescription,
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
        ConsumerTerm.navigationMore => 'navigation.more',
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
    ConsumerTerm.homeScreenToolsTitle: 'Công cụ',
    ConsumerTerm.homeScreenToolsLoadFailed:
        'Không thể tải danh sách công cụ. Vui lòng thử lại.',
    ConsumerTerm.homeScreenRecentTitle: 'Gần đây',
    ConsumerTerm.homeScreenNoRecentTitle: 'Chưa có hoạt động gần đây',
    ConsumerTerm.homeScreenNoRecentDescription:
        'Các hoạt động gần đây của bạn sẽ xuất hiện ở đây.',
    ConsumerTerm.homeNextActionTitle: 'Việc nên làm tiếp theo',
    ConsumerTerm.homeSeverityCritical: 'Khẩn cấp',
    ConsumerTerm.homeSeverityUrgent: 'Khẩn cấp',
    ConsumerTerm.homeSeverityAttention: 'Cần chú ý',
    ConsumerTerm.homeSeverityNormal: 'Gợi ý',
    ConsumerTerm.homeSeverityRoutine: 'Thường quy',
    ConsumerTerm.homeAskPlaceholder:
        'Hỏi CLARA về sức khỏe, triệu chứng, đơn thuốc...',
    ConsumerTerm.homeAskCamera: 'Chụp ảnh nhãn thuốc hoặc kết quả',
    ConsumerTerm.homeAskVoice: 'Nói câu hỏi',
    ConsumerTerm.homeAskText: 'Gửi câu hỏi',
    ConsumerTerm.homeScheduleTitle: 'Lịch hôm nay',
    ConsumerTerm.homeScheduleEmpty: 'Không có lịch trình nào hôm nay',
    ConsumerTerm.homeScheduleMedication: 'Thuốc',
    ConsumerTerm.homeScheduleVisit: 'Khám bệnh',
    ConsumerTerm.homeScheduleTask: 'Việc chăm sóc',
    ConsumerTerm.homeRecentChangesTitle: 'Thay đổi gần đây',
    ConsumerTerm.homeRecentChangesEmpty:
        'Chưa có thay đổi nào được ghi nhận',
    ConsumerTerm.homeRecentChangesRealSourceNotice:
        'Từ nguồn dữ liệu thực tế',
    ConsumerTerm.homeCaughtUpTitle: 'Bạn đã hoàn thành các việc hôm nay',
    ConsumerTerm.homeCaughtUpDescription:
        'Các việc hoàn tất đã được ghi nhận. Bạn có thể nghỉ ngơi hoặc cập nhật nếu có thay đổi.',
    ConsumerTerm.homeProfessionalTools: 'Công cụ chuyên môn',
    ConsumerTerm.homeProfessionalDrawer: 'Menu chuyên môn',
    ConsumerTerm.profileHubToolsAndPrivacy: 'Công cụ & quyền riêng tư',
    ConsumerTerm.profileHubVisitsTitle: 'Chuẩn bị đi khám',
    ConsumerTerm.profileHubVisitsDescription:
        'Gom câu hỏi và thông tin cho buổi khám',
    ConsumerTerm.profileHubFamilyTitle: 'Người thân & chia sẻ',
    ConsumerTerm.profileHubFamilyDescription:
        'Chia sẻ tối thiểu với người hỗ trợ, có thể thu hồi',
    ConsumerTerm.profileHubEvidenceTitle: 'Bằng chứng đang cập nhật',
    ConsumerTerm.profileHubEvidenceDescription:
        'Theo dõi thay đổi đã được chuyên gia rà soát',
    ConsumerTerm.profileHubCommunityTitle: 'Cộng đồng',
    ConsumerTerm.profileHubCommunityDescription:
        'Chia sẻ và hỏi đáp cùng cộng đồng sức khỏe',
    ConsumerTerm.profileHubHealthDataTitle: 'Dữ liệu sức khỏe',
    ConsumerTerm.profileHubHealthDataDescription:
        'Quản lý các nguồn bạn đã cho phép kết nối',
    ConsumerTerm.profileHubClinicalNotesTitle: 'Ghi chú lâm sàng',
    ConsumerTerm.profileHubClinicalNotesDescription:
        'Ghi âm và tạo ghi chú SOAP',
    ConsumerTerm.profileHubCaseConsultationTitle: 'Hội chẩn ca bệnh',
    ConsumerTerm.profileHubCaseConsultationDescription:
        'Tập hợp góc nhìn đa chuyên khoa cho ca khó',
    ConsumerTerm.profileHubConsentTitle: 'Quyền riêng tư & đồng ý',
    ConsumerTerm.profileHubConsentDescription: 'Quản lý đồng ý theo mục đích',
    ConsumerTerm.profileHubDataRightsTitle: 'Quyền dữ liệu cá nhân',
    ConsumerTerm.profileHubDataRightsDescription:
        'Xuất, chỉnh sửa, hạn chế hoặc xoá dữ liệu của bạn',
    ConsumerTerm.profileHubSettingsTitle: 'Cài đặt',
    ConsumerTerm.profileHubSettingsDescription:
        'Giao diện, ngôn ngữ, tài khoản và quyền riêng tư',
    ConsumerTerm.todayStartHereTitle: 'Bạn muốn làm gì hôm nay?',
    ConsumerTerm.todayStartHereDescription:
        'Chọn một việc. CLARA sẽ chỉ dùng thông tin bạn đã cho phép.',
    ConsumerTerm.todayAskHealthTitle: 'Hỏi về vấn đề sức khỏe',
    ConsumerTerm.todayAskHealthDescription:
        'Trao đổi với CLARA và nhận hướng dẫn rõ ràng về bước tiếp theo.',
    ConsumerTerm.todayCheckMedicineTitle: 'Kiểm tra thuốc',
    ConsumerTerm.todayCheckMedicineDescription:
        'Xem thuốc đang dùng và kiểm tra an toàn từ nguồn thuốc đã xác minh.',
    ConsumerTerm.todaySaveHealthInfoTitle: 'Lưu thông tin sức khỏe',
    ConsumerTerm.todaySaveHealthInfoDescription:
        'Cập nhật hồ sơ của bạn. Thông tin chỉ được lưu khi bạn tự xác nhận.',
    ConsumerTerm.todayPrepareVisitTitle: 'Chuẩn bị cho buổi khám',
    ConsumerTerm.todayPrepareVisitDescription:
        'Gom điều cần hỏi và thông tin bạn muốn mang theo khi đi khám.',
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
    ConsumerTerm.loginSafetyTagline:
        'Trợ lý y tế an toàn — hỗ trợ quyết định, không thay thế bác sĩ.',
    ConsumerTerm.loginEmail: 'Email',
    ConsumerTerm.loginPassword: 'Mật khẩu',
    ConsumerTerm.loginShowPassword: 'Hiện mật khẩu',
    ConsumerTerm.loginHidePassword: 'Ẩn mật khẩu',
    ConsumerTerm.loginSubmit: 'Đăng nhập',
    ConsumerTerm.loginCreateAccount: 'Tạo tài khoản',
    ConsumerTerm.loginForgotPassword: 'Quên mật khẩu?',
    ConsumerTerm.loginEmailRequired: 'Vui lòng nhập email.',
    ConsumerTerm.loginPasswordRequired: 'Vui lòng nhập mật khẩu.',
    ConsumerTerm.loginUnauthorized:
        'Đăng nhập thất bại. Vui lòng kiểm tra lại email và mật khẩu.',
    ConsumerTerm.loginFailed: 'Không thể đăng nhập lúc này. Vui lòng thử lại.',
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
    ConsumerTerm.lifeMapReplayLabel: 'Nhìn lại hành trình',
    ConsumerTerm.lifeMapReplayFallbackTitle: 'Lịch sử LifeMap',
    ConsumerTerm.lifeMapReplayDescription:
        'Mỗi mục hiển thị đúng phiên bản và quy tắc đã dùng. Chỉnh sửa cần mạng '
            'và không được xếp hàng ngoại tuyến.',
    ConsumerTerm.lifeMapReplayStale:
        'Một số kết quả cũ đang được tính lại vì thông tin nguồn đã thay đổi.',
    ConsumerTerm.lifeMapReplayEmptyTitle: 'Chưa có bản ghi',
    ConsumerTerm.lifeMapReplayEmptyDescription:
        'Hành trình này chưa có thông tin để xem lại.',
    ConsumerTerm.lifeMapReplayVersion: 'Phiên bản {revision}',
    ConsumerTerm.lifeMapReplayWhy: 'Vì sao có mục này: {reason}',
    ConsumerTerm.lifeMapReplayEdit: 'Sửa thông tin',
    ConsumerTerm.lifeMapReplayDispute: 'Cần xem lại',
    ConsumerTerm.lifeMapReplayLoadFailed:
        'Không thể tải lịch sử. Vui lòng thử lại khi có mạng.',
    ConsumerTerm.lifeMapCorrectionTitle: 'Sửa thông tin',
    ConsumerTerm.lifeMapCorrectionNotice:
        'Thao tác này cần kết nối mạng và tạo một phiên bản mới. Phiên bản cũ '
            'vẫn được giữ trong lịch sử.',
    ConsumerTerm.lifeMapCorrectionLabel: 'Thông tin đúng',
    ConsumerTerm.lifeMapCorrectionSave: 'Lưu phiên bản mới',
    ConsumerTerm.lifeMapCorrectionSaved: 'Đã lưu phiên bản mới.',
    ConsumerTerm.lifeMapMutationOffline:
        'Không thể lưu. Thay đổi sức khỏe không được xếp hàng ngoại tuyến.',
    ConsumerTerm.lifeMapDisputeTitle: 'Gửi để xem xét',
    ConsumerTerm.lifeMapDisputeNotice:
        'Tranh chấp không xóa thông tin. CLARA giữ nguồn và tạo một hàng đợi '
            'xem xét. Thao tác này cần mạng.',
    ConsumerTerm.lifeMapDisputeLabel: 'Vì sao thông tin này cần xem lại?',
    ConsumerTerm.lifeMapDisputeSubmit: 'Gửi',
    ConsumerTerm.lifeMapDisputeSubmitted:
        'Đã đưa thông tin vào hàng đợi xem xét.',
    ConsumerTerm.lifeMapDisputeQueueTitle: 'Thông tin đang được xem xét',
    ConsumerTerm.lifeMapDisputeQueueNotice:
        'CLARA không tự chọn bên nào đúng. Mỗi quyết định tạo một phiên bản mới '
            'và giữ lịch sử nguồn.',
    ConsumerTerm.lifeMapDisputeQueueVersion:
        '{eventType} · phiên bản {revision}',
    ConsumerTerm.lifeMapDisputeQueueOpen: 'Đang mở',
    ConsumerTerm.lifeMapDisputeQueueResolved: 'Đã xử lý',
    ConsumerTerm.lifeMapDisputeQueueClinicalReview:
        'Loại thông tin này cần người có quyền lâm sàng kiểm tra nguồn.',
    ConsumerTerm.lifeMapDisputeQueueResolve: 'Xác nhận sau khi kiểm tra nguồn',
    ConsumerTerm.lifeMapSummarySectionTitle: 'Nhìn lại LifeMap',
    ConsumerTerm.lifeMapSummaryDescription:
        'Gom các bản ghi hiện có mà không đổi trạng thái đúng, đang tranh chấp hay mâu thuẫn.',
    ConsumerTerm.lifeMapSummaryScope: 'Phạm vi',
    ConsumerTerm.lifeMapSummaryDay: 'Theo ngày',
    ConsumerTerm.lifeMapSummaryWeek: 'Theo tuần',
    ConsumerTerm.lifeMapSummarySelectedJourney: 'Hành trình đang chọn',
    ConsumerTerm.lifeMapSummaryCreate: 'Tạo tóm tắt',
    ConsumerTerm.lifeMapSummaryEmpty: 'Chưa đủ bản ghi để tạo tóm tắt.',
    ConsumerTerm.lifeMapSummaryCitation: 'nguồn {citations}',
    ConsumerTerm.lifeMapSummarySafetyNotice:
        'Tóm tắt theo quy tắc, có liên kết nguồn và không phải tư vấn y tế.',
    ConsumerTerm.lifeMapSummaryLoadFailed:
        'Không thể tạo bản tóm tắt. Vui lòng thử lại.',
    ConsumerTerm.lifeMapReviewSectionTitle: 'Thông tin cần bạn kiểm tra',
    ConsumerTerm.lifeMapReviewDescription:
        'Quy tắc chỉ phát hiện khả năng trùng hoặc mâu thuẫn; CLARA không tự chọn bản nào đúng.',
    ConsumerTerm.lifeMapReviewCheck: 'Kiểm tra',
    ConsumerTerm.lifeMapReviewPossibleContradiction: 'Có thể mâu thuẫn',
    ConsumerTerm.lifeMapReviewPossibleDuplicate: 'Có thể trùng',
    ConsumerTerm.lifeMapReviewNeedsMoreInformation: 'Cần bổ sung',
    ConsumerTerm.lifeMapReviewBasedOnSavedRecords:
        'Dựa trên các thông tin bạn đã lưu trong LifeMap.',
    ConsumerTerm.lifeMapReviewResolved: 'Tôi đã kiểm tra',
    ConsumerTerm.lifeMapReviewDismiss: 'Không cần xử lý',
    ConsumerTerm.lifeMapReviewRecorded: 'Đã ghi nhận lựa chọn của bạn.',
    ConsumerTerm.lifeMapReviewLoadFailed:
        'Không thể kiểm tra thông tin. Vui lòng thử lại.',
    ConsumerTerm.lifeMapCaptureSectionTitle: 'Ghi nhận nhanh',
    ConsumerTerm.lifeMapCaptureCreateDescription:
        'Tạo bản nháp để xem lại trước khi đưa vào LifeMap.',
    ConsumerTerm.lifeMapCaptureInputLabel: 'Điều bạn muốn ghi lại',
    ConsumerTerm.lifeMapCaptureInputHint: 'Ví dụ: Tối qua tôi ngủ khoảng 7 giờ',
    ConsumerTerm.lifeMapCaptureCreate: 'Tạo bản nháp',
    ConsumerTerm.lifeMapCaptureArtifactTitle: 'Ghi nhận từ ảnh',
    ConsumerTerm.lifeMapCaptureArtifactDescription:
        'Ảnh chỉ tạo dữ liệu nháp. Bạn phải đối chiếu nguồn, sửa trường thiếu và xác nhận rõ ràng trước khi lưu.',
    ConsumerTerm.lifeMapCaptureSourceType: 'Loại nguồn',
    ConsumerTerm.lifeMapCaptureMedicationLabel: 'Nhãn thuốc',
    ConsumerTerm.lifeMapCaptureVisitDocument: 'Tài liệu khám',
    ConsumerTerm.lifeMapCaptureTakePhoto: 'Chụp ảnh',
    ConsumerTerm.lifeMapCaptureChoosePhoto: 'Chọn ảnh',
    ConsumerTerm.lifeMapCaptureCreateFailed:
        'Không thể tạo bản nháp. Vui lòng thử lại.',
    ConsumerTerm.lifeMapCaptureImageInvalid:
        'Ảnh phải nhỏ hơn 10 MB và không được để trống.',
    ConsumerTerm.lifeMapCaptureUploading: 'Đang tải nguồn an toàn…',
    ConsumerTerm.lifeMapCaptureReading:
        'Nguồn đang được đọc. Chưa có dữ liệu nào được xác nhận.',
    ConsumerTerm.lifeMapCaptureUploadFailed:
        'Không thể tải nguồn. Vui lòng thử lại.',
    ConsumerTerm.lifeMapCaptureReadingFailed:
        'Không thể đọc nguồn. Bản nháp chưa được xác nhận.',
    ConsumerTerm.lifeMapCaptureJobPending:
        'Tác vụ vẫn đang xử lý. Hãy kiểm tra lại sau.',
    ConsumerTerm.lifeMapCaptureRefreshFailed:
        'Không thể làm mới bản nháp. Vui lòng thử lại.',
    ConsumerTerm.lifeMapCaptureConfirmFailed:
        'Không thể xác nhận bản ghi. Vui lòng thử lại.',
    ConsumerTerm.lifeMapCaptureAbandonOffline:
        'Cần kết nối mạng để hủy bản nháp.',
    ConsumerTerm.lifeMapCaptureEmergencyFallback:
        'Nếu bạn đang gặp nguy hiểm ngay lập tức, hãy gọi cấp cứu địa phương hoặc đến cơ sở cấp cứu gần nhất.',
    ConsumerTerm.lifeMapCaptureDeleteSourceDraft: 'Xóa bản nháp nguồn',
    ConsumerTerm.lifeMapCaptureDraft: 'Bản nháp chưa xác nhận',
    ConsumerTerm.lifeMapCaptureRejected: 'Bản nháp đã bị từ chối',
    ConsumerTerm.lifeMapCaptureConfirmed: 'Bản ghi đã xác nhận',
    ConsumerTerm.lifeMapCaptureOnlineNotice:
        'Chỉ xử lý khi có mạng. CLARA không tự xác nhận và dữ liệu ngoại tuyến có thể đã cũ.',
    ConsumerTerm.lifeMapCaptureLowConfidence:
        'Một số phần chưa đọc rõ từ nguồn. Hãy đối chiếu trước khi lưu.',
    ConsumerTerm.lifeMapCaptureMissingFields: 'Cần bổ sung: {fields}',
    ConsumerTerm.lifeMapCaptureUnsafe:
        'Nguồn có nội dung không an toàn; không thể xác nhận.',
    ConsumerTerm.lifeMapCaptureNormalizeTitle: 'Chuẩn hóa tên thuốc',
    ConsumerTerm.lifeMapCaptureNormalizeLoading: 'Đang kiểm tra từ điển thuốc…',
    ConsumerTerm.lifeMapCaptureNormalizeUnavailable:
        'Chưa tìm thấy mã chuẩn phù hợp. Tên gốc vẫn được giữ nguyên và chưa được chuẩn hóa.',
    ConsumerTerm.lifeMapCaptureNormalizeProposal:
        'Đề xuất: {name} · RxNorm {code}',
    ConsumerTerm.lifeMapCaptureNormalizeUseCode:
        'Dùng mã chuẩn này cho hồ sơ thuốc',
    ConsumerTerm.lifeMapCaptureNormalizeUseCodeNotice:
        'Bản ghi chỉ được tạo sau khi bạn xác nhận.',
    ConsumerTerm.lifeMapCaptureEdit: 'Chỉnh sửa',
    ConsumerTerm.lifeMapCaptureReject: 'Từ chối',
    ConsumerTerm.lifeMapCaptureConfirm: 'Xác nhận',
    ConsumerTerm.lifeMapCaptureAbandon: 'Hủy và xóa bản nháp',
    ConsumerTerm.lifeMapCaptureProcessing: 'Bản nháp nguồn đang xử lý',
    ConsumerTerm.lifeMapCaptureCheckResult: 'Kiểm tra kết quả',
    ConsumerTerm.lifeMapCaptureEditTitle: 'Chỉnh sửa bản nháp',
    ConsumerTerm.lifeMapCaptureEditSave: 'Lưu chỉnh sửa',
    ConsumerTerm.lifeMapCaptureSourceImageLabel: 'Ảnh nguồn {name}',
    ConsumerTerm.lifeMapCaptureSourcePreviewError:
        'Không thể hiển thị ảnh nguồn.',
    ConsumerTerm.lifeMapCaptureSourcePreview:
        'Nguồn: {name} · chỉ giữ tạm trong bộ nhớ khi xem xét.',
    ConsumerTerm.lifeMapCaptureSourceUncached:
        'Ảnh nguồn không được lưu vào bộ nhớ đệm trên thiết bị. Hãy đối chiếu lại bản gốc trước khi xác nhận.',
    ConsumerTerm.lifeMapAskSectionTitle: 'Hỏi LifeMap của tôi',
    ConsumerTerm.lifeMapAskSafetyNotice:
        'Chỉ tra cứu dữ liệu bạn được phép xem. CLARA không chẩn đoán, kê đơn hay tự thay đổi LifeMap.',
    ConsumerTerm.lifeMapAskInputLabel: 'Bạn muốn tìm điều gì?',
    ConsumerTerm.lifeMapAskInputHint: 'Ví dụ: Các ghi nhận đau đầu gần đây?',
    ConsumerTerm.lifeMapAskInputHelp:
        'Câu trả lời chỉ ra đúng bản ghi và phiên bản đã dùng.',
    ConsumerTerm.lifeMapAskSubmit: 'Tra cứu',
    ConsumerTerm.lifeMapAskCitation: 'Nguồn: {source} · phiên bản {revision}',
    ConsumerTerm.lifeMapAskAnswerSafetyNotice:
        'AI có dẫn nguồn · Chỉ đọc · Không phải tư vấn y tế.',
    ConsumerTerm.lifeMapAskLoadFailed:
        'Không thể tra cứu LifeMap. Vui lòng thử lại.',
    ConsumerTerm.lifeMapQuestionNoneNeeded:
        'Hiện chưa có câu hỏi cần thiết. CLARA ưu tiên hỏi ít nhất có thể.',
    ConsumerTerm.lifeMapQuestionWhy: 'Vì sao CLARA hỏi: {reason}',
    ConsumerTerm.lifeMapQuestionAnswerLabel: 'Câu trả lời của bạn',
    ConsumerTerm.lifeMapQuestionAnswerHelp:
        'Sẽ tạo bản nháp để bạn kiểm tra trước.',
    ConsumerTerm.lifeMapQuestionLater: 'Để sau',
    ConsumerTerm.lifeMapQuestionCreateDraft: 'Tạo bản nháp',
    ConsumerTerm.lifeMapQuestionDraftCreated:
        'Đã tạo bản nháp. Hãy kiểm tra rồi xác nhận.',
    ConsumerTerm.lifeMapQuestionLoadFailed:
        'Không thể tải câu hỏi. Vui lòng thử lại khi có mạng.',
    ConsumerTerm.lifeMapBaselineSectionTitle: 'Thay đổi so với chính bạn',
    ConsumerTerm.lifeMapBaselineNotice:
        'Không phải mức bình thường lâm sàng hay chẩn đoán.',
    ConsumerTerm.lifeMapBaselineSamples: '{days} ngày dữ liệu · {version}',
    ConsumerTerm.lifeMapBaselineInsufficientData: 'Chưa đủ dữ liệu',
    ConsumerTerm.medicinesMyMedicines: 'Thuốc của tôi',
    ConsumerTerm.medicinesCabinet: 'Tủ thuốc',
    ConsumerTerm.medicinesSafety: 'An toàn',
    ConsumerTerm.medicinesLoginRequired:
        'Bạn cần đăng nhập để xem danh sách thuốc.',
    ConsumerTerm.medicinesLoadFailed:
        'Không thể tải danh sách thuốc. Vui lòng thử lại.',
    ConsumerTerm.medicinesProfileRequiredTitle: 'Chưa có hồ sơ sức khỏe',
    ConsumerTerm.medicinesProfileRequiredDescription:
        'Bạn cần tạo hồ sơ sức khỏe trước khi thêm thuốc. Sau khi có hồ sơ, '
            'danh sách thuốc của bạn sẽ hiển thị ở đây.',
    ConsumerTerm.medicinesReload: 'Tải lại',
    ConsumerTerm.medicinesEmptyTitle: 'Chưa có thuốc nào',
    ConsumerTerm.medicinesEmptyDescription:
        'Thêm thuốc bạn đang dùng để CLARA giúp theo dõi. Thông tin chỉ được '
            'lưu khi bạn tự xác nhận.',
    ConsumerTerm.medicinesAdd: 'Thêm thuốc',
    ConsumerTerm.medicinesUnnamed: 'Thuốc chưa đặt tên',
    ConsumerTerm.medicinesEnded: 'Đã kết thúc',
    ConsumerTerm.medicinesActive: 'Đang dùng',
    ConsumerTerm.medicinesSourceMatched: 'Đã khớp nguồn',
    ConsumerTerm.medicinesUnverified: 'Chưa xác minh',
    ConsumerTerm.medicinesActionsTooltip: 'Thao tác với thuốc',
    ConsumerTerm.medicinesEditNewVersion: 'Sửa bằng phiên bản mới',
    ConsumerTerm.medicinesEndCourse: 'Ghi nhận đã kết thúc',
    ConsumerTerm.medicinesEndConfirmTitle: 'Ghi nhận đã kết thúc?',
    ConsumerTerm.medicinesEndConfirmDescription:
        'Thao tác này chỉ cập nhật hồ sơ của bạn, không phải khuyến nghị dừng '
            'thuốc. Không tự ý ngừng thuốc nếu chưa trao đổi với chuyên gia y tế.',
    ConsumerTerm.medicinesEndAuditReason:
        'Người dùng xác nhận kết thúc trên ứng dụng di động',
    ConsumerTerm.medicinesCancel: 'Hủy',
    ConsumerTerm.medicinesConfirm: 'Ghi nhận',
    ConsumerTerm.medicinesNameRequired: 'Vui lòng nhập tên thuốc.',
    ConsumerTerm.medicinesLoginToAdd: 'Bạn cần đăng nhập để thêm thuốc.',
    ConsumerTerm.medicinesEditReasonRequired: 'Vui lòng nhập lý do chỉnh sửa.',
    ConsumerTerm.medicinesSaveFailed: 'Không thể lưu thuốc. Vui lòng thử lại.',
    ConsumerTerm.medicinesAddTitle: 'Thêm thuốc',
    ConsumerTerm.medicinesEditTitle: 'Sửa thông tin thuốc',
    ConsumerTerm.medicinesNameLabel: 'Tên thuốc *',
    ConsumerTerm.medicinesNameHint: 'Ví dụ: Paracetamol',
    ConsumerTerm.medicinesDoseLabel: 'Liều dùng',
    ConsumerTerm.medicinesDoseHint: 'Ví dụ: 500mg',
    ConsumerTerm.medicinesScheduleLabel: 'Lịch dùng',
    ConsumerTerm.medicinesScheduleHint: 'Ví dụ: 2 lần/ngày sau ăn',
    ConsumerTerm.medicinesRouteLabel: 'Đường dùng',
    ConsumerTerm.medicinesRouteHint: 'Ví dụ: Uống',
    ConsumerTerm.medicinesFormLabel: 'Dạng thuốc',
    ConsumerTerm.medicinesFormHint: 'Ví dụ: Viên nén',
    ConsumerTerm.medicinesEditReasonLabel: 'Lý do chỉnh sửa *',
    ConsumerTerm.medicinesEditReasonHint: 'Ví dụ: Sửa thông tin đã nhập nhầm',
    ConsumerTerm.medicinesSave: 'Lưu thuốc',
    ConsumerTerm.medicinesSaveNewVersion: 'Lưu phiên bản mới',
    ConsumerTerm.medicinesSafetyTitle: 'Kiểm tra tương tác thuốc',
    ConsumerTerm.medicinesSafetyDescription:
        'Việc kiểm tra tương tác thuốc được thực hiện trong Tủ thuốc. Khi bạn '
            'thêm từ hai loại thuốc trở lên, CLARA sẽ rà soát các tương tác có '
            'thể xảy ra dựa trên danh sách đó.',
    ConsumerTerm.medicinesOpenCabinet: 'Mở Tủ thuốc',
    ConsumerTerm.medicinesSafetyNotice:
        'CLARA là trợ lý hỗ trợ quyết định, không thay thế bác sĩ. Kết quả kiểm '
            'tra chỉ mang tính tham khảo — hãy trao đổi với dược sĩ hoặc bác sĩ '
            'trước khi thay đổi cách dùng thuốc.',
    ConsumerTerm.visitsTitle: 'Chuẩn bị đi khám',
    ConsumerTerm.visitsCreate: 'Tạo buổi khám',
    ConsumerTerm.visitsClose: 'Đóng',
    ConsumerTerm.visitsProfileRequiredTitle: 'Hãy tạo hồ sơ sức khỏe trước',
    ConsumerTerm.visitsProfileRequiredDescription:
        'Để chuẩn bị cho buổi khám, bạn cần tạo hồ sơ sức khỏe trước. Đây là '
            'bước giúp bạn trao đổi với bác sĩ hiệu quả hơn, không phải chẩn đoán.',
    ConsumerTerm.visitsEmptyTitle: 'Chưa có buổi khám nào',
    ConsumerTerm.visitsEmptyDescription:
        'Tạo một buổi khám để chuẩn bị nội dung cần trao đổi với bác sĩ. CLARA '
            'giúp bạn sắp xếp mối quan tâm, không phải chẩn đoán.',
    ConsumerTerm.visitsSafetyLabel: 'Lưu ý về buổi khám',
    ConsumerTerm.visitsSafetyNotice:
        'Buổi khám giúp bạn chuẩn bị trước khi gặp bác sĩ. Đây không phải là tư '
            'vấn hay chẩn đoán y tế.',
    ConsumerTerm.visitsNameLabel: 'Tên buổi khám',
    ConsumerTerm.visitsNameHint: 'Ví dụ: Khám tim mạch định kỳ',
    ConsumerTerm.visitsReasonLabel: 'Lý do khám (không bắt buộc)',
    ConsumerTerm.visitsReasonHint: 'Điều bạn muốn trao đổi với bác sĩ',
    ConsumerTerm.visitsUnnamed: 'Buổi khám chưa đặt tên',
    ConsumerTerm.visitsPreparationTitle: 'Chuẩn bị buổi khám',
    ConsumerTerm.visitsOpenPreparation: 'Mở chuẩn bị',
    ConsumerTerm.visitsNoSchedule: 'Chưa đặt lịch',
    ConsumerTerm.visitsScheduledDate: 'Lịch: {date}',
    ConsumerTerm.visitsNameRequired: 'Vui lòng nhập tên buổi khám.',
    ConsumerTerm.visitsLoadFailed:
        'Không thể tải danh sách buổi khám. Vui lòng thử lại.',
    ConsumerTerm.visitsCreateFailed:
        'Không thể tạo buổi khám. Vui lòng thử lại.',
    ConsumerTerm.visitDraftTitle: 'Bản nháp chuẩn bị buổi khám',
    ConsumerTerm.visitDraftDescription:
        'Tạo bản nháp riêng tư từ các ghi nhận LifeMap để bạn xem, sửa và mang theo khi đi khám.',
    ConsumerTerm.visitDraftGoalLabel:
        'Bạn muốn chuẩn bị điều gì cho buổi khám?',
    ConsumerTerm.visitDraftGoalHint:
        'Ví dụ: Tôi muốn trao đổi các ghi nhận đau đầu gần đây.',
    ConsumerTerm.visitDraftCreate: 'Tạo bản nháp',
    ConsumerTerm.visitDraftCreating: 'Đang tạo bản nháp…',
    ConsumerTerm.visitDraftReviewNotice:
        'Đây là bản nháp để bạn tự xem và chỉnh sửa. Nó không thay đổi hồ sơ sức khỏe.',
    ConsumerTerm.visitDraftImportantNow: 'Điều quan trọng nhất',
    ConsumerTerm.visitDraftSources: 'CLARA dựa vào thông tin nào',
    ConsumerTerm.visitDraftNoSources:
        'Chưa có ghi nhận phù hợp trong phạm vi đã chọn.',
    ConsumerTerm.visitDraftUncertainty: 'Phần chưa chắc chắn',
    ConsumerTerm.visitDraftNoUncertainty:
        'Không có điểm chưa chắc chắn được nêu trong bản nháp này.',
    ConsumerTerm.visitDraftNextStep: 'Bạn có thể làm gì tiếp theo',
    ConsumerTerm.visitDraftUrgentHelp: 'Khi nào cần hỗ trợ khẩn cấp',
    ConsumerTerm.visitDraftQuestions: 'Câu hỏi để cân nhắc khi đi khám',
    ConsumerTerm.visitDraftNoQuestions:
        'Chưa có câu hỏi từ các ghi nhận hiện có.',
    ConsumerTerm.visitDraftCopy: 'Sao chép bản nháp',
    ConsumerTerm.visitDraftCopied: 'Đã sao chép bản nháp.',
    ConsumerTerm.visitDraftCreateFailed:
        'Không thể tạo bản nháp. Vui lòng kiểm tra kết nối và thử lại.',
    ConsumerTerm.visitDetailPreparationNotice:
        'CLARA giúp chuẩn bị cho cuộc trao đổi với bác sĩ, không chẩn đoán hay '
            'kê đơn. Chỉ nội dung bạn tự chọn và duyệt mới được sử dụng.',
    ConsumerTerm.visitDetailConcernsTitle: '1. Điều cần hỏi',
    ConsumerTerm.visitDetailConcernLabel: 'Điều bạn muốn trao đổi với bác sĩ',
    ConsumerTerm.visitDetailSaveConcern: 'Lưu điều cần hỏi',
    ConsumerTerm.visitDetailDocumentsTitle: '2. Tài liệu bạn chọn',
    ConsumerTerm.visitDetailDocumentsDescription:
        'Dán nội dung đã chọn. CLARA không tự mở liên kết hay tự nhập hồ sơ.',
    ConsumerTerm.visitDetailDocumentTitle: 'Tên tài liệu',
    ConsumerTerm.visitDetailDocumentContent: 'Nội dung văn bản đã chọn',
    ConsumerTerm.visitDetailSaveDocument: 'Lưu tài liệu',
    ConsumerTerm.visitDetailInactiveDocument: 'Đã rút hoặc xoá khỏi xử lý',
    ConsumerTerm.visitDetailControlledDocument: 'Đang do bạn kiểm soát',
    ConsumerTerm.visitDetailCheckPlan: 'Kiểm tra kế hoạch',
    ConsumerTerm.visitDetailWithdrawDocument: 'Rút khỏi xử lý',
    ConsumerTerm.visitDetailDeleteDocument: 'Xoá nội dung',
    ConsumerTerm.visitDetailReviewTitle: '3. Rà soát có căn cứ',
    ConsumerTerm.visitDetailNoEvidence:
        'Không có mục đủ căn cứ để đề xuất. Hãy kiểm tra lại với bác sĩ.',
    ConsumerTerm.visitDetailReviewGuidance:
        'Chỉ xác nhận chỉ dẫn của bác sĩ có đoạn nguồn nguyên văn.',
    ConsumerTerm.visitDetailSource: 'Nguồn: “{source}”',
    ConsumerTerm.visitDetailUnconfirmableCandidate:
        'Diễn giải AI hoặc thiếu nguồn — không thể xác nhận.',
    ConsumerTerm.visitDetailConfirmSelected: 'Xác nhận mục đã chọn',
    ConsumerTerm.visitDetailWithdrawDraft: 'Rút bản nháp',
    ConsumerTerm.visitDetailPackTitle: '4. Chọn và duyệt Visit Pack',
    ConsumerTerm.visitDetailPackNotice:
        'Không có mục nào được tự động thêm hoặc chia sẻ.',
    ConsumerTerm.visitDetailNoMatchingItems: 'Chưa có mục phù hợp.',
    ConsumerTerm.visitDetailPackConcerns: 'Điều cần hỏi',
    ConsumerTerm.visitDetailPackMedications: 'Thuốc đã xác nhận',
    ConsumerTerm.visitDetailPackEpisodes: 'Hành trình liên quan',
    ConsumerTerm.visitDetailPackEvents: 'Diễn biến đã xác nhận',
    ConsumerTerm.visitDetailPackInstructions: 'Chỉ dẫn bác sĩ bạn đã xác nhận',
    ConsumerTerm.visitDetailCreatePack: 'Tạo và duyệt gói',
    ConsumerTerm.visitDetailCreateNewPackVersion: 'Tạo phiên bản mới',
    ConsumerTerm.visitDetailApprovedPackVersion:
        'Phiên bản {version} đã được bạn duyệt.',
    ConsumerTerm.visitDetailCreateShare: 'Tạo liên kết 7 ngày',
    ConsumerTerm.visitDetailRevokeShare: 'Thu hồi liên kết',
    ConsumerTerm.visitDetailScribeConsentTitle:
        'Đồng ý ghi âm riêng cho buổi này',
    ConsumerTerm.visitDetailScribeConsentDescription:
        'Bạn có thể rút lại ngay. Chưa có đồng ý thì Scribe không được xử lý.',
    ConsumerTerm.visitDetailScribeConsentGranted: 'Đã đồng ý cho buổi này',
    ConsumerTerm.visitDetailScribeConsentNotGranted: 'Chưa đồng ý ghi âm',
    ConsumerTerm.visitDetailLoadFailed:
        'Không thể tải dữ liệu buổi khám. Vui lòng thử lại.',
    ConsumerTerm.visitDetailActionFailed:
        'Không thể hoàn tất thao tác. Vui lòng thử lại.',
    ConsumerTerm.visitDetailConcernRequired:
        'Hãy nhập điều bạn muốn hỏi bác sĩ.',
    ConsumerTerm.visitDetailDocumentRequired:
        'Hãy đặt tên và dán nội dung tài liệu bạn đã chọn.',
    ConsumerTerm.familyTitle: 'Người thân & chia sẻ',
    ConsumerTerm.familySupporter: 'Người hỗ trợ',
    ConsumerTerm.familyNewNotification: 'Thông báo mới',
    ConsumerTerm.familyAccessGrant: 'Quyền truy cập',
    ConsumerTerm.familyInvite: 'Mời người thân',
    ConsumerTerm.familyClose: 'Đóng',
    ConsumerTerm.familySharingNoteSemanticLabel:
        'Lưu ý về chia sẻ với người hỗ trợ',
    ConsumerTerm.familySharingNote:
        'Chia sẻ tối thiểu với người hỗ trợ. Bạn chỉ chia sẻ khi đồng ý và có '
            'thể thu hồi bất cứ lúc nào.',
    ConsumerTerm.familySharedWith: 'Người bạn đang chia sẻ',
    ConsumerTerm.familyEmptyTitle: 'Chưa chia sẻ với ai',
    ConsumerTerm.familyEmptyDescription:
        'Mời một người thân để họ có thể hỗ trợ bạn. Bạn kiểm soát những gì '
            'được chia sẻ và có thể thu hồi bất cứ lúc nào.',
    ConsumerTerm.familyNotifications: 'Thông báo cần xem',
    ConsumerTerm.familyActiveGrants: 'Quyền truy cập đang mở',
    ConsumerTerm.familyAccessLog: 'Nhật ký truy cập gần đây',
    ConsumerTerm.familyAccessLogActorOwner: 'Bạn',
    ConsumerTerm.familyAccessLogActorSupporter: 'Người hỗ trợ',
    ConsumerTerm.familyAccessLogActorSystem: 'Hệ thống',
    ConsumerTerm.familyAccessLogActorOther: 'Người dùng',
    ConsumerTerm.familyAccessLogActionView: 'xem dữ liệu được chia sẻ',
    ConsumerTerm.familyAccessLogActionAddObservation: 'thêm ghi nhận',
    ConsumerTerm.familyAccessLogActionCompleteTask: 'hoàn thành việc chăm sóc',
    ConsumerTerm.familyAccessLogActionInvitationAccept: 'chấp nhận lời mời',
    ConsumerTerm.familyAccessLogActionGrantRevoke: 'thu hồi quyền',
    ConsumerTerm.familyAccessLogActionGrantRenewalInvited:
        'tạo lời mời gia hạn',
    ConsumerTerm.familyAccessLogActionNotificationAcknowledged:
        'xác nhận thông báo',
    ConsumerTerm.familyAccessLogActionOther: 'thao tác được ghi nhận',
    ConsumerTerm.familyAccessLogOutcomeAllowed: 'được cho phép',
    ConsumerTerm.familyAccessLogOutcomeDenied: 'bị từ chối',
    ConsumerTerm.familyAccessLogOutcomeFailed: 'không thực hiện được',
    ConsumerTerm.familyAccessLogOutcomeUnknown: 'không xác định',
    ConsumerTerm.familyEmailLabel: 'Email người thân',
    ConsumerTerm.familyEmailHint: 'vidu@email.com',
    ConsumerTerm.familyScopeLabel: 'Chỉ chia sẻ',
    ConsumerTerm.familyScopeJourney: 'Một hành trình',
    ConsumerTerm.familyScopeVisit: 'Một buổi khám',
    ConsumerTerm.familySharedItemLabel: 'Mục được chia sẻ',
    ConsumerTerm.familyPurposeLabel: 'Mục đích',
    ConsumerTerm.familyPurposeCareCoordination: 'Phối hợp chăm sóc',
    ConsumerTerm.familyPurposeVisitSupport: 'Hỗ trợ đi khám',
    ConsumerTerm.familySendInvitation: 'Gửi lời mời',
    ConsumerTerm.familyInvitationTokenNotice:
        'Mã chỉ hiển thị lần này. Gửi mã qua kênh bạn tin cậy:',
    ConsumerTerm.familyAcknowledge: 'Đã xem',
    ConsumerTerm.familyExpiresAt: 'Hết hạn: {date}',
    ConsumerTerm.familyRenew: 'Gia hạn',
    ConsumerTerm.familyRevoke: 'Thu hồi',
    ConsumerTerm.familyRevokeConfirmTitle: 'Thu hồi quyền truy cập?',
    ConsumerTerm.familyRevokeConfirmDescription:
        'Sau khi thu hồi, "{name}" sẽ không còn xem được thông tin bạn đã '
            'chia sẻ. Bạn có thể mời lại sau này.',
    ConsumerTerm.familyCancel: 'Hủy',
    ConsumerTerm.familyEmailRequired: 'Vui lòng nhập email người thân.',
    ConsumerTerm.familySharedItemRequired:
        'Hãy chọn đúng hành trình hoặc buổi khám để chia sẻ.',
    ConsumerTerm.familyInvitationCreated:
        'Đã tạo mã mời. CLARA chưa tự gửi email.',
    ConsumerTerm.familyInvitationFailed:
        'Không thể gửi lời mời. Vui lòng thử lại.',
    ConsumerTerm.familyNotificationUnavailable:
        'Thông báo này không thể xác nhận.',
    ConsumerTerm.familyAcknowledgeFailed:
        'Không thể xác nhận. Vui lòng thử lại.',
    ConsumerTerm.familyGrantUnavailable:
        'Quyền truy cập này không thể thu hồi.',
    ConsumerTerm.familyRevoked: 'Đã thu hồi quyền truy cập.',
    ConsumerTerm.familyRevokeFailed: 'Không thể thu hồi. Vui lòng thử lại.',
    ConsumerTerm.familyRenewed:
        'Đã tạo mã gia hạn; người nhận cần chấp nhận lại.',
    ConsumerTerm.familyRenewFailed: 'Không thể tạo lời mời gia hạn.',
    ConsumerTerm.familyLoadFailed:
        'Không thể tải thông tin chia sẻ. Vui lòng thử lại.',
    ConsumerTerm.familyUseInvitationCode: 'Dùng mã lời mời',
    ConsumerTerm.familyInvitationAcceptTitle: 'Xem lời mời chia sẻ',
    ConsumerTerm.familyInvitationAcceptDescription:
        'Nhập mã được gửi riêng cho bạn. CLARA sẽ cho bạn xem phạm vi trước khi '
            'bạn đồng ý.',
    ConsumerTerm.familyInvitationCodeLabel: 'Mã lời mời',
    ConsumerTerm.familyInvitationCodeHint: 'Dán mã lời mời vào đây',
    ConsumerTerm.familyInvitationCodeRequired: 'Hãy nhập mã lời mời.',
    ConsumerTerm.familyPreviewInvitation: 'Xem trước lời mời',
    ConsumerTerm.familyPreviewingInvitation: 'Đang xem trước lời mời…',
    ConsumerTerm.familyInvitationPreviewTitle: 'Bạn sẽ chia sẻ như sau',
    ConsumerTerm.familyInvitationPreviewNotice:
        'Bước này chưa cấp quyền truy cập và không mở dữ liệu sức khỏe. Chỉ khi '
            'bạn chọn chấp nhận thì quyền mới được tạo.',
    ConsumerTerm.familyInvitationScopeLabel: 'Phạm vi chia sẻ',
    ConsumerTerm.familyInvitationActionsLabel: 'Người này có thể',
    ConsumerTerm.familyInvitationExpiryUnavailable: 'Hạn dùng chưa rõ',
    ConsumerTerm.familyInvitationScopeCareTask: 'Một việc chăm sóc',
    ConsumerTerm.familyInvitationActionView: 'Xem thông tin đã được chia sẻ',
    ConsumerTerm.familyInvitationActionAddObservation: 'Thêm ghi nhận',
    ConsumerTerm.familyInvitationActionCompleteTask: 'Hoàn thành việc chăm sóc',
    ConsumerTerm.familyInvitationActionOther: 'Thực hiện một thao tác giới hạn',
    ConsumerTerm.familyInvitationPreviewFailed:
        'Không thể xem lời mời. Kiểm tra mã và thử lại.',
    ConsumerTerm.familyInvitationAccept: 'Chấp nhận chia sẻ này',
    ConsumerTerm.familyAcceptingInvitation: 'Đang chấp nhận…',
    ConsumerTerm.familyInvitationAccepted:
        'Bạn đã chấp nhận quyền chia sẻ này.',
    ConsumerTerm.familyInvitationAcceptFailed:
        'Không thể chấp nhận lời mời. Hãy xem lại mã và thử lại.',
    ConsumerTerm.connectedHealthTitle: 'Dữ liệu sức khỏe',
    ConsumerTerm.connectedHealthIntroTitle: 'Kết nối khi bạn muốn',
    ConsumerTerm.connectedHealthIntroDescription:
        'CLARA chỉ đọc các nhóm dữ liệu bạn cho phép. Bạn có thể tạm dừng, '
            'ngắt kết nối hoặc xóa dữ liệu bất cứ lúc nào.',
    ConsumerTerm.connectedHealthSourcesTitle: 'Nguồn đã kết nối',
    ConsumerTerm.connectedHealthBeforeConnectingTitle: 'Trước khi kết nối',
    ConsumerTerm.connectedHealthChooseDataTitle: 'Bạn chọn dữ liệu được dùng',
    ConsumerTerm.connectedHealthChooseDataDescription:
        'Ví dụ: bước chân, giấc ngủ hoặc nhịp tim. CLARA không suy đoán khi '
            'dữ liệu thiếu.',
    ConsumerTerm.connectedHealthPrivateDataTitle:
        'Dữ liệu cá nhân không tự động gửi vào chat',
    ConsumerTerm.connectedHealthPrivateDataDescription:
        'Bạn cần cho phép mục đích hỗ trợ sức khỏe trước khi dữ liệu được đưa '
            'vào gợi ý cá nhân.',
    ConsumerTerm.connectedHealthEmptyTitle: 'Chưa có nguồn nào được kết nối',
    ConsumerTerm.connectedHealthEmptyDescription:
        'Khi tính năng kết nối trên thiết bị sẵn sàng, CLARA sẽ luôn hỏi quyền '
            'trước khi đọc dữ liệu.',
    ConsumerTerm.connectedHealthFallbackSourceTitle: 'Nguồn sức khỏe',
    ConsumerTerm.connectedHealthAllowedData: 'Được phép: {types}',
    ConsumerTerm.connectedHealthPause: 'Tạm dừng',
    ConsumerTerm.connectedHealthResume: 'Tiếp tục',
    ConsumerTerm.connectedHealthDisconnect: 'Ngắt kết nối',
    ConsumerTerm.connectedHealthDeleteImportedData: 'Xóa dữ liệu',
    ConsumerTerm.connectedHealthStatusHealthy: 'Đã cập nhật',
    ConsumerTerm.connectedHealthStatusConnected: 'Sẵn sàng',
    ConsumerTerm.connectedHealthStatusPaused: 'Đang tạm dừng',
    ConsumerTerm.connectedHealthStatusNeedsReauth: 'Cần cấp quyền lại',
    ConsumerTerm.connectedHealthStatusDisconnected: 'Đã ngắt kết nối',
    ConsumerTerm.connectedHealthStatusUnknown: 'Chưa rõ',
    ConsumerTerm.connectedHealthLoadFailedTitle: 'Chưa thể tải nguồn sức khỏe',
    ConsumerTerm.connectedHealthDisconnectConfirmTitle:
        'Ngắt kết nối nguồn này?',
    ConsumerTerm.connectedHealthDisconnectConfirmDescription:
        'Dữ liệu đã nhập vẫn được giữ lại. Bạn có thể xóa riêng dữ liệu đó bên dưới.',
    ConsumerTerm.connectedHealthDisconnectConfirmAction: 'Ngắt kết nối',
    ConsumerTerm.connectedHealthDeleteConfirmTitle: 'Xóa dữ liệu đã nhập?',
    ConsumerTerm.connectedHealthDeleteConfirmDescription:
        'Việc này xóa các quan sát và tổng hợp từ nguồn này. Không thể hoàn tác.',
    ConsumerTerm.connectedHealthDeleteConfirmAction: 'Xóa dữ liệu',
    ConsumerTerm.connectedHealthDeleteSuccess:
        'Đã xóa dữ liệu đã nhập từ nguồn này.',
    ConsumerTerm.connectedHealthCancel: 'Hủy',
    // Living Evidence keeps findings read-only until the service's reviewed
    // change workflow has released them. These terms never translate source
    // text, clinical claims, or raw API errors.
    ConsumerTerm.livingEvidenceTitle: 'Bằng chứng đang cập nhật',
    ConsumerTerm.livingEvidenceSafetyNotice:
        'CLARA chỉ thông báo thay đổi quan trọng sau khi chuyên gia rà soát. '
            'Kết quả tìm kiếm mới không tự trở thành khuyến nghị.',
    ConsumerTerm.livingEvidenceReviewedChanges: 'Thay đổi đã được rà soát',
    ConsumerTerm.livingEvidenceNotificationSemanticLabel:
        'Mở thông báo thay đổi bằng chứng',
    ConsumerTerm.livingEvidenceRead: 'Đã đọc',
    ConsumerTerm.livingEvidenceMarkRead: 'Chạm để đánh dấu đã đọc',
    ConsumerTerm.livingEvidenceSubscriptions: 'Theo dõi của bạn',
    ConsumerTerm.livingEvidenceEmptyTitle: 'Chưa theo dõi câu hỏi nào',
    ConsumerTerm.livingEvidenceEmptyDescription:
        'Tạo câu hỏi bên dưới để bắt đầu.',
    ConsumerTerm.livingEvidenceNewQuestion: 'Tạo câu hỏi mới',
    ConsumerTerm.livingEvidenceJourneyLabel: 'Hành trình LifeMap',
    ConsumerTerm.livingEvidenceQuestionLabel: 'Điều bạn muốn biết',
    ConsumerTerm.livingEvidenceContextLabel:
        'Bối cảnh đã xác nhận (không bắt buộc)',
    ConsumerTerm.livingEvidenceCreateAndFollow: 'Xác nhận, tìm và theo dõi',
    ConsumerTerm.livingEvidenceLoadFailed: 'Chưa thể tải theo dõi bằng chứng.',
    ConsumerTerm.livingEvidenceRunIncomplete:
        'Lần tìm bằng chứng chưa hoàn tất; không có kết luận nào được phát hành.',
    ConsumerTerm.livingEvidenceCreateFailed:
        'Chưa thể tạo theo dõi bằng chứng.',
    ConsumerTerm.livingEvidenceIntervalFailed: 'Không thể cập nhật tần suất.',
    ConsumerTerm.livingEvidenceStopFailed: 'Không thể dừng theo dõi.',
    ConsumerTerm.livingEvidenceSubscriptionTitle: 'Theo dõi bằng chứng',
    ConsumerTerm.livingEvidenceApplicabilityPending:
        'Khả năng áp dụng chưa được đánh giá.',
    ConsumerTerm.livingEvidenceNoContradictions:
        'Mâu thuẫn: chưa được đánh giá hoặc chưa có báo cáo.',
    ConsumerTerm.livingEvidenceContradictionsCount:
        'Mâu thuẫn cần đối chiếu: {count}.',
    ConsumerTerm.livingEvidenceIntervalLabel: 'Tần suất kiểm tra',
    ConsumerTerm.livingEvidenceEveryDay: 'Mỗi ngày',
    ConsumerTerm.livingEvidenceEveryWeek: 'Mỗi tuần',
    ConsumerTerm.livingEvidenceEveryThirtyDays: 'Mỗi 30 ngày',
    ConsumerTerm.livingEvidenceStopFollowing: 'Dừng theo dõi',
    ConsumerTerm.socialSessionExpired:
        'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
    ConsumerTerm.socialLoadFailed:
        'Không thể tải cộng đồng lúc này. Vui lòng thử lại.',
    ConsumerTerm.socialNoCommunities: 'Chưa có cộng đồng để đăng bài.',
    ConsumerTerm.socialConsentTitle: 'Tham gia cộng đồng CLARA',
    ConsumerTerm.socialConsentDescription:
        'Cộng đồng là nơi chia sẻ kinh nghiệm và hỗ trợ nhau. Đây KHÔNG phải '
            'tư vấn y tế: không kê đơn, chẩn đoán hay chỉ định liều dùng. Nội '
            'dung được kiểm duyệt để giữ an toàn. Bạn đồng ý quy tắc ứng xử và '
            'quyền riêng tư của cộng đồng?',
    ConsumerTerm.socialConsentAgree: 'Tôi đồng ý tham gia',
    ConsumerTerm.socialLater: 'Để sau',
    ConsumerTerm.socialTitle: 'Cộng đồng',
    ConsumerTerm.socialProfileTooltip: 'Hồ sơ cộng đồng',
    ConsumerTerm.socialPost: 'Đăng bài',
    ConsumerTerm.socialConsentCardSemanticLabel: 'Tham gia cộng đồng',
    ConsumerTerm.socialConsentCardTitle: 'Tham gia để đăng bài & bình luận',
    ConsumerTerm.socialConsentCardDescription:
        'Bạn vẫn có thể đọc bài. Đồng ý quy tắc cộng đồng để tham gia chia sẻ.',
    ConsumerTerm.socialJoin: 'Tham gia',
    ConsumerTerm.socialCommunities: 'Cộng đồng',
    ConsumerTerm.socialFeed: 'Bảng tin',
    ConsumerTerm.socialEmptyFeed:
        'Chưa có bài viết nào. Hãy là người đầu tiên chia sẻ.',
    ConsumerTerm.socialReactionSent: 'Đã gửi phản hồi hữu ích.',
    ConsumerTerm.socialReactionHelpful: 'Hữu ích',
    ConsumerTerm.socialAnonymous: 'ẩn danh',
    ConsumerTerm.socialDisclaimer:
        'Cộng đồng là nơi hỗ trợ ngang hàng, không thay thế tư vấn của bác sĩ. '
            'Nội dung kê đơn/chẩn đoán/liều dùng cá nhân sẽ bị chặn.',
    ConsumerTerm.socialMembers: '{count} thành viên',
    ConsumerTerm.socialJoined: 'Đã tham gia',
    ConsumerTerm.socialUnavailableTitle: 'Cộng đồng sắp ra mắt',
    ConsumerTerm.socialUnavailableDescription:
        'Tính năng cộng đồng sức khỏe đang được chuẩn bị và sẽ sớm mở.',
    ConsumerTerm.socialComposeTitle: 'Chia sẻ với cộng đồng',
    ConsumerTerm.socialCommunityLabel: 'Cộng đồng',
    ConsumerTerm.socialPostTitleLabel: 'Tiêu đề',
    ConsumerTerm.socialPostBodyLabel: 'Nội dung',
    ConsumerTerm.socialComposeRequired:
        'Vui lòng nhập tiêu đề, nội dung và chọn cộng đồng.',
    ConsumerTerm.socialComments: 'Bình luận',
    ConsumerTerm.socialEmptyComments:
        'Chưa có bình luận. Hãy là người đầu tiên.',
    ConsumerTerm.socialCommentLabel: 'Viết bình luận…',
    ConsumerTerm.socialCommentJoinRequired: 'Tham gia cộng đồng để bình luận.',
    ConsumerTerm.socialModerationBlocked:
        'Bình luận không phù hợp quy tắc cộng đồng (không kê đơn/chẩn đoán/liều '
            'dùng) hoặc có dấu hiệu khẩn cấp.',
    ConsumerTerm.socialReportTitle: 'Báo cáo bài viết',
    ConsumerTerm.socialReportDescription:
        'Báo cáo nội dung vi phạm quy tắc cộng đồng (kê đơn/chẩn đoán/liều '
            'dùng cá nhân, spam, hoặc không phù hợp). Đội ngũ kiểm duyệt sẽ xem xét.',
    ConsumerTerm.socialCancel: 'Hủy',
    ConsumerTerm.socialReport: 'Báo cáo',
    ConsumerTerm.socialReportSent: 'Đã gửi báo cáo. Cảm ơn bạn.',
    ConsumerTerm.socialClose: 'Đóng',
    ConsumerTerm.socialProfileTitle: 'Hồ sơ cộng đồng',
    ConsumerTerm.socialDisplayNameLabel: 'Tên hiển thị',
    ConsumerTerm.socialBioLabel:
        'Giới thiệu (không chia sẻ thông tin y tế cá nhân)',
    ConsumerTerm.socialSaveProfile: 'Lưu hồ sơ',
    ConsumerTerm.socialProfileSaved: 'Đã lưu hồ sơ cộng đồng.',
    ConsumerTerm.socialDoctor: 'Bác sĩ',
    ConsumerTerm.socialResearcher: 'Nhà nghiên cứu',
    ConsumerTerm.moreTitle: 'Thêm',
    ConsumerTerm.moreOtherToolsTitle: 'Công cụ khác',
    ConsumerTerm.settingsTitle: 'Cài đặt',
    ConsumerTerm.settingsAppearanceTitle: 'Giao diện',
    ConsumerTerm.settingsThemeLight: 'Sáng',
    ConsumerTerm.settingsThemeDark: 'Tối',
    ConsumerTerm.settingsThemeSystem: 'Hệ thống',
    ConsumerTerm.settingsLanguageTitle: 'Ngôn ngữ',
    ConsumerTerm.settingsSelected: 'đã chọn',
    ConsumerTerm.settingsNotSelected: 'chưa chọn',
    ConsumerTerm.settingsAccountTitle: 'Tài khoản',
    ConsumerTerm.settingsEmailLabel: 'Email',
    ConsumerTerm.settingsRoleLabel: 'Vai trò',
    ConsumerTerm.settingsNoInformation: 'Chưa có thông tin',
    ConsumerTerm.settingsRoleConsumer: 'Người dùng',
    ConsumerTerm.settingsRoleResearcher: 'Nghiên cứu viên',
    ConsumerTerm.settingsRoleDoctor: 'Bác sĩ',
    ConsumerTerm.settingsRoleAdmin: 'Quản trị viên',
    ConsumerTerm.settingsSignOut: 'Đăng xuất',
    ConsumerTerm.settingsSignOutConfirmTitle: 'Đăng xuất',
    ConsumerTerm.settingsSignOutConfirmDescription:
        'Bạn có chắc muốn đăng xuất khỏi CLARA? Phiên đăng nhập trên thiết bị này sẽ bị xóa.',
    ConsumerTerm.settingsCancel: 'Hủy',
    ConsumerTerm.settingsPrivacyTitle: 'Quyền riêng tư & đồng ý',
    ConsumerTerm.settingsPrivacyDescription:
        'CLARA chỉ xử lý dữ liệu sức khỏe bạn tự khai báo và yêu cầu đồng ý theo phiên bản trước khi cung cấp nội dung y tế. Bạn có thể xem lại và quản lý đồng ý trong mục "Quyền riêng tư & đồng ý" ở phần Thêm.',
    ConsumerTerm.settingsTransparencyTitle: 'Minh bạch AI',
    ConsumerTerm.settingsAiModelLabel: 'Mô hình AI',
    ConsumerTerm.settingsAiModelGovernedRoute:
        'DeepSeek V4 Pro / Flash — được chọn theo từng tác vụ',
    ConsumerTerm.settingsAboutTitle: 'Giới thiệu',
    ConsumerTerm.settingsVersion: 'Phiên bản {version}',
    ConsumerTerm.settingsAboutDescription:
        'CLARA là trợ lý y tế AI hỗ trợ ra quyết định. CLARA không phải bác sĩ và không thay thế tư vấn, chẩn đoán hay điều trị y khoa chuyên môn. Trong trường hợp khẩn cấp, hãy gọi ngay dịch vụ cấp cứu tại địa phương.',
    ConsumerTerm.settingsHelpTitle: 'Trợ giúp',
    ConsumerTerm.settingsHelpDescription:
        'Cần hỗ trợ? Xem hướng dẫn sử dụng trong ứng dụng hoặc liên hệ đội ngũ CLARA để được trợ giúp.',
  };

  static const Map<ConsumerTerm, String> _enMessages = {
    ConsumerTerm.homeScreenToolsTitle: 'Tools',
    ConsumerTerm.homeScreenToolsLoadFailed:
        'We could not load the available tools. Try again.',
    ConsumerTerm.homeScreenRecentTitle: 'Recent',
    ConsumerTerm.homeScreenNoRecentTitle: 'No recent activity yet',
    ConsumerTerm.homeScreenNoRecentDescription:
        'Your recent activity will appear here.',
    ConsumerTerm.homeNextActionTitle: 'What to do next',
    ConsumerTerm.homeSeverityCritical: 'Critical',
    ConsumerTerm.homeSeverityUrgent: 'Urgent',
    ConsumerTerm.homeSeverityAttention: 'Attention',
    ConsumerTerm.homeSeverityNormal: 'Suggested',
    ConsumerTerm.homeSeverityRoutine: 'Routine',
    ConsumerTerm.homeAskPlaceholder:
        'Ask CLARA about health, symptoms, medicines...',
    ConsumerTerm.homeAskCamera: 'Scan medicine label or test',
    ConsumerTerm.homeAskVoice: 'Voice input',
    ConsumerTerm.homeAskText: 'Ask CLARA',
    ConsumerTerm.homeScheduleTitle: "Today's schedule",
    ConsumerTerm.homeScheduleEmpty: 'No schedule items for today',
    ConsumerTerm.homeScheduleMedication: 'Medication',
    ConsumerTerm.homeScheduleVisit: 'Visit',
    ConsumerTerm.homeScheduleTask: 'Care task',
    ConsumerTerm.homeRecentChangesTitle: 'Recent changes',
    ConsumerTerm.homeRecentChangesEmpty: 'No recent changes recorded',
    ConsumerTerm.homeRecentChangesRealSourceNotice:
        'From verified health records',
    ConsumerTerm.homeCaughtUpTitle: "You're all caught up for today",
    ConsumerTerm.homeCaughtUpDescription:
        'All completed items have been recorded. Take a rest or update if anything changes.',
    ConsumerTerm.homeProfessionalTools: 'Professional tools',
    ConsumerTerm.homeProfessionalDrawer: 'Professional menu',
    ConsumerTerm.profileHubToolsAndPrivacy: 'Tools & privacy',
    ConsumerTerm.profileHubVisitsTitle: 'Prepare for a visit',
    ConsumerTerm.profileHubVisitsDescription:
        'Gather questions and details for your appointment',
    ConsumerTerm.profileHubFamilyTitle: 'Family & sharing',
    ConsumerTerm.profileHubFamilyDescription:
        'Share the minimum with a supporter; revoke anytime',
    ConsumerTerm.profileHubEvidenceTitle: 'Living evidence',
    ConsumerTerm.profileHubEvidenceDescription:
        'Follow changes reviewed by experts',
    ConsumerTerm.profileHubCommunityTitle: 'Community',
    ConsumerTerm.profileHubCommunityDescription:
        'Share and ask questions with the health community',
    ConsumerTerm.profileHubHealthDataTitle: 'Health data',
    ConsumerTerm.profileHubHealthDataDescription:
        'Manage the sources you allowed to connect',
    ConsumerTerm.profileHubClinicalNotesTitle: 'Clinical notes',
    ConsumerTerm.profileHubClinicalNotesDescription:
        'Record and create a SOAP note',
    ConsumerTerm.profileHubCaseConsultationTitle: 'Case consultation',
    ConsumerTerm.profileHubCaseConsultationDescription:
        'Bring together specialist perspectives for complex cases',
    ConsumerTerm.profileHubConsentTitle: 'Privacy & consent',
    ConsumerTerm.profileHubConsentDescription: 'Manage consent by purpose',
    ConsumerTerm.profileHubDataRightsTitle: 'Personal data rights',
    ConsumerTerm.profileHubDataRightsDescription:
        'Export, correct, restrict, or delete your data',
    ConsumerTerm.profileHubSettingsTitle: 'Settings',
    ConsumerTerm.profileHubSettingsDescription:
        'Appearance, language, account, and privacy',
    ConsumerTerm.todayStartHereTitle: 'What would you like to do today?',
    ConsumerTerm.todayStartHereDescription:
        'Choose one task. CLARA only uses the information you have allowed.',
    ConsumerTerm.todayAskHealthTitle: 'Ask about a health concern',
    ConsumerTerm.todayAskHealthDescription:
        'Talk with CLARA and get clear guidance on the next step.',
    ConsumerTerm.todayCheckMedicineTitle: 'Check a medicine',
    ConsumerTerm.todayCheckMedicineDescription:
        'Review your medicines and safety information from a verified drug source.',
    ConsumerTerm.todaySaveHealthInfoTitle: 'Save health information',
    ConsumerTerm.todaySaveHealthInfoDescription:
        'Update your profile. Nothing is saved until you confirm it yourself.',
    ConsumerTerm.todayPrepareVisitTitle: 'Prepare for a visit',
    ConsumerTerm.todayPrepareVisitDescription:
        'Gather questions and information you want to bring to your appointment.',
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
    ConsumerTerm.loginSafetyTagline:
        'A safer health assistant — supporting decisions, not replacing a clinician.',
    ConsumerTerm.loginEmail: 'Email',
    ConsumerTerm.loginPassword: 'Password',
    ConsumerTerm.loginShowPassword: 'Show password',
    ConsumerTerm.loginHidePassword: 'Hide password',
    ConsumerTerm.loginSubmit: 'Sign in',
    ConsumerTerm.loginCreateAccount: 'Create an account',
    ConsumerTerm.loginForgotPassword: 'Forgot password?',
    ConsumerTerm.loginEmailRequired: 'Enter your email.',
    ConsumerTerm.loginPasswordRequired: 'Enter your password.',
    ConsumerTerm.loginUnauthorized:
        'Sign-in failed. Check your email and password.',
    ConsumerTerm.loginFailed: 'We could not sign you in right now. Try again.',
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
    ConsumerTerm.lifeMapProfileRequiredTitle:
        'Create your health profile first',
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
    ConsumerTerm.lifeMapTaskNameHint:
        'For example: Measure blood pressure in the morning',
    ConsumerTerm.lifeMapUnnamedTask: 'Unnamed task',
    ConsumerTerm.lifeMapOneQuestion: 'One question',
    ConsumerTerm.lifeMapViewHistory: 'View history',
    ConsumerTerm.lifeMapLoadFailed: 'We could not load LifeMap. Try again.',
    ConsumerTerm.lifeMapReplayLabel: 'Health Replay',
    ConsumerTerm.lifeMapReplayFallbackTitle: 'LifeMap history',
    ConsumerTerm.lifeMapReplayDescription:
        'Each item shows the exact version and rule used. Corrections need a '
            'network connection and are never queued offline.',
    ConsumerTerm.lifeMapReplayStale:
        'Some earlier results are being recalculated because source information changed.',
    ConsumerTerm.lifeMapReplayEmptyTitle: 'No records yet',
    ConsumerTerm.lifeMapReplayEmptyDescription:
        'This journey has no information to review yet.',
    ConsumerTerm.lifeMapReplayVersion: 'Version {revision}',
    ConsumerTerm.lifeMapReplayWhy: 'Why this appears: {reason}',
    ConsumerTerm.lifeMapReplayEdit: 'Correct information',
    ConsumerTerm.lifeMapReplayDispute: 'Needs review',
    ConsumerTerm.lifeMapReplayLoadFailed:
        'We could not load the history. Try again with a network connection.',
    ConsumerTerm.lifeMapCorrectionTitle: 'Correct information',
    ConsumerTerm.lifeMapCorrectionNotice:
        'This needs a network connection and creates a new version. The older '
            'version remains in the history.',
    ConsumerTerm.lifeMapCorrectionLabel: 'Correct information',
    ConsumerTerm.lifeMapCorrectionSave: 'Save new version',
    ConsumerTerm.lifeMapCorrectionSaved: 'New version saved.',
    ConsumerTerm.lifeMapMutationOffline:
        'We could not save this. Health changes are never queued offline.',
    ConsumerTerm.lifeMapDisputeTitle: 'Send for review',
    ConsumerTerm.lifeMapDisputeNotice:
        'A dispute does not erase information. CLARA keeps the source and opens '
            'a review queue. This action needs a network connection.',
    ConsumerTerm.lifeMapDisputeLabel: 'Why does this information need review?',
    ConsumerTerm.lifeMapDisputeSubmit: 'Send',
    ConsumerTerm.lifeMapDisputeSubmitted:
        'This information was sent to the review queue.',
    ConsumerTerm.lifeMapDisputeQueueTitle: 'Information under review',
    ConsumerTerm.lifeMapDisputeQueueNotice:
        'CLARA does not choose which side is correct. Each decision creates a '
            'new version and keeps the source history.',
    ConsumerTerm.lifeMapDisputeQueueVersion: '{eventType} · version {revision}',
    ConsumerTerm.lifeMapDisputeQueueOpen: 'Open',
    ConsumerTerm.lifeMapDisputeQueueResolved: 'Resolved',
    ConsumerTerm.lifeMapDisputeQueueClinicalReview:
        'This type of information needs someone with clinical authority to '
            'review the source.',
    ConsumerTerm.lifeMapDisputeQueueResolve:
        'Confirm after reviewing the source',
    ConsumerTerm.lifeMapSummarySectionTitle: 'Review LifeMap',
    ConsumerTerm.lifeMapSummaryDescription:
        'Groups existing records without changing which information is confirmed, disputed, or conflicting.',
    ConsumerTerm.lifeMapSummaryScope: 'Scope',
    ConsumerTerm.lifeMapSummaryDay: 'By day',
    ConsumerTerm.lifeMapSummaryWeek: 'By week',
    ConsumerTerm.lifeMapSummarySelectedJourney: 'Selected journey',
    ConsumerTerm.lifeMapSummaryCreate: 'Create summary',
    ConsumerTerm.lifeMapSummaryEmpty:
        'There are not enough records to create a summary.',
    ConsumerTerm.lifeMapSummaryCitation: 'source {citations}',
    ConsumerTerm.lifeMapSummarySafetyNotice:
        'This rule-based summary links to its sources and is not medical advice.',
    ConsumerTerm.lifeMapSummaryLoadFailed:
        'We could not create the summary. Try again.',
    ConsumerTerm.lifeMapReviewSectionTitle: 'Information for you to review',
    ConsumerTerm.lifeMapReviewDescription:
        'Rules only identify possible duplicates or conflicts; CLARA never chooses which record is correct.',
    ConsumerTerm.lifeMapReviewCheck: 'Check',
    ConsumerTerm.lifeMapReviewPossibleContradiction: 'Possible conflict',
    ConsumerTerm.lifeMapReviewPossibleDuplicate: 'Possible duplicate',
    ConsumerTerm.lifeMapReviewNeedsMoreInformation: 'Needs more information',
    ConsumerTerm.lifeMapReviewBasedOnSavedRecords:
        'Based on information you saved in LifeMap.',
    ConsumerTerm.lifeMapReviewResolved: 'I checked this',
    ConsumerTerm.lifeMapReviewDismiss: 'No action needed',
    ConsumerTerm.lifeMapReviewRecorded: 'Your choice was recorded.',
    ConsumerTerm.lifeMapReviewLoadFailed:
        'We could not check this information. Try again.',
    ConsumerTerm.lifeMapCaptureSectionTitle: 'Quick capture',
    ConsumerTerm.lifeMapCaptureCreateDescription:
        'Create a draft to review before it goes into LifeMap.',
    ConsumerTerm.lifeMapCaptureInputLabel: 'What would you like to record?',
    ConsumerTerm.lifeMapCaptureInputHint:
        'For example: I slept about 7 hours last night',
    ConsumerTerm.lifeMapCaptureCreate: 'Create draft',
    ConsumerTerm.lifeMapCaptureArtifactTitle: 'Capture from a photo',
    ConsumerTerm.lifeMapCaptureArtifactDescription:
        'A photo only creates a draft. Check the source, fix missing fields, and explicitly confirm before saving.',
    ConsumerTerm.lifeMapCaptureSourceType: 'Source type',
    ConsumerTerm.lifeMapCaptureMedicationLabel: 'Medicine label',
    ConsumerTerm.lifeMapCaptureVisitDocument: 'Visit document',
    ConsumerTerm.lifeMapCaptureTakePhoto: 'Take photo',
    ConsumerTerm.lifeMapCaptureChoosePhoto: 'Choose photo',
    ConsumerTerm.lifeMapCaptureCreateFailed:
        'We could not create the draft. Try again.',
    ConsumerTerm.lifeMapCaptureImageInvalid:
        'The image must be non-empty and smaller than 10 MB.',
    ConsumerTerm.lifeMapCaptureUploading: 'Uploading the source securely…',
    ConsumerTerm.lifeMapCaptureReading:
        'The source is being read. No information has been confirmed.',
    ConsumerTerm.lifeMapCaptureUploadFailed:
        'We could not upload the source. Try again.',
    ConsumerTerm.lifeMapCaptureReadingFailed:
        'We could not read the source. The draft was not confirmed.',
    ConsumerTerm.lifeMapCaptureJobPending:
        'The task is still processing. Check again later.',
    ConsumerTerm.lifeMapCaptureRefreshFailed:
        'We could not refresh the draft. Try again.',
    ConsumerTerm.lifeMapCaptureConfirmFailed:
        'We could not confirm the record. Try again.',
    ConsumerTerm.lifeMapCaptureAbandonOffline:
        'A network connection is required to discard this draft.',
    ConsumerTerm.lifeMapCaptureEmergencyFallback:
        'If you may be in immediate danger, call local emergency services or go to the nearest emergency department.',
    ConsumerTerm.lifeMapCaptureDeleteSourceDraft: 'Delete source draft',
    ConsumerTerm.lifeMapCaptureDraft: 'Draft not confirmed',
    ConsumerTerm.lifeMapCaptureRejected: 'Draft rejected',
    ConsumerTerm.lifeMapCaptureConfirmed: 'Record confirmed',
    ConsumerTerm.lifeMapCaptureOnlineNotice:
        'This is only processed online. CLARA never confirms it automatically, and offline information may be stale.',
    ConsumerTerm.lifeMapCaptureLowConfidence:
        'Some parts are unclear from the source. Compare them before saving.',
    ConsumerTerm.lifeMapCaptureMissingFields: 'Missing: {fields}',
    ConsumerTerm.lifeMapCaptureUnsafe:
        'The source contains unsafe content and cannot be confirmed.',
    ConsumerTerm.lifeMapCaptureNormalizeTitle: 'Normalize medicine name',
    ConsumerTerm.lifeMapCaptureNormalizeLoading:
        'Checking the medicine dictionary…',
    ConsumerTerm.lifeMapCaptureNormalizeUnavailable:
        'No matching standard code was found. The original name is retained and has not been normalized.',
    ConsumerTerm.lifeMapCaptureNormalizeProposal:
        'Suggestion: {name} · RxNorm {code}',
    ConsumerTerm.lifeMapCaptureNormalizeUseCode:
        'Use this standard code for my medicine record',
    ConsumerTerm.lifeMapCaptureNormalizeUseCodeNotice:
        'The record is created only after you confirm it.',
    ConsumerTerm.lifeMapCaptureEdit: 'Edit',
    ConsumerTerm.lifeMapCaptureReject: 'Reject',
    ConsumerTerm.lifeMapCaptureConfirm: 'Confirm',
    ConsumerTerm.lifeMapCaptureAbandon: 'Discard and delete draft',
    ConsumerTerm.lifeMapCaptureProcessing: 'Source draft is processing',
    ConsumerTerm.lifeMapCaptureCheckResult: 'Check result',
    ConsumerTerm.lifeMapCaptureEditTitle: 'Edit draft',
    ConsumerTerm.lifeMapCaptureEditSave: 'Save changes',
    ConsumerTerm.lifeMapCaptureSourceImageLabel: 'Source image {name}',
    ConsumerTerm.lifeMapCaptureSourcePreviewError:
        'We could not display the source image.',
    ConsumerTerm.lifeMapCaptureSourcePreview:
        'Source: {name} · retained in memory only while you review it.',
    ConsumerTerm.lifeMapCaptureSourceUncached:
        'The source image is not stored in the device cache. Check the original before confirming.',
    ConsumerTerm.lifeMapAskSectionTitle: 'Ask my LifeMap',
    ConsumerTerm.lifeMapAskSafetyNotice:
        'Only searches information you are allowed to view. CLARA does not diagnose, prescribe, or change LifeMap on its own.',
    ConsumerTerm.lifeMapAskInputLabel: 'What would you like to find?',
    ConsumerTerm.lifeMapAskInputHint: 'For example: Recent headache records?',
    ConsumerTerm.lifeMapAskInputHelp:
        'The answer identifies the exact records and versions used.',
    ConsumerTerm.lifeMapAskSubmit: 'Search',
    ConsumerTerm.lifeMapAskCitation: 'Source: {source} · version {revision}',
    ConsumerTerm.lifeMapAskAnswerSafetyNotice:
        'AI with sources · Read-only · Not medical advice.',
    ConsumerTerm.lifeMapAskLoadFailed:
        'We could not search LifeMap. Try again.',
    ConsumerTerm.lifeMapQuestionNoneNeeded:
        'No question is needed now. CLARA asks as little as possible.',
    ConsumerTerm.lifeMapQuestionWhy: 'Why CLARA asks: {reason}',
    ConsumerTerm.lifeMapQuestionAnswerLabel: 'Your answer',
    ConsumerTerm.lifeMapQuestionAnswerHelp:
        'This creates a draft for you to review first.',
    ConsumerTerm.lifeMapQuestionLater: 'Later',
    ConsumerTerm.lifeMapQuestionCreateDraft: 'Create draft',
    ConsumerTerm.lifeMapQuestionDraftCreated:
        'Draft created. Review it, then explicitly confirm.',
    ConsumerTerm.lifeMapQuestionLoadFailed:
        'We could not load the question. Try again with a network connection.',
    ConsumerTerm.lifeMapBaselineSectionTitle: 'Changes relative to you',
    ConsumerTerm.lifeMapBaselineNotice:
        'This is not a clinical normal range or a diagnosis.',
    ConsumerTerm.lifeMapBaselineSamples: '{days} days of data · {version}',
    ConsumerTerm.lifeMapBaselineInsufficientData: 'Not enough data',
    ConsumerTerm.medicinesMyMedicines: 'My medicines',
    ConsumerTerm.medicinesCabinet: 'Medicine cabinet',
    ConsumerTerm.medicinesSafety: 'Safety',
    ConsumerTerm.medicinesLoginRequired:
        'Please sign in to view your medicine list.',
    ConsumerTerm.medicinesLoadFailed:
        'We could not load your medicine list. Try again.',
    ConsumerTerm.medicinesProfileRequiredTitle: 'Health profile required',
    ConsumerTerm.medicinesProfileRequiredDescription:
        'Create your health profile before adding medicine. Your medicine list '
            'will appear here once it is ready.',
    ConsumerTerm.medicinesReload: 'Reload',
    ConsumerTerm.medicinesEmptyTitle: 'No medicines yet',
    ConsumerTerm.medicinesEmptyDescription:
        'Add medicines you are taking so CLARA can help you keep track. '
            'Information is saved only after you confirm it.',
    ConsumerTerm.medicinesAdd: 'Add medicine',
    ConsumerTerm.medicinesUnnamed: 'Unnamed medicine',
    ConsumerTerm.medicinesEnded: 'Ended',
    ConsumerTerm.medicinesActive: 'Taking now',
    ConsumerTerm.medicinesSourceMatched: 'Source matched',
    ConsumerTerm.medicinesUnverified: 'Not verified',
    ConsumerTerm.medicinesActionsTooltip: 'Medicine actions',
    ConsumerTerm.medicinesEditNewVersion: 'Edit as a new version',
    ConsumerTerm.medicinesEndCourse: 'Record as ended',
    ConsumerTerm.medicinesEndConfirmTitle: 'Record this medicine as ended?',
    ConsumerTerm.medicinesEndConfirmDescription:
        'This only updates your record; it is not advice to stop the medicine. '
            'Do not stop a medicine without speaking with a health professional.',
    ConsumerTerm.medicinesEndAuditReason:
        'User recorded the medicine as ended in the mobile app',
    ConsumerTerm.medicinesCancel: 'Cancel',
    ConsumerTerm.medicinesConfirm: 'Record',
    ConsumerTerm.medicinesNameRequired: 'Enter the medicine name.',
    ConsumerTerm.medicinesLoginToAdd: 'Please sign in to add a medicine.',
    ConsumerTerm.medicinesEditReasonRequired: 'Enter a reason for this edit.',
    ConsumerTerm.medicinesSaveFailed:
        'We could not save this medicine. Try again.',
    ConsumerTerm.medicinesAddTitle: 'Add medicine',
    ConsumerTerm.medicinesEditTitle: 'Edit medicine details',
    ConsumerTerm.medicinesNameLabel: 'Medicine name *',
    ConsumerTerm.medicinesNameHint: 'For example: Paracetamol',
    ConsumerTerm.medicinesDoseLabel: 'Dose',
    ConsumerTerm.medicinesDoseHint: 'For example: 500 mg',
    ConsumerTerm.medicinesScheduleLabel: 'Schedule',
    ConsumerTerm.medicinesScheduleHint: 'For example: twice daily after food',
    ConsumerTerm.medicinesRouteLabel: 'Route',
    ConsumerTerm.medicinesRouteHint: 'For example: by mouth',
    ConsumerTerm.medicinesFormLabel: 'Form',
    ConsumerTerm.medicinesFormHint: 'For example: tablet',
    ConsumerTerm.medicinesEditReasonLabel: 'Reason for edit *',
    ConsumerTerm.medicinesEditReasonHint:
        'For example: correct an entry mistake',
    ConsumerTerm.medicinesSave: 'Save medicine',
    ConsumerTerm.medicinesSaveNewVersion: 'Save new version',
    ConsumerTerm.medicinesSafetyTitle: 'Check medicine interactions',
    ConsumerTerm.medicinesSafetyDescription:
        'Medicine-interaction checks happen in Medicine cabinet. When you add '
            'two or more medicines there, CLARA reviews potential interactions '
            'against that list.',
    ConsumerTerm.medicinesOpenCabinet: 'Open medicine cabinet',
    ConsumerTerm.medicinesSafetyNotice:
        'CLARA is a decision-support assistant, not a substitute for a doctor. '
            'Check results are for reference only — speak with a pharmacist or '
            'doctor before changing how you use a medicine.',
    ConsumerTerm.visitsTitle: 'Prepare for a visit',
    ConsumerTerm.visitsCreate: 'Create visit',
    ConsumerTerm.visitsClose: 'Close',
    ConsumerTerm.visitsProfileRequiredTitle: 'Create your health profile first',
    ConsumerTerm.visitsProfileRequiredDescription:
        'Create your health profile before preparing for a visit. This helps '
            'you have a more useful conversation with your doctor; it is not a diagnosis.',
    ConsumerTerm.visitsEmptyTitle: 'No visits yet',
    ConsumerTerm.visitsEmptyDescription:
        'Create a visit to prepare what you want to discuss with your doctor. '
            'CLARA helps you organize concerns; it does not diagnose.',
    ConsumerTerm.visitsSafetyLabel: 'Visit preparation note',
    ConsumerTerm.visitsSafetyNotice:
        'A visit helps you prepare before you see a doctor. It is not medical '
            'advice or a diagnosis.',
    ConsumerTerm.visitsNameLabel: 'Visit name',
    ConsumerTerm.visitsNameHint: 'For example: Routine cardiology visit',
    ConsumerTerm.visitsReasonLabel: 'Reason for visit (optional)',
    ConsumerTerm.visitsReasonHint: 'What you want to discuss with your doctor',
    ConsumerTerm.visitsUnnamed: 'Unnamed visit',
    ConsumerTerm.visitsPreparationTitle: 'Visit preparation',
    ConsumerTerm.visitsOpenPreparation: 'Open preparation',
    ConsumerTerm.visitsNoSchedule: 'Not scheduled',
    ConsumerTerm.visitsScheduledDate: 'Scheduled: {date}',
    ConsumerTerm.visitsNameRequired: 'Enter a visit name.',
    ConsumerTerm.visitsLoadFailed: 'We could not load your visits. Try again.',
    ConsumerTerm.visitsCreateFailed:
        'We could not create the visit. Try again.',
    ConsumerTerm.visitDraftTitle: 'Visit preparation draft',
    ConsumerTerm.visitDraftDescription:
        'Create a private draft from LifeMap records to review, edit, and bring to your visit.',
    ConsumerTerm.visitDraftGoalLabel: 'What would you like to prepare for?',
    ConsumerTerm.visitDraftGoalHint:
        'For example: I want to discuss my recent headache records.',
    ConsumerTerm.visitDraftCreate: 'Create draft',
    ConsumerTerm.visitDraftCreating: 'Creating draft…',
    ConsumerTerm.visitDraftReviewNotice:
        'This is a draft for you to review and edit. It does not change your health record.',
    ConsumerTerm.visitDraftImportantNow: 'Most important right now',
    ConsumerTerm.visitDraftSources: 'What CLARA used',
    ConsumerTerm.visitDraftNoSources:
        'There are no matching records in the selected scope yet.',
    ConsumerTerm.visitDraftUncertainty: 'What is uncertain',
    ConsumerTerm.visitDraftNoUncertainty:
        'This draft does not identify an uncertainty.',
    ConsumerTerm.visitDraftNextStep: 'What you can do next',
    ConsumerTerm.visitDraftUrgentHelp: 'When to seek urgent help',
    ConsumerTerm.visitDraftQuestions: 'Questions to consider at your visit',
    ConsumerTerm.visitDraftNoQuestions:
        'There are no questions from the current records yet.',
    ConsumerTerm.visitDraftCopy: 'Copy draft',
    ConsumerTerm.visitDraftCopied: 'Draft copied.',
    ConsumerTerm.visitDraftCreateFailed:
        'We could not create the draft. Check your connection and try again.',
    ConsumerTerm.visitDetailPreparationNotice:
        'CLARA helps you prepare for a conversation with your doctor; it does '
            'not diagnose or prescribe. Only content you choose and approve is used.',
    ConsumerTerm.visitDetailConcernsTitle: '1. What you want to ask',
    ConsumerTerm.visitDetailConcernLabel:
        'What you want to discuss with your doctor',
    ConsumerTerm.visitDetailSaveConcern: 'Save question',
    ConsumerTerm.visitDetailDocumentsTitle: '2. Documents you choose',
    ConsumerTerm.visitDetailDocumentsDescription:
        'Paste content you selected. CLARA does not open links or import records on its own.',
    ConsumerTerm.visitDetailDocumentTitle: 'Document title',
    ConsumerTerm.visitDetailDocumentContent: 'Selected text content',
    ConsumerTerm.visitDetailSaveDocument: 'Save document',
    ConsumerTerm.visitDetailInactiveDocument: 'Removed from processing',
    ConsumerTerm.visitDetailControlledDocument: 'Under your control',
    ConsumerTerm.visitDetailCheckPlan: 'Review plan',
    ConsumerTerm.visitDetailWithdrawDocument: 'Remove from processing',
    ConsumerTerm.visitDetailDeleteDocument: 'Delete content',
    ConsumerTerm.visitDetailReviewTitle: '3. Evidence-based review',
    ConsumerTerm.visitDetailNoEvidence:
        'There are no sufficiently supported items to suggest. Check with your doctor.',
    ConsumerTerm.visitDetailReviewGuidance:
        'Only confirm clinician instructions that have an exact source quote.',
    ConsumerTerm.visitDetailSource: 'Source: “{source}”',
    ConsumerTerm.visitDetailUnconfirmableCandidate:
        'AI interpretation or missing source — cannot be confirmed.',
    ConsumerTerm.visitDetailConfirmSelected: 'Confirm selected items',
    ConsumerTerm.visitDetailWithdrawDraft: 'Withdraw draft',
    ConsumerTerm.visitDetailPackTitle: '4. Select and approve Visit Pack',
    ConsumerTerm.visitDetailPackNotice:
        'No item is added or shared automatically.',
    ConsumerTerm.visitDetailNoMatchingItems: 'No matching items yet.',
    ConsumerTerm.visitDetailPackConcerns: 'Questions to ask',
    ConsumerTerm.visitDetailPackMedications: 'Confirmed medicines',
    ConsumerTerm.visitDetailPackEpisodes: 'Related care journeys',
    ConsumerTerm.visitDetailPackEvents: 'Confirmed events',
    ConsumerTerm.visitDetailPackInstructions:
        'Clinician instructions you confirmed',
    ConsumerTerm.visitDetailCreatePack: 'Create and approve pack',
    ConsumerTerm.visitDetailCreateNewPackVersion: 'Create a new version',
    ConsumerTerm.visitDetailApprovedPackVersion:
        'You approved version {version}.',
    ConsumerTerm.visitDetailCreateShare: 'Create 7-day link',
    ConsumerTerm.visitDetailRevokeShare: 'Revoke link',
    ConsumerTerm.visitDetailScribeConsentTitle:
        'Consent to recording for this visit',
    ConsumerTerm.visitDetailScribeConsentDescription:
        'You can withdraw it immediately. Without consent, Scribe cannot process recording.',
    ConsumerTerm.visitDetailScribeConsentGranted:
        'Consent granted for this visit',
    ConsumerTerm.visitDetailScribeConsentNotGranted: 'Recording not consented',
    ConsumerTerm.visitDetailLoadFailed:
        'We could not load this visit. Try again.',
    ConsumerTerm.visitDetailActionFailed:
        'We could not complete that action. Try again.',
    ConsumerTerm.visitDetailConcernRequired:
        'Enter what you want to ask your doctor.',
    ConsumerTerm.visitDetailDocumentRequired:
        'Give the document a title and paste the content you chose.',
    ConsumerTerm.familyTitle: 'Family & sharing',
    ConsumerTerm.familySupporter: 'Supporter',
    ConsumerTerm.familyNewNotification: 'New notification',
    ConsumerTerm.familyAccessGrant: 'Access grant',
    ConsumerTerm.familyInvite: 'Invite a supporter',
    ConsumerTerm.familyClose: 'Close',
    ConsumerTerm.familySharingNoteSemanticLabel:
        'Note about sharing with a supporter',
    ConsumerTerm.familySharingNote:
        'Share the minimum with a supporter. You choose what to share and can '
            'revoke access at any time.',
    ConsumerTerm.familySharedWith: 'People you share with',
    ConsumerTerm.familyEmptyTitle: 'Not sharing with anyone yet',
    ConsumerTerm.familyEmptyDescription:
        'Invite a supporter when you need help. You control what is shared and '
            'can revoke access at any time.',
    ConsumerTerm.familyNotifications: 'Notifications to review',
    ConsumerTerm.familyActiveGrants: 'Active access',
    ConsumerTerm.familyAccessLog: 'Recent access log',
    ConsumerTerm.familyAccessLogActorOwner: 'You',
    ConsumerTerm.familyAccessLogActorSupporter: 'Supporter',
    ConsumerTerm.familyAccessLogActorSystem: 'System',
    ConsumerTerm.familyAccessLogActorOther: 'User',
    ConsumerTerm.familyAccessLogActionView: 'viewed shared data',
    ConsumerTerm.familyAccessLogActionAddObservation: 'added an observation',
    ConsumerTerm.familyAccessLogActionCompleteTask: 'completed a care task',
    ConsumerTerm.familyAccessLogActionInvitationAccept:
        'accepted an invitation',
    ConsumerTerm.familyAccessLogActionGrantRevoke: 'revoked access',
    ConsumerTerm.familyAccessLogActionGrantRenewalInvited:
        'created a renewal invitation',
    ConsumerTerm.familyAccessLogActionNotificationAcknowledged:
        'acknowledged a notification',
    ConsumerTerm.familyAccessLogActionOther: 'recorded an access action',
    ConsumerTerm.familyAccessLogOutcomeAllowed: 'allowed',
    ConsumerTerm.familyAccessLogOutcomeDenied: 'denied',
    ConsumerTerm.familyAccessLogOutcomeFailed: 'not completed',
    ConsumerTerm.familyAccessLogOutcomeUnknown: 'unknown',
    ConsumerTerm.familyEmailLabel: 'Supporter email',
    ConsumerTerm.familyEmailHint: 'example@email.com',
    ConsumerTerm.familyScopeLabel: 'Share only',
    ConsumerTerm.familyScopeJourney: 'One health journey',
    ConsumerTerm.familyScopeVisit: 'One visit',
    ConsumerTerm.familySharedItemLabel: 'Shared item',
    ConsumerTerm.familyPurposeLabel: 'Purpose',
    ConsumerTerm.familyPurposeCareCoordination: 'Care coordination',
    ConsumerTerm.familyPurposeVisitSupport: 'Visit support',
    ConsumerTerm.familySendInvitation: 'Send invitation',
    ConsumerTerm.familyInvitationTokenNotice:
        'This code is shown only once. Send it through a channel you trust:',
    ConsumerTerm.familyAcknowledge: 'Reviewed',
    ConsumerTerm.familyExpiresAt: 'Expires: {date}',
    ConsumerTerm.familyRenew: 'Renew',
    ConsumerTerm.familyRevoke: 'Revoke',
    ConsumerTerm.familyRevokeConfirmTitle: 'Revoke access?',
    ConsumerTerm.familyRevokeConfirmDescription:
        'After revocation, "{name}" can no longer see what you shared. You '
            'can invite them again later.',
    ConsumerTerm.familyCancel: 'Cancel',
    ConsumerTerm.familyEmailRequired: 'Enter your supporter\'s email.',
    ConsumerTerm.familySharedItemRequired:
        'Choose the health journey or visit you want to share.',
    ConsumerTerm.familyInvitationCreated:
        'Invitation code created. CLARA has not sent an email automatically.',
    ConsumerTerm.familyInvitationFailed:
        'We could not create the invitation. Try again.',
    ConsumerTerm.familyNotificationUnavailable:
        'This notification cannot be acknowledged.',
    ConsumerTerm.familyAcknowledgeFailed:
        'We could not acknowledge this. Try again.',
    ConsumerTerm.familyGrantUnavailable: 'This access grant cannot be revoked.',
    ConsumerTerm.familyRevoked: 'Access revoked.',
    ConsumerTerm.familyRevokeFailed: 'We could not revoke access. Try again.',
    ConsumerTerm.familyRenewed:
        'Renewal code created; the recipient must accept it again.',
    ConsumerTerm.familyRenewFailed: 'We could not create a renewal invitation.',
    ConsumerTerm.familyLoadFailed:
        'We could not load sharing details. Try again.',
    ConsumerTerm.familyUseInvitationCode: 'Use an invitation code',
    ConsumerTerm.familyInvitationAcceptTitle: 'Review a sharing invitation',
    ConsumerTerm.familyInvitationAcceptDescription:
        'Enter the code sent privately to you. CLARA shows the scope before you '
            'agree.',
    ConsumerTerm.familyInvitationCodeLabel: 'Invitation code',
    ConsumerTerm.familyInvitationCodeHint: 'Paste the invitation code here',
    ConsumerTerm.familyInvitationCodeRequired: 'Enter the invitation code.',
    ConsumerTerm.familyPreviewInvitation: 'Preview invitation',
    ConsumerTerm.familyPreviewingInvitation: 'Previewing invitation…',
    ConsumerTerm.familyInvitationPreviewTitle: 'You would share the following',
    ConsumerTerm.familyInvitationPreviewNotice:
        'This step does not grant access or open health data. Access is created '
            'only if you choose to accept.',
    ConsumerTerm.familyInvitationScopeLabel: 'Sharing scope',
    ConsumerTerm.familyInvitationActionsLabel: 'This person can',
    ConsumerTerm.familyInvitationExpiryUnavailable: 'Expiry unavailable',
    ConsumerTerm.familyInvitationScopeCareTask: 'One care task',
    ConsumerTerm.familyInvitationActionView: 'View the information shared',
    ConsumerTerm.familyInvitationActionAddObservation: 'Add an observation',
    ConsumerTerm.familyInvitationActionCompleteTask: 'Complete a care task',
    ConsumerTerm.familyInvitationActionOther: 'Perform a limited action',
    ConsumerTerm.familyInvitationPreviewFailed:
        'We could not preview this invitation. Check the code and try again.',
    ConsumerTerm.familyInvitationAccept: 'Accept this sharing',
    ConsumerTerm.familyAcceptingInvitation: 'Accepting…',
    ConsumerTerm.familyInvitationAccepted: 'You accepted this sharing access.',
    ConsumerTerm.familyInvitationAcceptFailed:
        'We could not accept this invitation. Check the code and try again.',
    ConsumerTerm.connectedHealthTitle: 'Health data',
    ConsumerTerm.connectedHealthIntroTitle: 'Connect when you want',
    ConsumerTerm.connectedHealthIntroDescription:
        'CLARA reads only the data categories you allow. You can pause, '
            'disconnect, or delete imported data at any time.',
    ConsumerTerm.connectedHealthSourcesTitle: 'Connected sources',
    ConsumerTerm.connectedHealthBeforeConnectingTitle: 'Before you connect',
    ConsumerTerm.connectedHealthChooseDataTitle:
        'You choose which data is used',
    ConsumerTerm.connectedHealthChooseDataDescription:
        'For example: steps, sleep, or heart rate. CLARA does not make up '
            'missing data.',
    ConsumerTerm.connectedHealthPrivateDataTitle:
        'Personal data is not sent to chat automatically',
    ConsumerTerm.connectedHealthPrivateDataDescription:
        'You must allow the health-support purpose before data is used in '
            'personal guidance.',
    ConsumerTerm.connectedHealthEmptyTitle: 'No source is connected yet',
    ConsumerTerm.connectedHealthEmptyDescription:
        'When a device connection is available, CLARA will always ask for '
            'permission before reading its data.',
    ConsumerTerm.connectedHealthFallbackSourceTitle: 'Health source',
    ConsumerTerm.connectedHealthAllowedData: 'Allowed: {types}',
    ConsumerTerm.connectedHealthPause: 'Pause',
    ConsumerTerm.connectedHealthResume: 'Resume',
    ConsumerTerm.connectedHealthDisconnect: 'Disconnect',
    ConsumerTerm.connectedHealthDeleteImportedData: 'Delete data',
    ConsumerTerm.connectedHealthStatusHealthy: 'Up to date',
    ConsumerTerm.connectedHealthStatusConnected: 'Ready',
    ConsumerTerm.connectedHealthStatusPaused: 'Paused',
    ConsumerTerm.connectedHealthStatusNeedsReauth: 'Permission needed again',
    ConsumerTerm.connectedHealthStatusDisconnected: 'Disconnected',
    ConsumerTerm.connectedHealthStatusUnknown: 'Unknown',
    ConsumerTerm.connectedHealthLoadFailedTitle:
        'We could not load health sources',
    ConsumerTerm.connectedHealthDisconnectConfirmTitle:
        'Disconnect this source?',
    ConsumerTerm.connectedHealthDisconnectConfirmDescription:
        'Imported data stays available. You can delete that data separately below.',
    ConsumerTerm.connectedHealthDisconnectConfirmAction: 'Disconnect',
    ConsumerTerm.connectedHealthDeleteConfirmTitle: 'Delete imported data?',
    ConsumerTerm.connectedHealthDeleteConfirmDescription:
        'This deletes observations and summaries from this source. It cannot be undone.',
    ConsumerTerm.connectedHealthDeleteConfirmAction: 'Delete data',
    ConsumerTerm.connectedHealthDeleteSuccess:
        'Imported data from this source was deleted.',
    ConsumerTerm.connectedHealthCancel: 'Cancel',
    ConsumerTerm.livingEvidenceTitle: 'Living evidence',
    ConsumerTerm.livingEvidenceSafetyNotice:
        'CLARA notifies you only about important changes after expert review. '
            'New search results do not automatically become recommendations.',
    ConsumerTerm.livingEvidenceReviewedChanges: 'Reviewed changes',
    ConsumerTerm.livingEvidenceNotificationSemanticLabel:
        'Open evidence-change notification',
    ConsumerTerm.livingEvidenceRead: 'Read',
    ConsumerTerm.livingEvidenceMarkRead: 'Tap to mark as read',
    ConsumerTerm.livingEvidenceSubscriptions: 'Following',
    ConsumerTerm.livingEvidenceEmptyTitle: 'You are not following a question',
    ConsumerTerm.livingEvidenceEmptyDescription:
        'Create a question below to start.',
    ConsumerTerm.livingEvidenceNewQuestion: 'Create a question',
    ConsumerTerm.livingEvidenceJourneyLabel: 'LifeMap journey',
    ConsumerTerm.livingEvidenceQuestionLabel: 'What you want to know',
    ConsumerTerm.livingEvidenceContextLabel: 'Confirmed context (optional)',
    ConsumerTerm.livingEvidenceCreateAndFollow: 'Confirm, search, and follow',
    ConsumerTerm.livingEvidenceLoadFailed:
        'We could not load evidence tracking.',
    ConsumerTerm.livingEvidenceRunIncomplete:
        'The evidence search did not finish; no conclusion was released.',
    ConsumerTerm.livingEvidenceCreateFailed:
        'We could not create evidence tracking.',
    ConsumerTerm.livingEvidenceIntervalFailed:
        'We could not update the frequency.',
    ConsumerTerm.livingEvidenceStopFailed: 'We could not stop following.',
    ConsumerTerm.livingEvidenceSubscriptionTitle: 'Evidence tracking',
    ConsumerTerm.livingEvidenceApplicabilityPending:
        'Applicability has not been assessed.',
    ConsumerTerm.livingEvidenceNoContradictions:
        'Contradictions: not assessed or no report is available.',
    ConsumerTerm.livingEvidenceContradictionsCount:
        'Contradictions to review: {count}.',
    ConsumerTerm.livingEvidenceIntervalLabel: 'Check frequency',
    ConsumerTerm.livingEvidenceEveryDay: 'Every day',
    ConsumerTerm.livingEvidenceEveryWeek: 'Every week',
    ConsumerTerm.livingEvidenceEveryThirtyDays: 'Every 30 days',
    ConsumerTerm.livingEvidenceStopFollowing: 'Stop following',
    ConsumerTerm.socialSessionExpired:
        'Your session has expired. Please sign in again.',
    ConsumerTerm.socialLoadFailed:
        'We could not load the community. Try again.',
    ConsumerTerm.socialNoCommunities:
        'There are no communities to post in yet.',
    ConsumerTerm.socialConsentTitle: 'Join the CLARA community',
    ConsumerTerm.socialConsentDescription:
        'The community is a place to share experience and support one another. '
            'It is NOT medical advice: no prescribing, diagnosis, or personal '
            'dosage advice. Content is moderated for safety. Do you agree to the '
            'community rules and privacy terms?',
    ConsumerTerm.socialConsentAgree: 'I agree to join',
    ConsumerTerm.socialLater: 'Not now',
    ConsumerTerm.socialTitle: 'Community',
    ConsumerTerm.socialProfileTooltip: 'Community profile',
    ConsumerTerm.socialPost: 'Post',
    ConsumerTerm.socialConsentCardSemanticLabel: 'Join the community',
    ConsumerTerm.socialConsentCardTitle: 'Join to post and comment',
    ConsumerTerm.socialConsentCardDescription:
        'You can still read posts. Agree to the community rules to take part.',
    ConsumerTerm.socialJoin: 'Join',
    ConsumerTerm.socialCommunities: 'Communities',
    ConsumerTerm.socialFeed: 'Feed',
    ConsumerTerm.socialEmptyFeed: 'No posts yet. Be the first to share.',
    ConsumerTerm.socialReactionSent: 'Your helpful reaction was sent.',
    ConsumerTerm.socialReactionHelpful: 'Helpful',
    ConsumerTerm.socialAnonymous: 'anonymous',
    ConsumerTerm.socialDisclaimer:
        'The community is for peer support and does not replace a doctor. '
            'Personal prescribing, diagnosis, and dosage content is blocked.',
    ConsumerTerm.socialMembers: '{count} members',
    ConsumerTerm.socialJoined: 'Joined',
    ConsumerTerm.socialUnavailableTitle: 'Community is coming soon',
    ConsumerTerm.socialUnavailableDescription:
        'The health community feature is being prepared and will open soon.',
    ConsumerTerm.socialComposeTitle: 'Share with the community',
    ConsumerTerm.socialCommunityLabel: 'Community',
    ConsumerTerm.socialPostTitleLabel: 'Title',
    ConsumerTerm.socialPostBodyLabel: 'Content',
    ConsumerTerm.socialComposeRequired:
        'Enter a title and content, then choose a community.',
    ConsumerTerm.socialComments: 'Comments',
    ConsumerTerm.socialEmptyComments:
        'No comments yet. Be the first to comment.',
    ConsumerTerm.socialCommentLabel: 'Write a comment…',
    ConsumerTerm.socialCommentJoinRequired: 'Join the community to comment.',
    ConsumerTerm.socialModerationBlocked:
        'This comment does not follow the community rules (no prescribing, '
            'diagnosis, or dosage advice), or it may show an emergency sign.',
    ConsumerTerm.socialReportTitle: 'Report post',
    ConsumerTerm.socialReportDescription:
        'Report content that breaks the community rules (personal prescribing, '
            'diagnosis, dosage advice, spam, or other unsuitable content). Our '
            'moderation team will review it.',
    ConsumerTerm.socialCancel: 'Cancel',
    ConsumerTerm.socialReport: 'Report',
    ConsumerTerm.socialReportSent: 'Your report was sent. Thank you.',
    ConsumerTerm.socialClose: 'Close',
    ConsumerTerm.socialProfileTitle: 'Community profile',
    ConsumerTerm.socialDisplayNameLabel: 'Display name',
    ConsumerTerm.socialBioLabel:
        'About you (do not share personal health information)',
    ConsumerTerm.socialSaveProfile: 'Save profile',
    ConsumerTerm.socialProfileSaved: 'Community profile saved.',
    ConsumerTerm.socialDoctor: 'Doctor',
    ConsumerTerm.socialResearcher: 'Researcher',
    ConsumerTerm.moreTitle: 'More',
    ConsumerTerm.moreOtherToolsTitle: 'Other tools',
    ConsumerTerm.settingsTitle: 'Settings',
    ConsumerTerm.settingsAppearanceTitle: 'Appearance',
    ConsumerTerm.settingsThemeLight: 'Light',
    ConsumerTerm.settingsThemeDark: 'Dark',
    ConsumerTerm.settingsThemeSystem: 'System',
    ConsumerTerm.settingsLanguageTitle: 'Language',
    ConsumerTerm.settingsSelected: 'selected',
    ConsumerTerm.settingsNotSelected: 'not selected',
    ConsumerTerm.settingsAccountTitle: 'Account',
    ConsumerTerm.settingsEmailLabel: 'Email',
    ConsumerTerm.settingsRoleLabel: 'Role',
    ConsumerTerm.settingsNoInformation: 'No information yet',
    ConsumerTerm.settingsRoleConsumer: 'Consumer',
    ConsumerTerm.settingsRoleResearcher: 'Researcher',
    ConsumerTerm.settingsRoleDoctor: 'Doctor',
    ConsumerTerm.settingsRoleAdmin: 'Administrator',
    ConsumerTerm.settingsSignOut: 'Sign out',
    ConsumerTerm.settingsSignOutConfirmTitle: 'Sign out',
    ConsumerTerm.settingsSignOutConfirmDescription:
        'Are you sure you want to sign out of CLARA? The sign-in session on this device will be removed.',
    ConsumerTerm.settingsCancel: 'Cancel',
    ConsumerTerm.settingsPrivacyTitle: 'Privacy & consent',
    ConsumerTerm.settingsPrivacyDescription:
        'CLARA only processes health information you provide and requires versioned consent before it provides medical content. You can review and manage consent in Privacy & consent under More.',
    ConsumerTerm.settingsTransparencyTitle: 'AI transparency',
    ConsumerTerm.settingsAiModelLabel: 'AI model',
    ConsumerTerm.settingsAiModelGovernedRoute:
        'DeepSeek V4 Pro / Flash — selected for each task',
    ConsumerTerm.settingsAboutTitle: 'About',
    ConsumerTerm.settingsVersion: 'Version {version}',
    ConsumerTerm.settingsAboutDescription:
        'CLARA is an AI health assistant for decision support. CLARA is not a doctor and does not replace professional medical advice, diagnosis, or treatment. In an emergency, call your local emergency service immediately.',
    ConsumerTerm.settingsHelpTitle: 'Help',
    ConsumerTerm.settingsHelpDescription:
        'Need help? Read the in-app guide or contact the CLARA team for support.',
  };
}
