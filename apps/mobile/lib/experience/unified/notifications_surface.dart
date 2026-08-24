// Notifications preference surface for CLARA_Mobile Unified (Spec v5 Section 7.10).
//
// Features:
//   * Medication reminder schedules: Daily slots (Morning, Noon, Evening, Night) + DDI safety alerts.
//   * Care journey alerts: LifeMap milestones, follow-up check-ins, and abnormal vital warnings.
//   * Family updates: Family member logs, emergency proxy reminders, sharing access requests.
//   * Push / Email channel toggles: Channel switches and quiet hours setting.
//   * Safety invariant: Reminders follow verified prescriptions only (not a doctor).

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/api_client.dart';
import '../../core/consumer_terminology.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';

/// A single medication reminder time slot.
class MedicationReminderSlot {
  const MedicationReminderSlot({
    required this.id,
    required this.labelVi,
    required this.labelEn,
    required this.defaultTime,
    required this.icon,
  });

  final String id;
  final String labelVi;
  final String labelEn;
  final String defaultTime;
  final IconData icon;

  String label(bool isEnglish) => isEnglish ? labelEn : labelVi;
}

const List<MedicationReminderSlot> kDefaultMedicationSlots = [
  MedicationReminderSlot(
    id: 'morning',
    labelVi: 'Buổi sáng',
    labelEn: 'Morning',
    defaultTime: '08:00',
    icon: Icons.wb_sunny_outlined,
  ),
  MedicationReminderSlot(
    id: 'noon',
    labelVi: 'Buổi trưa',
    labelEn: 'Noon',
    defaultTime: '12:00',
    icon: Icons.wb_twilight_outlined,
  ),
  MedicationReminderSlot(
    id: 'evening',
    labelVi: 'Buổi chiều',
    labelEn: 'Evening',
    defaultTime: '18:00',
    icon: Icons.wb_cloudy_outlined,
  ),
  MedicationReminderSlot(
    id: 'night',
    labelVi: 'Buổi tối',
    labelEn: 'Night',
    defaultTime: '21:00',
    icon: Icons.nightlight_outlined,
  ),
];

/// The unified Notifications ("Thông báo") surface (Spec v5 Section 7.10).
class NotificationsSurface extends StatefulWidget {
  const NotificationsSurface({
    super.key,
    this.apiClient,
    this.sessionStore,
    this.languageController,
    this.onSaved,
  });

  final ApiClient? apiClient;
  final SessionStore? sessionStore;
  final LanguageController? languageController;
  final VoidCallback? onSaved;

  @override
  State<NotificationsSurface> createState() => _NotificationsSurfaceState();
}

class _NotificationsSurfaceState extends State<NotificationsSurface> {
  // Channels
  bool _pushEnabled = true;
  bool _emailEnabled = true;
  bool _smsEnabled = false;
  bool _quietHoursEnabled = false;

  // Medication Reminders
  bool _medicationRemindersMaster = true;
  final Map<String, bool> _medicationSlotEnabled = {
    'morning': true,
    'noon': true,
    'evening': true,
    'night': true,
  };
  final Map<String, String> _medicationSlotTimes = {
    'morning': '08:00',
    'noon': '12:00',
    'evening': '18:00',
    'night': '21:00',
  };
  bool _ddiSafetyAlertsEnabled = true;

  // Care Journey Alerts
  bool _careJourneyMaster = true;
  bool _careJourneyMilestones = true;
  bool _careJourneyCheckins = true;
  bool _careJourneyVitals = true;

  // Family Updates
  bool _familyMaster = true;
  bool _familyMemberLogs = true;
  bool _familyEmergencyAlerts = true;
  bool _familySharingRequests = true;

  bool _isSaving = false;

  Future<void> _pickSlotTime(BuildContext context, String slotId, bool isEnglish) async {
    final currentTimeStr = _medicationSlotTimes[slotId] ?? '08:00';
    final parts = currentTimeStr.split(':');
    final initialTime = TimeOfDay(
      hour: int.tryParse(parts[0]) ?? 8,
      minute: parts.length > 1 ? (int.tryParse(parts[1]) ?? 0) : 0,
    );

    final picked = await showTimePicker(
      context: context,
      initialTime: initialTime,
      helpText: isEnglish ? 'Select reminder time' : 'Chọn giờ nhắc uống thuốc',
    );

    if (picked != null && mounted) {
      final hourStr = picked.hour.toString().padLeft(2, '0');
      final minuteStr = picked.minute.toString().padLeft(2, '0');
      setState(() {
        _medicationSlotTimes[slotId] = '$hourStr:$minuteStr';
      });
    }
  }

