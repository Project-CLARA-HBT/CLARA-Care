import 'package:flutter/material.dart';

/// Modal bottom sheet providing statutory consent rights explanations
/// under Decree 13/2023/ND-CP (PDPD Vietnam) and Medical AI safety standards.
class ConsentExplanationSheet extends StatelessWidget {
  const ConsentExplanationSheet({
    super.key,
    required this.purposeTitle,
    required this.purposeKey,
    required this.isEnglish,
  });

  final String purposeTitle;
  final String purposeKey;
  final bool isEnglish;

  static Future<void> show(
    BuildContext context, {
    required String purposeTitle,
    required String purposeKey,
    bool isEnglish = false,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => ConsentExplanationSheet(
        purposeTitle: purposeTitle,
        purposeKey: purposeKey,
        isEnglish: isEnglish,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              purposeTitle,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              _explanationText(purposeKey, isEnglish),
              style: theme.textTheme.bodyMedium?.copyWith(
                height: 1.5,
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.security,
                    size: 20,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      isEnglish
                          ? 'You can withdraw this consent at any time without affecting past care.'
                          : 'Bạn có thể rút lại sự đồng ý bất kỳ lúc nào mà không ảnh hưởng chăm sóc trước đó.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(isEnglish ? 'Understood' : 'Đã hiểu'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _explanationText(String key, bool english) {
    switch (key) {
      case 'core_service':
        return english
            ? 'Required to store your profile, health notes, and facilitate doctor consultations.'
            : 'Cần thiết để lưu hồ sơ cá nhân, ghi chú sức khỏe và hỗ trợ tham vấn bác sĩ.';
      case 'ai_transparency':
        return english
            ? 'Explains that CLARA uses AI language models as an assistant, requiring medical supervision.'
            : 'Làm rõ rằng CLARA sử dụng mô hình trí tuệ nhân tạo như một trợ lý và cần sự giám sát của y bác sĩ.';
      case 'research':
        return english
            ? 'Anonymized de-identified data used to improve medical evidence synthesis.'
            : 'Dữ liệu được ẩn danh hoàn toàn để phục vụ nghiên cứu và nâng cao chất lượng bằng chứng y khoa.';
      case 'cross_border_processing':
        return english
            ? 'Encrypted prompt processing with international AI inference providers strictly under PDPD safeguards.'
            : 'Xử lý câu lệnh mã hóa với nhà cung cấp suy luận AI quốc tế theo đúng chuẩn bảo vệ dữ liệu PDPD.';
      case 'sharing':
        return english
            ? 'Enables sharing selected health dossiers with family members or designated clinicians.'
            : 'Cho phép chia sẻ hồ sơ sức khỏe đã chọn với người thân hoặc bác sĩ được chỉ định.';
      default:
        return english
            ? 'Consent for data processing under Vietnam Personal Data Protection Decree.'
            : 'Đồng ý xử lý dữ liệu theo Nghị định Bảo vệ Dữ liệu Cá nhân Việt Nam.';
    }
  }
}
