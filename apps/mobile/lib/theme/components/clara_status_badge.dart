import 'package:flutter/material.dart';
import '../generated/clara_tokens.g.dart';
import '../tokens.dart';

enum ClaraStatusTone { success, warning, danger, info, unknown }

class ClaraStatusBadge extends StatelessWidget {
  const ClaraStatusBadge({
    super.key,
    required this.label,
    this.tone = ClaraStatusTone.info,
    this.icon,
  });

  final String label;
  final ClaraStatusTone tone;
  final Widget? icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    Color bg;
    Color border;
    Color text;

    switch (tone) {
      case ClaraStatusTone.success:
        bg = isDark ? ClaraGeneratedTokens.darkStatusSuccessBg : ClaraGeneratedTokens.lightStatusSuccessBg;
        border = isDark ? ClaraGeneratedTokens.darkStatusSuccessBorder : ClaraGeneratedTokens.lightStatusSuccessBorder;
        text = isDark ? ClaraGeneratedTokens.darkStatusSuccessText : ClaraGeneratedTokens.lightStatusSuccessText;
        break;
      case ClaraStatusTone.warning:
        bg = isDark ? ClaraGeneratedTokens.darkStatusWarningBg : ClaraGeneratedTokens.lightStatusWarningBg;
        border = isDark ? ClaraGeneratedTokens.darkStatusWarningBorder : ClaraGeneratedTokens.lightStatusWarningBorder;
        text = isDark ? ClaraGeneratedTokens.darkStatusWarningText : ClaraGeneratedTokens.lightStatusWarningText;
        break;
      case ClaraStatusTone.danger:
        bg = isDark ? ClaraGeneratedTokens.darkStatusDangerBg : ClaraGeneratedTokens.lightStatusDangerBg;
        border = isDark ? ClaraGeneratedTokens.darkStatusDangerBorder : ClaraGeneratedTokens.lightStatusDangerBorder;
        text = isDark ? ClaraGeneratedTokens.darkStatusDangerText : ClaraGeneratedTokens.lightStatusDangerText;
        break;
      case ClaraStatusTone.info:
        bg = isDark ? ClaraGeneratedTokens.darkStatusInfoBg : ClaraGeneratedTokens.lightStatusInfoBg;
        border = isDark ? ClaraGeneratedTokens.darkStatusInfoBorder : ClaraGeneratedTokens.lightStatusInfoBorder;
        text = isDark ? ClaraGeneratedTokens.darkStatusInfoText : ClaraGeneratedTokens.lightStatusInfoText;
        break;
      case ClaraStatusTone.unknown:
        bg = isDark ? ClaraGeneratedTokens.darkStatusUnknownBg : ClaraGeneratedTokens.lightStatusUnknownBg;
        border = isDark ? ClaraGeneratedTokens.darkStatusUnknownBorder : ClaraGeneratedTokens.lightStatusUnknownBorder;
        text = isDark ? ClaraGeneratedTokens.darkStatusUnknownText : ClaraGeneratedTokens.lightStatusUnknownText;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusPill),
        border: Border.all(color: border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            icon!,
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: theme.textTheme.labelSmall?.copyWith(
              color: text,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
