// Server-backed first-run onboarding for CLARA_Mobile (clara-mobile-unified,
// Requirement 6).
//
// Unlike the legacy client-only "seen" carousel, this gate is backed by the
// durable PHR onboarding state (`GET/PATCH /api/v1/phr/onboarding`), so the
// first-run decision matches the web `/welcome` flow and is consistent across
// devices. It applies to EVERY role (Req 6.4).
//
// Flow:
//   * [UnifiedOnboardingGate] loads `getPhrOnboarding` once. While loading it
//     shows a minimal splash. On `needs_onboarding == false` (or any load
//     failure — fail-open so the user is never stranded) it renders [child].
//     Otherwise it renders [OnboardingFlow].
//   * [OnboardingFlow] is a 3-step, all-optional flow (welcome → basics →
//     personalization consent) that completes or skips via
//     `PATCH /phr/onboarding`. No health fact is required; nothing is inferred.
//
// Safety: this collects only self-declared, optional profile basics and an
// explicit personalization-consent choice. It never presents medical advice.

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/session_store.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/tokens.dart';

/// Loads the durable onboarding decision and either renders [child] or the
/// first-run [OnboardingFlow]. Fail-open: a load error renders [child].
class UnifiedOnboardingGate extends StatefulWidget {
  const UnifiedOnboardingGate({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.child,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final Widget child;

  @override
  State<UnifiedOnboardingGate> createState() => _UnifiedOnboardingGateState();
}

class _UnifiedOnboardingGateState extends State<UnifiedOnboardingGate> {
  /// `null` while loading; `true` ⇒ show onboarding; `false` ⇒ show [child].
  bool? _needsOnboarding;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      if (mounted) setState(() => _needsOnboarding = false);
      return;
    }
    try {
      final data = await widget.apiClient.getPhrOnboarding(accessToken: token);
      if (!mounted) return;
      setState(() => _needsOnboarding = data['needs_onboarding'] == true);
    } catch (_) {
      // Fail-open: never strand the user behind a flaky onboarding read.
      if (!mounted) return;
      setState(() => _needsOnboarding = false);
    }
  }

  void _onDone() {
    if (!mounted) return;
    setState(() => _needsOnboarding = false);
  }

  @override
  Widget build(BuildContext context) {
    final needs = _needsOnboarding;
    if (needs == null) {
      return const Scaffold(
        body: Center(
          key: Key('unified-onboarding-splash'),
          child: CircularProgressIndicator(),
        ),
      );
    }
    if (!needs) return widget.child;
    return OnboardingFlow(
      apiClient: widget.apiClient,
      sessionStore: widget.sessionStore,
      onDone: _onDone,
    );
  }
}