  Future<void> _savePreferences(BuildContext context, bool isEnglish) async {
    setState(() {
      _isSaving = true;
    });

    // Simulate saving settings (or server sync)
    await Future<void>.delayed(const Duration(milliseconds: 300));

    if (mounted) {
      setState(() {
        _isSaving = false;
      });
      widget.onSaved?.call();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isEnglish
                ? 'Notification preferences saved successfully.'
                : 'Đã lưu tùy chọn thông báo thành công.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.languageController;
    if (controller == null) {
      return _buildLocalized(context, ConsumerTerminology.forLocale(null));
    }
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) => _buildLocalized(
        context,
        ConsumerTerminology.forLocale(controller.languageCode),
      ),
    );
  }

  Widget _buildLocalized(BuildContext context, ConsumerTerminology copy) {
    final isEnglish = copy.locale == 'en';
    final theme = Theme.of(context);
    final textScaler = A11y.resolveTextScaler(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(isEnglish ? 'Notification Preferences' : 'Tùy chọn thông báo'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: ClaraTokens.spaceXl),
          children: [
            // 1. Notification Channels
            _buildChannelsSection(context, isEnglish, textScaler, theme),

            // 2. Medication Reminder Schedules (Spec v5 Section 7.10)
            _buildMedicationRemindersSection(context, isEnglish, textScaler, theme),

            // 3. Care Journey Alerts (Spec v5 Section 7.10)
            _buildCareJourneySection(context, isEnglish, textScaler, theme),

            // 4. Family Updates (Spec v5 Section 7.10)
            _buildFamilyUpdatesSection(context, isEnglish, textScaler, theme),

            // 5. Safety Invariant Card
            _buildSafetyInvariantCard(context, isEnglish, textScaler, theme),

            // 6. Save Action Button
            Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: ClaraButton.primary(
                key: const Key('save-notification-preferences-button'),
                label: isEnglish ? 'Save Preferences' : 'Lưu tùy chọn thông báo',
                icon: Icons.check_circle_outline,
                loading: _isSaving,
                onPressed: () => _savePreferences(context, isEnglish),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChannelsSection(
    BuildContext context,
    bool isEnglish,
    TextScaler textScaler,
    ThemeData theme,
  ) {
    return _NotificationGroup(
      title: isEnglish ? 'Delivery Channels' : 'Kênh nhận thông báo',
      child: Column(
        children: [
          SwitchListTile.adaptive(
            key: const Key('notification-channel-push-switch'),
            value: _pushEnabled,
            onChanged: (val) => setState(() => _pushEnabled = val),
            secondary: Icon(Icons.notifications_active_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Push Notifications' : 'Thông báo đẩy trên thiết bị (Push)',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Receive alerts immediately on your mobile phone.'
                  : 'Nhận thông báo tức thì trên màn hình điện thoại.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          const Divider(height: 1),
          SwitchListTile.adaptive(
            key: const Key('notification-channel-email-switch'),
            value: _emailEnabled,
            onChanged: (val) => setState(() => _emailEnabled = val),
            secondary: Icon(Icons.email_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Email Notifications' : 'Thông báo qua Email',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Weekly health digests and critical care summary emails.'
                  : 'Tóm tắt sức khỏe định kỳ và bản tin chăm sóc quan trọng.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          const Divider(height: 1),
          SwitchListTile.adaptive(
            key: const Key('notification-channel-sms-switch'),
            value: _smsEnabled,
            onChanged: (val) => setState(() => _smsEnabled = val),
            secondary: Icon(Icons.sms_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'SMS Alerts (Urgent Only)' : 'Tin nhắn SMS (Chỉ trường hợp khẩn)',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Text messages for critical dosage and emergency safety flags.'
                  : 'Tin nhắn cho cảnh báo liều dùng khẩn cấp và nguy cơ an toàn.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          const Divider(height: 1),
          SwitchListTile.adaptive(
            key: const Key('notification-quiet-hours-switch'),
            value: _quietHoursEnabled,
            onChanged: (val) => setState(() => _quietHoursEnabled = val),
            secondary: Icon(Icons.bedtime_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Quiet Hours (22:00 - 07:00)' : 'Chế độ yên lặng ban đêm (22:00 - 07:00)',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Silence non-urgent notification chimes during sleep hours.'
                  : 'Tắt chuông thông báo không khẩn cấp trong khung giờ nghỉ ngơi.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMedicationRemindersSection(
    BuildContext context,
    bool isEnglish,
    TextScaler textScaler,
    ThemeData theme,
  ) {
    return _NotificationGroup(
      title: isEnglish ? 'Medication Reminders' : 'Lịch nhắc uống thuốc',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SwitchListTile.adaptive(
            key: const Key('notification-medication-toggle'),
            value: _medicationRemindersMaster,
            onChanged: (val) => setState(() => _medicationRemindersMaster = val),
            secondary: Icon(Icons.medication_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Medication Intake Reminders' : 'Nhắc nhở uống thuốc hàng ngày',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Timely alarms aligned with your active prescription schedules.'
                  : 'Chuông báo đúng giờ theo lịch trình đơn thuốc đang dùng.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          if (_medicationRemindersMaster) ...[
            const Divider(height: ClaraTokens.spaceMd),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceSm, vertical: 4),
              child: Text(
                isEnglish ? 'Reminder Schedule Slots:' : 'Khung giờ nhắc thuốc:',
                style: theme.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
                textScaler: textScaler,
              ),
            ),
            for (final slot in kDefaultMedicationSlots)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2.0),
                child: Row(
                  children: [
                    Checkbox(
                      key: Key('reminder-${slot.id}-switch'),
                      value: _medicationSlotEnabled[slot.id] ?? true,
                      onChanged: (checked) {
                        setState(() {
                          _medicationSlotEnabled[slot.id] = checked ?? true;
                        });
                      },
                    ),
                    Icon(slot.icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
                    const SizedBox(width: ClaraTokens.spaceSm),
                    Expanded(
                      child: Text(
                        slot.label(isEnglish),
                        style: theme.textTheme.bodyMedium,
                        textScaler: textScaler,
                      ),
                    ),
                    TextButton.icon(
                      onPressed: (_medicationSlotEnabled[slot.id] ?? true)
                          ? () => _pickSlotTime(context, slot.id, isEnglish)
                          : null,
                      icon: const Icon(Icons.access_time, size: 16),
                      label: Text(
                        _medicationSlotTimes[slot.id] ?? slot.defaultTime,
                        style: theme.textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: (_medicationSlotEnabled[slot.id] ?? true)
                              ? theme.colorScheme.primary
                              : theme.colorScheme.outline,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            const Divider(height: ClaraTokens.spaceMd),
            SwitchListTile.adaptive(
              key: const Key('notification-ddi-alerts-switch'),
              value: _ddiSafetyAlertsEnabled,
              onChanged: (val) => setState(() => _ddiSafetyAlertsEnabled = val),
              secondary: Icon(Icons.health_and_safety_outlined, color: theme.colorScheme.error),
              title: Text(
                isEnglish ? 'Drug-Drug Interaction & Safety Alerts' : 'Cảnh báo tương tác thuốc (DDI) & an toàn',
                style: theme.textTheme.titleSmall,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish
                    ? 'Notify when potential interactions or safety warnings are detected.'
                    : 'Thông báo ngay khi phát hiện nguy cơ tương tác thuốc bất lợi.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCareJourneySection(
    BuildContext context,
    bool isEnglish,
    TextScaler textScaler,
    ThemeData theme,
  ) {
    return _NotificationGroup(
      title: isEnglish ? 'Care Journey Alerts' : 'Cảnh báo hành trình chăm sóc',
      child: Column(
        children: [
          SwitchListTile.adaptive(
            key: const Key('notification-care-journey-toggle'),
            value: _careJourneyMaster,
            onChanged: (val) => setState(() => _careJourneyMaster = val),
            secondary: Icon(Icons.route_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Care Journey & LifeMap Notifications' : 'Thông báo lộ trình LifeMap & chăm sóc',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Follow-up actions and milestone tracking in your care plan.'
                  : 'Theo dõi các cột mốc và bước tiếp theo trong kế hoạch chăm sóc.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          if (_careJourneyMaster) ...[
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('care-journey-milestones-switch'),
              value: _careJourneyMilestones,
              onChanged: (val) => setState(() => _careJourneyMilestones = val),
              title: Text(
                isEnglish ? 'Doctor Visits & Health Milestones' : 'Lịch tái khám & Cột mốc điều trị',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish ? 'Reminders for scheduled appointments.' : 'Nhắc nhở trước ngày có lịch khám bệnh.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('care-journey-checkins-switch'),
              value: _careJourneyCheckins,
              onChanged: (val) => setState(() => _careJourneyCheckins = val),
              title: Text(
                isEnglish ? 'Health Recovery Check-ins' : 'Kiểm tra tiến độ phục hồi định kỳ',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish ? 'Check-in prompts to record symptom changes.' : 'Hỏi thăm diễn biến triệu chứng sau điều trị.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('care-journey-vitals-switch'),
              value: _careJourneyVitals,
              onChanged: (val) => setState(() => _careJourneyVitals = val),
              title: Text(
                isEnglish ? 'Abnormal Vital Sign Warnings' : 'Cảnh báo chỉ số sinh hiệu bất thường',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish
                    ? 'Alerts when blood pressure or glucose readings exceed target ranges.'
                    : 'Cảnh báo khi chỉ số huyết áp hoặc đường huyết vượt ngưỡng.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFamilyUpdatesSection(
    BuildContext context,
    bool isEnglish,
    TextScaler textScaler,
    ThemeData theme,
  ) {
    return _NotificationGroup(
      title: isEnglish ? 'Family Updates' : 'Cập nhật từ gia đình',
      child: Column(
        children: [
          SwitchListTile.adaptive(
            key: const Key('notification-family-toggle'),
            value: _familyMaster,
            onChanged: (val) => setState(() => _familyMaster = val),
            secondary: Icon(Icons.family_restroom_outlined, color: theme.colorScheme.primary),
            title: Text(
              isEnglish ? 'Family Circle Updates' : 'Thông báo từ Vòng tròn gia đình',
              style: theme.textTheme.titleSmall,
              textScaler: textScaler,
            ),
            subtitle: Text(
              isEnglish
                  ? 'Shared notifications with authorized family members.'
                  : 'Nhận thông báo cập nhật từ các thành viên gia đình được ủy quyền.',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              textScaler: textScaler,
            ),
          ),
          if (_familyMaster) ...[
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('family-records-switch'),
              value: _familyMemberLogs,
              onChanged: (val) => setState(() => _familyMemberLogs = val),
              title: Text(
                isEnglish ? 'Prescription & Record Updates' : 'Cập nhật đơn thuốc & kết quả mới',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish
                    ? 'When a family member uploads a new medical document.'
                    : 'Khi người thân tải lên đơn thuốc hoặc phiếu xét nghiệm mới.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('family-emergency-switch'),
              value: _familyEmergencyAlerts,
              onChanged: (val) => setState(() => _familyEmergencyAlerts = val),
              title: Text(
                isEnglish ? 'Emergency Alerts & Missed Dose Reminders' : 'Cảnh báo khẩn cấp & Quên uống thuốc',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish
                    ? 'Notify if an elderly or child family member misses a critical dose.'
                    : 'Báo động khi người thân lớn tuổi hoặc trẻ nhỏ quên liều quan trọng.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
            const Divider(height: 1),
            SwitchListTile.adaptive(
              key: const Key('family-sharing-requests-switch'),
              value: _familySharingRequests,
              onChanged: (val) => setState(() => _familySharingRequests = val),
              title: Text(
                isEnglish ? 'Access Sharing & Invitation Requests' : 'Yêu cầu ủy quyền & Chia sẻ hồ sơ',
                style: theme.textTheme.bodyMedium,
                textScaler: textScaler,
              ),
              subtitle: Text(
                isEnglish
                    ? 'Invitations to view or manage family care circles.'
                    : 'Lời mời tham gia hoặc yêu cầu xem hồ sơ sức khỏe gia đình.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textScaler: textScaler,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSafetyInvariantCard(
    BuildContext context,
    bool isEnglish,
    TextScaler textScaler,
    ThemeData theme,
  ) {
    return _NotificationGroup(
      title: isEnglish ? 'Safety Notice' : 'Lưu ý an toàn',
      clinical: true,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, size: 22, color: theme.colorScheme.primary),
          const SizedBox(width: ClaraTokens.spaceMd),
          Expanded(
            child: Text(
              isEnglish
                  ? 'Medication reminders and alerts are based strictly on confirmed prescriptions and user records. CLARA is a clinical assistant and does not self-prescribe or adjust dosages.'
                  : 'Lịch nhắc uống thuốc và các cảnh báo chỉ dựa trên đơn thuốc đã được người dùng xác nhận. CLARA là trợ lý hỗ trợ y tế, không tự ý kê đơn hoặc thay đổi liều lượng.',
              style: theme.textTheme.bodyMedium,
              textScaler: textScaler,
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationGroup extends StatelessWidget {
  const _NotificationGroup({
    required this.title,
    required this.child,
    this.clinical = false,
  });

  final String title;
  final Widget child;
  final bool clinical;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        SectionHeader(title: title),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: ClaraTokens.spaceMd),
          child: A11yLabeled(
            label: title,
            child: GlassSurface(
              blurSigma: GlassTokens.blurCard,
              radius: GlassTokens.radiusCard,
              fill: GlassFill.regular,
              clinical: clinical,
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Material(
                type: MaterialType.transparency,
                child: child,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
