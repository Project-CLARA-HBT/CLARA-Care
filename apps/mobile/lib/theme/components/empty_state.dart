import 'package:flutter/material.dart';
import '../generated/clara_tokens.g.dart';
import '../tokens.dart';

class ClaraEmptyState extends StatelessWidget {
  const ClaraEmptyState({
    super.key,
    required this.title,
    required this.description,
    this.icon,
    this.primaryActionLabel,
    this.onPrimaryAction,
    this.secondaryActionLabel,
    this.onSecondaryAction,
  });

  final String title;
  final String description;
  final Widget? icon;
  final String? primaryActionLabel;
  final VoidCallback? onPrimaryAction;
  final String? secondaryActionLabel;
  final VoidCallback? onSecondaryAction;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(ClaraTokens.spaceLg),
        child: Container(
          padding: const EdgeInsets.all(ClaraTokens.spaceLg),
          decoration: BoxDecoration(
            color: isDark ? ClaraGeneratedTokens.darkSurface1 : ClaraGeneratedTokens.lightSurface0,
            borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
            border: Border.all(
              color: isDark ? ClaraGeneratedTokens.darkBorderSubtle : ClaraGeneratedTokens.lightBorderSubtle,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Container(
                  width: 56,
                  height: 56,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: isDark ? ClaraGeneratedTokens.darkSurface2 : ClaraGeneratedTokens.brand50,
                    borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                  ),
                  child: icon,
                ),
                const SizedBox(height: ClaraTokens.spaceMd),
              ],
              Text(
                title,
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: isDark ? ClaraGeneratedTokens.darkTextPrimary : ClaraGeneratedTokens.lightTextPrimary,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                description,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: isDark ? ClaraGeneratedTokens.darkTextSecondary : ClaraGeneratedTokens.lightTextSecondary,
                ),
              ),
              if (primaryActionLabel != null || secondaryActionLabel != null) ...[
                const SizedBox(height: ClaraTokens.spaceLg),
                Wrap(
                  spacing: ClaraTokens.spaceSm,
                  runSpacing: ClaraTokens.spaceSm,
                  alignment: WrapAlignment.center,
                  children: [
                    if (primaryActionLabel != null)
                      FilledButton(
                        onPressed: onPrimaryAction,
                        style: FilledButton.styleFrom(
                          backgroundColor: ClaraGeneratedTokens.brand600,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                          ),
                        ),
                        child: Text(primaryActionLabel!),
                      ),
                    if (secondaryActionLabel != null)
                      OutlinedButton(
                        onPressed: onSecondaryAction,
                        style: OutlinedButton.styleFrom(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                          ),
                        ),
                        child: Text(secondaryActionLabel!),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