/// The 3-step, all-optional first-run flow. Completes/skips via
/// `PATCH /phr/onboarding`, then calls [onDone].
class OnboardingFlow extends StatefulWidget {
  const OnboardingFlow({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.onDone,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final VoidCallback onDone;

  @override
  State<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends State<OnboardingFlow> {
  int _step = 0;
  bool _saving = false;
  String? _error;
  bool _consent = false;

  final _fullName = TextEditingController();
  final _heightCm = TextEditingController();
  final _weightKg = TextEditingController();
  String _gender = '';
  String _bloodType = '';

  @override
  void dispose() {
    _fullName.dispose();
    _heightCm.dispose();
    _weightKg.dispose();
    super.dispose();
  }

  double? _numeric(String value) {
    final trimmed = value.trim().replaceAll(',', '.');
    if (trimmed.isEmpty) return null;
    return double.tryParse(trimmed);
  }

  Future<void> _finish({required bool skip}) async {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) {
      widget.onDone();
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final payload = skip
        ? <String, dynamic>{'action': 'skip'}
        : <String, dynamic>{
            'action': 'complete',
            'confirm_self_declared': true,
            'personalization_consent': _consent,
            'full_name': _fullName.text.trim(),
            'gender': _gender,
            'blood_type': _bloodType,
            'height_cm': _numeric(_heightCm.text),
            'weight_kg': _numeric(_weightKg.text),
          };
    try {
      await widget.apiClient
          .updatePhrOnboarding(accessToken: token, payload: payload);
      if (!mounted) return;
      widget.onDone();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Không thể lưu. Vui lòng thử lại.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(ClaraTokens.spaceLg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Stepper(step: _step),
                  const SizedBox(height: ClaraTokens.spaceLg),
                  if (_error != null) ...[
                    _ErrorBanner(message: _error!),
                    const SizedBox(height: ClaraTokens.spaceMd),
                  ],
                  if (_step == 0)
                    _WelcomeStep(
                      onStart: () => setState(() => _step = 1),
                      onSkip: _saving ? null : () => _finish(skip: true),
                    )
                  else if (_step == 1)
                    _BasicsStep(
                      fullName: _fullName,
                      heightCm: _heightCm,
                      weightKg: _weightKg,
                      gender: _gender,
                      bloodType: _bloodType,
                      onGender: (v) => setState(() => _gender = v),
                      onBloodType: (v) => setState(() => _bloodType = v),
                      onBack: () => setState(() => _step = 0),
                      onNext: () => setState(() => _step = 2),
                    )
                  else
                    _ConsentStep(
                      consent: _consent,
                      onConsent: (v) => setState(() => _consent = v),
                      saving: _saving,
                      onBack: () => setState(() => _step = 1),
                      onComplete: () => _finish(skip: false),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({required this.step});
  final int step;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    const labels = ['Chào mừng', 'Thông tin cơ bản', 'Cá nhân hoá'];
    return Row(
      children: [
        for (var i = 0; i < labels.length; i++) ...[
          CircleAvatar(
            radius: 14,
            backgroundColor: i <= step
                ? scheme.primary
                : scheme.surfaceContainerHighest,
            child: i < step
                ? Icon(Icons.check, size: 16, color: scheme.onPrimary)
                : Text(
                    '${i + 1}',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: i <= step ? scheme.onPrimary : scheme.onSurfaceVariant,
                    ),
                  ),
          ),
          if (i < labels.length - 1)
            Expanded(
              child: Container(
                height: 2,
                margin: const EdgeInsets.symmetric(horizontal: 6),
                color: i < step ? scheme.primary : scheme.surfaceContainerHighest,
              ),
            ),
        ],
      ],
    );
  }
}

class _WelcomeStep extends StatelessWidget {
  const _WelcomeStep({required this.onStart, required this.onSkip});
  final VoidCallback onStart;
  final VoidCallback? onSkip;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Chào mừng bạn đến với CLARA', style: text.headlineSmall),
        const SizedBox(height: ClaraTokens.spaceMd),
        Text(
          'CLARA là trợ lý sức khoẻ đồng hành cùng bạn theo thời gian — ghi nhớ, '
          'nhắc nhở và giúp bạn chuẩn bị tốt hơn cho mỗi lần khám. CLARA không '
          'thay thế bác sĩ và luôn để bạn nắm quyền kiểm soát dữ liệu của mình.',
          style: text.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton(label: 'Bắt đầu', onPressed: onStart),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraButton(
          label: 'Bỏ qua, để sau',
          variant: ClaraButtonVariant.secondary,
          onPressed: onSkip,
        ),
      ],
    );
  }
}

class _BasicsStep extends StatelessWidget {
  const _BasicsStep({
    required this.fullName,
    required this.heightCm,
    required this.weightKg,
    required this.gender,
    required this.bloodType,
    required this.onGender,
    required this.onBloodType,
    required this.onBack,
    required this.onNext,
  });

  final TextEditingController fullName;
  final TextEditingController heightCm;
  final TextEditingController weightKg;
  final String gender;
  final String bloodType;
  final ValueChanged<String> onGender;
  final ValueChanged<String> onBloodType;
  final VoidCallback onBack;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Một vài thông tin cơ bản', style: text.headlineSmall),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          'Tất cả đều không bắt buộc. Bạn có thể bỏ trống và cập nhật bất cứ '
          'lúc nào trong Hồ sơ.',
          style: text.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        TextField(
          controller: fullName,
          decoration: const InputDecoration(
            labelText: 'Tên hiển thị (không bắt buộc)',
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        DropdownButtonFormField<String>(
          initialValue: gender.isEmpty ? '' : gender,
          decoration: const InputDecoration(labelText: 'Giới tính'),
          items: const [
            DropdownMenuItem(value: '', child: Text('Không muốn nói')),
            DropdownMenuItem(value: 'female', child: Text('Nữ')),
            DropdownMenuItem(value: 'male', child: Text('Nam')),
            DropdownMenuItem(value: 'other', child: Text('Khác')),
          ],
          onChanged: (v) => onGender(v ?? ''),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        DropdownButtonFormField<String>(
          initialValue: bloodType.isEmpty ? '' : bloodType,
          decoration: const InputDecoration(labelText: 'Nhóm máu'),
          items: const [
            DropdownMenuItem(value: '', child: Text('Chưa rõ')),
            DropdownMenuItem(value: 'A', child: Text('A')),
            DropdownMenuItem(value: 'B', child: Text('B')),
            DropdownMenuItem(value: 'AB', child: Text('AB')),
            DropdownMenuItem(value: 'O', child: Text('O')),
          ],
          onChanged: (v) => onBloodType(v ?? ''),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: heightCm,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Chiều cao (cm)'),
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceMd),
            Expanded(
              child: TextField(
                controller: weightKg,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Cân nặng (kg)'),
              ),
            ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton(label: 'Tiếp tục', onPressed: onNext),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraButton(
          label: 'Quay lại',
          variant: ClaraButtonVariant.secondary,
          onPressed: onBack,
        ),
      ],
    );
  }
}

class _ConsentStep extends StatelessWidget {
  const _ConsentStep({
    required this.consent,
    required this.onConsent,
    required this.saving,
    required this.onBack,
    required this.onComplete,
  });

  final bool consent;
  final ValueChanged<bool> onConsent;
  final bool saving;
  final VoidCallback onBack;
  final VoidCallback onComplete;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Cá nhân hoá gợi ý cho bạn', style: text.headlineSmall),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          'Bạn có thể cho phép CLARA dùng hồ sơ của bạn để cá nhân hoá câu trả '
          'lời và cảnh báo an toàn. Bạn có thể thay đổi lựa chọn này bất cứ lúc nào.',
          style: text.bodyMedium,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),
        SwitchListTile(
          value: consent,
          onChanged: saving ? null : onConsent,
          title: const Text('Cho phép cá nhân hoá'),
          subtitle: const Text(
            'Dùng hồ sơ sức khoẻ để gợi ý phù hợp hơn. Không bắt buộc.',
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceXs),
        Text(
          'Thông tin bạn nhập là tự khai báo, không phải chẩn đoán y tế. CLARA '
          'hỗ trợ tham khảo và không thay thế tư vấn của bác sĩ.',
          style: text.bodySmall,
        ),
        const SizedBox(height: ClaraTokens.spaceLg),
        ClaraButton(
          label: 'Hoàn tất',
          loading: saving,
          onPressed: saving ? null : onComplete,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        ClaraButton(
          label: 'Quay lại',
          variant: ClaraButtonVariant.secondary,
          onPressed: saving ? null : onBack,
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(ClaraTokens.spaceMd),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: scheme.onErrorContainer, size: 20),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
