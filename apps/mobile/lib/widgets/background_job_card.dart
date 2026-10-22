import 'package:flutter/material.dart';

/// Job processing state representation for background mobile tasks.
enum BackgroundJobState {
  queued,
  running,
  succeeded,
  failed,
}

class BackgroundJobCard extends StatelessWidget {
  const BackgroundJobCard({
    super.key,
    required this.jobTitle,
    required this.jobState,
    this.progress = 0.0,
    this.errorMessage,
    this.onRetry,
  });

  final String jobTitle;
  final BackgroundJobState jobState;
  final double progress;
  final String? errorMessage;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    jobTitle,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                _statusBadge(context),
              ],
            ),
            if (jobState == BackgroundJobState.running) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: progress > 0 ? progress : null,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
            if (errorMessage != null && errorMessage!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                errorMessage!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            if (jobState == BackgroundJobState.failed && onRetry != null) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Thử lại'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _statusBadge(BuildContext context) {
    final theme = Theme.of(context);
    switch (jobState) {
      case BackgroundJobState.queued:
        return Text('Đang chờ', style: TextStyle(color: theme.colorScheme.onSurfaceVariant));
      case BackgroundJobState.running:
        return Text('Đang xử lý', style: TextStyle(color: theme.colorScheme.primary));
      case BackgroundJobState.succeeded:
        return const Text('Hoàn tất', style: TextStyle(color: Colors.green));
      case BackgroundJobState.failed:
        return Text('Thất bại', style: TextStyle(color: theme.colorScheme.error));
    }
  }
}
