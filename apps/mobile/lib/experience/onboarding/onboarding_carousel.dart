// First-run onboarding carousel for CLARA_Mobile Experience_V2 (Req 5.1, 5.2, 5.4).
//
// A skippable, paged introduction that primes the user before any system
// permission prompt: what CLARA is (decision-support over self-declared data,
// **not** a medical device or EMR/EHR), how privacy/consent works (no PII is
// collected; consent is asked explicitly, never granted here), and the key
// features they can use. All copy is Vietnamese-first.
//
// Scope of THIS widget (task 5.1): pure UI + callbacks only.
//   * It does NOT persist the "onboarding seen" flag and does NOT emit
//     analytics — task 5.2 wires `OnboardingStore.markSeen()` and the no-PII
//     analytics event by passing the [onComplete] / [onSkip] callbacks.
//   * It calls [onSkip] when the user taps "Bỏ qua" (Skip) on any page, and
//     [onComplete] when the user taps "Bắt đầu" (Get started) on the last page.
//
// Accessibility (Req 5.4):
//   * Paging animation duration is resolved through
//     `A11y.resolveMotionDuration(context, ClaraTokens.motionMedium)`; under
//     reduced motion `animateToPage` collapses to `Duration.zero` (an instant
//     jump), so motion-sensitive users get no carousel animation.
//   * Every interactive control is wrapped with `MinTapTarget` (≥48dp) and
//     labeled via `A11yLabeled` / `Semantics` for screen readers.
//   * Labels honor the OS text-scaling preference via `A11y.resolveTextScaler`.
//   * The page indicator status is conveyed by a semantics value (e.g.
//     "Trang 1 trên 4"), not by color alone.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/components/clara_button.dart';
import '../../theme/tokens.dart';

/// Immutable content for a single onboarding page (Vietnamese-first).
///
/// Pure data: an [icon], a [title], and a [body]. Held as a `const` list in
/// [OnboardingCarousel.pages] so the intro content is a single source of truth
/// and trivially testable.
class OnboardingPage {
  const OnboardingPage({
    required this.icon,
    required this.title,
    required this.body,
  });

  /// Decorative leading icon for the page (excluded from semantics; the
  /// title/body carry the meaning).
  final IconData icon;

  /// Vietnamese-first page heading, announced as a region header.
  final String title;

  /// Vietnamese-first supporting copy, announced as the region value.
  final String body;
}

/// A skippable, paged first-run onboarding carousel (Req 5.1, 5.2, 5.4).
///
/// Renders [pages] in a [PageView] with a "Bỏ qua" (Skip) control always
/// visible, a dot page indicator reflecting the current page, and a
/// context-sensitive primary action: "Tiếp tục" (Next) on intermediate pages
/// and "Bắt đầu" (Get started) on the last page.
///
/// This widget is pure UI: it persists nothing and emits no analytics. It
/// invokes [onSkip] when skipped and [onComplete] when finished; the caller
/// (task 5.2) is responsible for `OnboardingStore.markSeen()` and analytics.
class OnboardingCarousel extends StatefulWidget {
  const OnboardingCarousel({
    super.key,
    required this.onComplete,
    required this.onSkip,
    this.pages = defaultPages,
  });

  /// Invoked once when the user reaches and confirms the final page via
  /// "Bắt đầu" (Get started). The caller persists "seen" and emits analytics.
  final VoidCallback onComplete;

  /// Invoked when the user taps "Bỏ qua" (Skip) on any page. The caller
  /// persists "seen" and emits analytics.
  final VoidCallback onSkip;

  /// The pages to show. Defaults to [defaultPages] (Vietnamese-first priming).
  final List<OnboardingPage> pages;

  /// Vietnamese-first priming pages: what CLARA does (decision-support, not a
  /// medical device), privacy/consent (no PII), and key features.
  static const List<OnboardingPage> defaultPages = <OnboardingPage>[
    OnboardingPage(
      icon: Icons.health_and_safety_outlined,
      title: 'Chào mừng đến với CLARA',
      body: 'CLARA là phần mềm hỗ trợ ra quyết định dựa trên thông tin bạn tự '
          'cung cấp. CLARA không phải thiết bị y tế và không thay thế chẩn '
          'đoán hay tư vấn của bác sĩ.',
    ),
    OnboardingPage(
      icon: Icons.privacy_tip_outlined,
      title: 'Quyền riêng tư là trên hết',
      body: 'Chúng tôi không thu thập thông tin định danh cá nhân của bạn cho '
          'mục đích phân tích. Trước khi cần bất kỳ quyền truy cập nào, CLARA '
          'sẽ giải thích lý do và chỉ hỏi khi bạn đồng ý.',
    ),
    OnboardingPage(
      icon: Icons.medical_information_outlined,
      title: 'Hồ sơ sức khỏe của bạn',
      body: 'Lưu trữ hồ sơ sức khỏe cá nhân và tra cứu thông tin một cách an '
          'toàn. Bạn toàn quyền kiểm soát dữ liệu của mình và có thể xem lại '
          'bất cứ lúc nào.',
    ),
    OnboardingPage(
      icon: Icons.rocket_launch_outlined,
      title: 'Sẵn sàng bắt đầu',
      body: 'Khám phá các công cụ hỗ trợ sức khỏe được thiết kế dễ dùng và dễ '
          'tiếp cận. Bạn có thể thay đổi ngôn ngữ và tùy chọn bất cứ lúc nào '
          'trong phần Cài đặt.',
    ),
  ];

