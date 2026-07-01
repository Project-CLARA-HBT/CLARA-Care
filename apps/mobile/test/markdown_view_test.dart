// Tests for MarkdownView (widget) and mdToPlainText (pure helper).
//
// The pure `mdToPlainText` tests assert the plain-text flattening contract used
// by "copy" actions; the widget tests are smoke tests confirming a variety of
// GFM constructs render without throwing and surface their visible text.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/widgets/markdown_view.dart';

void main() {
  group('mdToPlainText', () {
    test('bold **x** flattens to x', () {
      expect(mdToPlainText('**x**'), 'x');
    });

    test('heading "# Title" flattens to Title', () {
      expect(mdToPlainText('# Title'), 'Title');
    });

    test('bullet list produces lines prefixed with "- "', () {
      final out = mdToPlainText('- a\n- b');
      final lines = out.split('\n');
      expect(lines, ['- a', '- b']);
      for (final line in lines) {
        expect(line.startsWith('- '), isTrue);
      }
    });

    test('link [label](http://x) reduces to label', () {
      expect(mdToPlainText('[label](http://x)'), 'label');
    });

    test('inline code renders without backticks', () {
      final out = mdToPlainText('use `code` here');
      expect(out, 'use code here');
      expect(out.contains('`'), isFalse);
    });

    test('fenced code block renders code text without backticks', () {
      final out = mdToPlainText('```\nprint(1)\n```');
      expect(out, 'print(1)');
      expect(out.contains('`'), isFalse);
    });

    test('headings and paragraphs are separated by blank lines', () {
      final out = mdToPlainText('# Title\n\nBody text');
      expect(out, 'Title\n\nBody text');
    });

    test('empty / whitespace input flattens to empty string', () {
      expect(mdToPlainText(''), '');
      expect(mdToPlainText('   \n  '), '');
    });
  });

  group('MarkdownView widget', () {
    Future<void> pumpMarkdown(WidgetTester tester, String source) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: MarkdownView(source)),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('renders a mix of GFM constructs without throwing',
        (tester) async {
      const source =
          '# H\n\n- a\n- b\n\n**bold** and `code`\n\n| A | B |\n|---|---|\n| 1 | 2 |';
      await pumpMarkdown(tester, source);

      expect(tester.takeException(), isNull);

      // The rendered visible text should surface these fragments somewhere.
      for (final fragment in const ['H', 'bold', 'code', 'A', '1']) {
        expect(
          find.textContaining(fragment, findRichText: true),
          findsWidgets,
          reason: 'expected to find "$fragment" in the rendered output',
        );
      }
    });

    testWidgets('renders headings, blockquotes, links and hr without throwing',
        (tester) async {
      const source =
          '## Heading\n\n> a quote\n\n[label](http://example.com)\n\n---\n\nplain paragraph';
      await pumpMarkdown(tester, source);

      expect(tester.takeException(), isNull);
      expect(find.byType(Divider), findsOneWidget);
      expect(
        find.textContaining('label', findRichText: true),
        findsWidgets,
      );
    });

    testWidgets('empty string renders a SizedBox with no exception',
        (tester) async {
      await pumpMarkdown(tester, '');

      expect(tester.takeException(), isNull);

      final view = tester.widget<MarkdownView>(find.byType(MarkdownView));
      final built = view.build(
        tester.element(find.byType(MarkdownView)),
      );
      expect(built, isA<SizedBox>());
      expect((built as SizedBox).width, 0.0);
      expect(built.height, 0.0);
    });

    testWidgets('whitespace-only string renders a shrunk SizedBox',
        (tester) async {
      await pumpMarkdown(tester, '   \n  ');
      expect(tester.takeException(), isNull);

      final view = tester.widget<MarkdownView>(find.byType(MarkdownView));
      final built = view.build(tester.element(find.byType(MarkdownView)));
      expect(built, isA<SizedBox>());
    });

    testWidgets('selectable variant renders without throwing', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MarkdownView('**bold** text', selectable: true),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.byType(SelectableText), findsWidgets);
    });
  });
}
