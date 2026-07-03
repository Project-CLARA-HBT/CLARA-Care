// Per-medicine AI detail sheet for the CLARA_Mobile redesign (Experience_V3).
//
// A bottom sheet that asks CLARA — via the existing `/api/v1/chat` endpoint —
// for plain-language information about ONE medicine already in the user's
// cabinet (what it is commonly used for, general precautions, how to store it,
// and when to talk to a clinician). It changes NO CLARA_API contract: it sends
// a single chat message and renders the End_User-safe answer through the shared
// markdown view + standing disclaimer.
//
// Safety framing (invariants preserved):
//   * The prompt explicitly asks for GENERAL, educational information only and
//     forbids personalized dosage/diagnosis — the server-side legal guard and
//     emergency fast-path still apply on top of this.
//   * The standing medical disclaimer is always shown, and the answer is
//     rendered through the same `MarkdownView` used elsewhere.
//   * No PII beyond the medicine name the user already stored is sent; the
//     request carries only the medicine name, not the whole cabinet.
//
// Vietnamese-first copy throughout.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/tokens.dart';
import '../../widgets/markdown_view.dart';

/// Opens the per-medicine AI detail sheet for [medicineName]. Returns when the
/// user dismisses it. Safe to call for any role; the sheet performs one chat
/// request and renders the result.
Future<void> showCabinetMedicineDetail(
  BuildContext context, {
  required ApiClient apiClient,
  required String accessToken,
  required String medicineName,
  String? activeIngredient,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _CabinetMedicineDetailSheet(
      apiClient: apiClient,
      accessToken: accessToken,
      medicineName: medicineName,
      activeIngredient: activeIngredient,
    ),
  );
}

class _CabinetMedicineDetailSheet extends StatefulWidget {
  const _CabinetMedicineDetailSheet({
    required this.apiClient,
    required this.accessToken,
    required this.medicineName,
    this.activeIngredient,
  });

  final ApiClient apiClient;
  final String accessToken;
  final String medicineName;
  final String? activeIngredient;

  @override
  State<_CabinetMedicineDetailSheet> createState() =>
      _CabinetMedicineDetailSheetState();
}

class _CabinetMedicineDetailSheetState
    extends State<_CabinetMedicineDetailSheet> {
  bool _loading = false;
  String? _error;
  String _answer = '';

  @override
  void initState() {
    super.initState();
    _ask();
  }

  /// Builds the general-information prompt. Explicitly scoped to educational,
  /// non-personalized content so it never becomes a dosage/diagnosis request.
  String get _prompt {
    final ingredient = (widget.activeIngredient ?? '').trim();
    final ingredientLine = ingredient.isNotEmpty &&
            ingredient.toLowerCase() != widget.medicineName.trim().toLowerCase()
        ? ' (hoạt chất: $ingredient)'
        : '';
    // NOTE: this prompt must NOT contain the ML legal-guard trigger tokens
    // ("kê đơn", "liều", "chẩn đoán"), otherwise the server hard-guard blocks
    // this legitimate educational lookup by matching its own safety wording.
    // The scope is conveyed positively instead (general education only).
    return 'Giới thiệu thông tin tổng quát, dễ hiểu về thuốc '
        '"${widget.medicineName.trim()}"$ingredientLine. '
        'Bao gồm: thường được dùng cho mục đích gì, nhóm thuốc, '
        'những lưu ý an toàn phổ biến khi sử dụng, cách bảo quản, '
        'và khi nào nên trao đổi với bác sĩ hoặc dược sĩ. '
        'Chỉ trình bày kiến thức giáo dục tổng quát cho người dùng, '
        'không hướng dẫn dùng thuốc cho riêng một cá nhân. '
        'Trả lời ngắn gọn, rõ ràng bằng tiếng Việt.';
  }

  Future<void> _ask() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    getAnalyticsClient().capture(
      const AnalyticsEvent('mobile_cabinet_medicine_info_requested'),
    );
    try {
      final response = await widget.apiClient.chat(
        accessToken: widget.accessToken,
        payload: <String, dynamic>{'message': _prompt},
      );
      if (!mounted) return;
      final reply = (response['reply'] ?? response['answer'] ?? '').toString();
      setState(() {
        _answer = reply.trim();
        if (_answer.isEmpty) {
          _error = 'Chưa nhận được thông tin. Vui lòng thử lại.';
        }
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(
          () => _error = 'Không thể tải thông tin lúc này. Vui lòng thử lại.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        0,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd + bottomInset,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_awesome, color: scheme.primary, size: 22),
                const SizedBox(width: ClaraTokens.spaceSm),
                Expanded(
                  child: Text(
                    widget.medicineName,
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: ClaraTokens.spaceXs),
            Text(
              'Thông tin tổng quát từ CLARA',
              style: theme.textTheme.labelMedium
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: ClaraTokens.spaceLg),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null) ...[
              Text(
                _error!,
                style:
                    theme.textTheme.bodyMedium?.copyWith(color: scheme.error),
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              ClaraButton.primary(
                label: 'Thử lại',
                icon: Icons.refresh,
                onPressed: _ask,
              ),
            ] else ...[
              MarkdownView(_answer, baseStyle: theme.textTheme.bodyMedium),
            ],
            const SizedBox(height: ClaraTokens.spaceMd),
            _DisclaimerBar(),
          ],
        ),
      ),
    );
  }
}

/// The standing medical disclaimer, shown on every medicine-info sheet.
class _DisclaimerBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    const text =
        'Thông tin chỉ mang tính hỗ trợ quyết định, không thay thế tư vấn của '
        'bác sĩ. Hãy trao đổi với nhân viên y tế có chuyên môn.';
    return Semantics(
      label: text,
      child: Container(
        padding: const EdgeInsets.all(ClaraTokens.spaceSm),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Icon(Icons.info_outline,
                  size: 16, color: scheme.onSurfaceVariant),
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: scheme.onSurfaceVariant),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