  @override
  State<OnboardingCarousel> createState() => _OnboardingCarouselState();
}

class _OnboardingCarouselState extends State<OnboardingCarousel> {
  final PageController _controller = PageController();
  int _currentPage = 0;

  bool get _isLastPage => _currentPage >= widget.pages.length - 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onPageChanged(int index) {
    if (index == _currentPage) {
      return;
    }
    setState(() => _currentPage = index);
  }

  /// Advances to the next page, or completes on the last page. Paging duration
  /// resolves through [A11y.resolveMotionDuration] so it jumps instantly
  /// (`Duration.zero`) under reduced motion.
  void _onPrimaryPressed() {
    if (_isLastPage) {
      widget.onComplete();
      return;
    }
    final duration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionMedium);
    if (duration == Duration.zero) {
      _controller.jumpToPage(_currentPage + 1);
      return;
    }
    _controller.animateToPage(
      _currentPage + 1,
      duration: duration,
      curve: Curves.easeInOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pages = widget.pages;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Skip control: always visible, top-aligned to the trailing edge.
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: Padding(
                padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                child: MinTapTarget(
                  child: TextButton(
                    key: const Key('onboarding-skip'),
                    onPressed: widget.onSkip,
                    child: Semantics(
                      button: true,
                      label: 'Bỏ qua phần giới thiệu',
                      child: ExcludeSemantics(
                        child: Text(
                          'Bỏ qua',
                          textScaler: A11y.resolveTextScaler(context),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                key: const Key('onboarding-pageview'),
                controller: _controller,
                onPageChanged: _onPageChanged,
                itemCount: pages.length,
                itemBuilder: (context, index) => _OnboardingPageView(
                  page: pages[index],
                ),
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            _PageIndicator(
              count: pages.length,
              currentIndex: _currentPage,
            ),
            const SizedBox(height: ClaraTokens.spaceLg),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaraTokens.spaceLg,
                0,
                ClaraTokens.spaceLg,
                ClaraTokens.spaceLg,
              ),
              child: SizedBox(
                width: double.infinity,
                child: ClaraButton.primary(
                  key: const Key('onboarding-primary'),
                  label: _isLastPage ? 'Bắt đầu' : 'Tiếp tục',
                  onPressed: _onPrimaryPressed,
                ),
              ),
            ),
          ],
        ),
      ),
      backgroundColor: theme.colorScheme.surface,
    );
  }
}

/// Renders a single [OnboardingPage]: a decorative icon, a heading, and the
/// supporting body, centered and text-scaling aware (Req 5.4).
class _OnboardingPageView extends StatelessWidget {
  const _OnboardingPageView({required this.page});

  final OnboardingPage page;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return A11yLabeled(
      label: page.title,
      value: page.body,
      isHeader: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceXl,
          vertical: ClaraTokens.spaceLg,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Decorative icon: excluded so the title/body are the single
            // authoritative announcement.
            ExcludeSemantics(
              child: Icon(
                page.icon,
                size: 96,
                color: scheme.primary,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceXl),
            Text(
              page.title,
              textAlign: TextAlign.center,
              textScaler: A11y.resolveTextScaler(context),
              style: theme.textTheme.headlineSmall?.copyWith(
                color: scheme.onSurface,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceMd),
            Text(
              page.body,
              textAlign: TextAlign.center,
              textScaler: A11y.resolveTextScaler(context),
              style: theme.textTheme.bodyLarge?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A dot page indicator reflecting the current page. The active dot is wider
/// and uses the primary color; the status is also exposed as a semantics value
/// ("Trang X trên N") so it is not conveyed by color alone (Req 5.4 / 9.5).
class _PageIndicator extends StatelessWidget {
  const _PageIndicator({
    required this.count,
    required this.currentIndex,
  });

  final int count;
  final int currentIndex;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Semantics(
      label: 'Tiến trình giới thiệu',
      value: 'Trang ${currentIndex + 1} trên $count',
      container: true,
      child: ExcludeSemantics(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List<Widget>.generate(count, (index) {
            final isActive = index == currentIndex;
            return AnimatedContainer(
              duration: A11y.resolveMotionDuration(
                context,
                ClaraTokens.motionFast,
              ),
              margin: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceXs,
              ),
              height: ClaraTokens.spaceSm,
              width: isActive ? ClaraTokens.spaceLg : ClaraTokens.spaceSm,
              decoration: BoxDecoration(
                color: isActive
                    ? scheme.primary
                    : scheme.onSurfaceVariant.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
              ),
            );
          }),
        ),
      ),
    );
  }
}
