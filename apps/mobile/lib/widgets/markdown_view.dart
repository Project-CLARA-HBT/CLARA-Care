// =============================================================================
// MarkdownView — themed, dependency-light GitHub-flavored Markdown renderer.
//
// Renders a Markdown string as native, theme-aware Flutter widgets, plus a
// pure `mdToPlainText` helper that flattens the same Markdown to plain text
// (used by "copy" actions).
//
// Design notes:
//   * Uses only the already-present pure-Dart `package:markdown` parser to
//     build a block/inline AST — no `flutter_markdown`, no `url_launcher`, no
//     other extra dependencies are introduced.
//   * Makes NO network calls and performs NO I/O. Links are rendered as styled,
//     NON-navigating text (no gesture recognizers, no URL launching).
//   * All colors and typography come from `Theme.of(context).colorScheme` /
//     `textTheme`, so light/dark and any custom palette apply automatically.
//     No hex colors are hardcoded.
//   * Robust by construction: unknown/unsupported element tags fall back to
//     rendering their flattened text content as a paragraph, and empty or
//     whitespace-only input renders `SizedBox.shrink()`.
// =============================================================================

import 'dart:convert' show LineSplitter;

import 'package:flutter/material.dart';
import 'package:markdown/markdown.dart' as md;

/// Parses [text] once with the shared GitHub-flavored configuration and returns
/// the top-level block AST nodes.
List<md.Node> _parseBlocks(String text) {
  final document = md.Document(extensionSet: md.ExtensionSet.gitHubFlavored);
  return document.parseLines(LineSplitter.split(text).toList());
}

/// A widget that renders GitHub-flavored Markdown [text] as themed Flutter
/// widgets.
///
/// Empty or whitespace-only [text] renders an empty [SizedBox.shrink]. Links
/// are styled but non-navigating (this widget never launches URLs or makes
/// network calls).
class MarkdownView extends StatelessWidget {
  const MarkdownView(this.text, {super.key, this.baseStyle, this.selectable = false});

  /// The raw Markdown source to render.
  final String text;

  /// Optional base text style for paragraph/inline content. Falls back to the
  /// theme's `bodyMedium` when null.
  final TextStyle? baseStyle;

  /// When true, rendered text is user-selectable.
  final bool selectable;

  @override
  Widget build(BuildContext context) {
    if (text.trim().isEmpty) {
      return const SizedBox.shrink();
    }

    final nodes = _parseBlocks(text);
    final children = <Widget>[];
    for (final node in nodes) {
      final widget = _buildBlock(context, node);
      if (widget != null) {
        children.add(widget);
      }
    }

    if (children.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: _withSpacing(children),
    );
  }

  /// Inserts vertical spacing between consecutive block widgets.
  List<Widget> _withSpacing(List<Widget> blocks) {
    final out = <Widget>[];
    for (var i = 0; i < blocks.length; i++) {
      if (i > 0) {
        out.add(const SizedBox(height: 8));
      }
      out.add(blocks[i]);
    }
    return out;
  }

  // ---------------------------------------------------------------------------
  // Block-level rendering
  // ---------------------------------------------------------------------------

  Widget? _buildBlock(BuildContext context, md.Node node) {
    if (node is md.Text) {
      final content = node.text.trim();
      if (content.isEmpty) return null;
      return _paragraph(context, [TextSpan(text: content)]);
    }
    if (node is! md.Element) {
      return null;
    }

    final theme = Theme.of(context);
    final children = node.children ?? const <md.Node>[];

    switch (node.tag) {
      case 'h1':
      case 'h2':
      case 'h3':
      case 'h4':
      case 'h5':
      case 'h6':
        return _heading(context, node.tag, children);

      case 'p':
        return _paragraph(context, _inlineSpans(context, children));

      case 'ul':
        return _list(context, node, ordered: false);

      case 'ol':
        return _list(context, node, ordered: true);

      case 'pre':
        return _codeBlock(context, node);

      case 'blockquote':
        return _blockquote(context, children);

      case 'table':
        return _table(context, node);

      case 'hr':
        return const Divider();

      case 'code':
        // A bare inline code element at block level: render as a paragraph.
        return _paragraph(context, _inlineSpans(context, [node]));

      default:
        // Unknown tag: fall back to its flattened text content as a paragraph.
        final flattened = node.textContent.trim();
        if (flattened.isEmpty) return null;
        return _paragraph(
          context,
          [TextSpan(text: flattened, style: baseStyle ?? theme.textTheme.bodyMedium)],
        );
    }
  }

  Widget _heading(BuildContext context, String tag, List<md.Node> children) {
    final textTheme = Theme.of(context).textTheme;
    TextStyle? base;
    switch (tag) {
      case 'h1':
        base = textTheme.headlineSmall;
        break;
      case 'h2':
        base = textTheme.titleLarge;
        break;
      case 'h3':
        base = textTheme.titleMedium;
        break;
      case 'h4':
        base = textTheme.titleSmall;
        break;
      case 'h5':
        base = textTheme.titleSmall?.copyWith(
          fontSize: (textTheme.titleSmall?.fontSize ?? 14) * 0.95,
        );
        break;
      case 'h6':
      default:
        base = textTheme.titleSmall?.copyWith(
          fontSize: (textTheme.titleSmall?.fontSize ?? 14) * 0.9,
        );
        break;
    }
    final style = (base ?? const TextStyle()).copyWith(fontWeight: FontWeight.bold);
    return _richText(context, _inlineSpans(context, children, base: style), style: style);
  }

  Widget _paragraph(BuildContext context, List<InlineSpan> spans) {
    final base = baseStyle ?? Theme.of(context).textTheme.bodyMedium;
    return _richText(context, spans, style: base);
  }

  Widget _richText(BuildContext context, List<InlineSpan> spans, {TextStyle? style}) {
    final rootSpan = TextSpan(style: style, children: spans);
    if (selectable) {
      return SelectableText.rich(rootSpan);
    }
    return Text.rich(rootSpan);
  }

  Widget _list(BuildContext context, md.Element listNode, {required bool ordered}) {
    final items = (listNode.children ?? const <md.Node>[])
        .whereType<md.Element>()
        .where((e) => e.tag == 'li')
        .toList();
    final rows = <Widget>[];
    for (var i = 0; i < items.length; i++) {
      rows.add(_listItem(context, items[i], ordered: ordered, index: i));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: rows,
    );
  }

  Widget _listItem(
    BuildContext context,
    md.Element item, {
    required bool ordered,
    required int index,
  }) {
    final base = baseStyle ?? Theme.of(context).textTheme.bodyMedium;
    final marker = ordered ? '${index + 1}.' : '•';

    // Split the item's children into leading inline content and nested blocks
    // (nested lists / paragraphs), so nested lists render indented below.
    final inlineChildren = <md.Node>[];
    final nestedBlocks = <md.Node>[];
    for (final child in item.children ?? const <md.Node>[]) {
      if (child is md.Element &&
          (child.tag == 'ul' ||
              child.tag == 'ol' ||
              child.tag == 'p' ||
              child.tag == 'blockquote' ||
              child.tag == 'pre')) {
        if (child.tag == 'p') {
          // A paragraph inside a list item is the item's own inline content.
          inlineChildren.addAll(child.children ?? const <md.Node>[]);
        } else {
          nestedBlocks.add(child);
        }
      } else {
        inlineChildren.add(child);
      }
    }

    final row = Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.only(right: 6),
          child: Text(marker, style: base),
        ),
        Expanded(
          child: _richText(context, _inlineSpans(context, inlineChildren), style: base),
        ),
      ],
    );

    if (nestedBlocks.isEmpty) {
      return Padding(padding: const EdgeInsets.only(bottom: 2), child: row);
    }

    final nestedWidgets = <Widget>[];
    for (final block in nestedBlocks) {
      final w = _buildBlock(context, block);
      if (w != null) nestedWidgets.add(w);
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          row,
          Padding(
            padding: const EdgeInsets.only(left: 16, top: 2),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: nestedWidgets,
            ),
          ),
        ],
      ),
    );
  }

  Widget _codeBlock(BuildContext context, md.Element pre) {
    final scheme = Theme.of(context).colorScheme;
    // A `pre` normally contains a single `code` element.
    String code;
    final codeChild = (pre.children ?? const <md.Node>[])
        .whereType<md.Element>()
        .firstWhere((e) => e.tag == 'code', orElse: () => md.Element.text('code', ''));
    code = codeChild.textContent;
    if (code.isEmpty) {
      code = pre.textContent;
    }
    // Trim a single trailing newline commonly emitted by the parser.
    if (code.endsWith('\n')) {
      code = code.substring(0, code.length - 1);
    }

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      padding: const EdgeInsets.all(12),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Text(
          code,
          style: TextStyle(
            fontFamily: 'monospace',
            color: scheme.onSurface,
          ),
        ),
      ),
    );
  }

  Widget _blockquote(BuildContext context, List<md.Node> children) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final quoteStyle = (baseStyle ?? theme.textTheme.bodyMedium)
        ?.copyWith(color: scheme.onSurfaceVariant);

    final inner = <Widget>[];
    for (final child in children) {
      if (child is md.Element && child.tag == 'p') {
        inner.add(
          _richText(
            context,
            _inlineSpans(context, child.children ?? const <md.Node>[], base: quoteStyle),
            style: quoteStyle,
          ),
        );
      } else {
        final w = _buildBlock(context, child);
        if (w != null) inner.add(w);
      }
    }
    if (inner.isEmpty) {
      final flattened = children.map((n) => n.textContent).join().trim();
      inner.add(Text(flattened, style: quoteStyle));
    }

    return Container(
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: scheme.primary, width: 3),
        ),
      ),
      padding: const EdgeInsets.only(left: 12, top: 4, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: inner,
      ),
    );
  }

  Widget _table(BuildContext context, md.Element table) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final headerCells = <List<md.Node>>[];
    final bodyRows = <List<List<md.Node>>>[];

    for (final section in (table.children ?? const <md.Node>[]).whereType<md.Element>()) {
      if (section.tag == 'thead') {
        for (final tr in (section.children ?? const <md.Node>[]).whereType<md.Element>()) {
          if (tr.tag != 'tr') continue;
          for (final cell in (tr.children ?? const <md.Node>[]).whereType<md.Element>()) {
            headerCells.add(cell.children ?? const <md.Node>[]);
          }
        }
      } else if (section.tag == 'tbody') {
        for (final tr in (section.children ?? const <md.Node>[]).whereType<md.Element>()) {
          if (tr.tag != 'tr') continue;
          final row = <List<md.Node>>[];
          for (final cell in (tr.children ?? const <md.Node>[]).whereType<md.Element>()) {
            row.add(cell.children ?? const <md.Node>[]);
          }
          bodyRows.add(row);
        }
      }
    }

    final headerStyle = (baseStyle ?? theme.textTheme.bodyMedium)
        ?.copyWith(fontWeight: FontWeight.bold);

    final tableRows = <TableRow>[];
    if (headerCells.isNotEmpty) {
      tableRows.add(
        TableRow(
          decoration: BoxDecoration(color: scheme.surfaceContainerHighest),
          children: [
            for (final cell in headerCells)
              _tableCell(context, cell, style: headerStyle),
          ],
        ),
      );
    }
    for (final row in bodyRows) {
      tableRows.add(
        TableRow(
          children: [
            for (final cell in row) _tableCell(context, cell),
          ],
        ),
      );
    }

    if (tableRows.isEmpty) {
      return const SizedBox.shrink();
    }

    final border = TableBorder.all(color: scheme.outline);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Table(
        border: border,
        defaultColumnWidth: const IntrinsicColumnWidth(),
        defaultVerticalAlignment: TableCellVerticalAlignment.middle,
        children: tableRows,
      ),
    );
  }

  Widget _tableCell(BuildContext context, List<md.Node> children, {TextStyle? style}) {
    final base = style ?? baseStyle ?? Theme.of(context).textTheme.bodyMedium;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: _richText(context, _inlineSpans(context, children, base: base), style: base),
    );
  }

  // ---------------------------------------------------------------------------
  // Inline rendering
  // ---------------------------------------------------------------------------

  /// Builds the inline spans for a list of inline [nodes]. [base] is the style
  /// inherited from the enclosing block, used to derive bold/italic/etc.
  List<InlineSpan> _inlineSpans(
    BuildContext context,
    List<md.Node> nodes, {
    TextStyle? base,
  }) {
    final theme = Theme.of(context);
    final effectiveBase = base ?? baseStyle ?? theme.textTheme.bodyMedium ?? const TextStyle();
    final spans = <InlineSpan>[];
    for (final node in nodes) {
      spans.addAll(_inlineSpansFor(context, node, effectiveBase));
    }
    return spans;
  }

  List<InlineSpan> _inlineSpansFor(BuildContext context, md.Node node, TextStyle base) {
    final scheme = Theme.of(context).colorScheme;

    if (node is md.Text) {
      return [TextSpan(text: node.text, style: base)];
    }
    if (node is! md.Element) {
      return const [];
    }

    final children = node.children ?? const <md.Node>[];

    switch (node.tag) {
      case 'strong':
      case 'b':
        final style = base.copyWith(fontWeight: FontWeight.bold);
        return _childInlineSpans(context, children, style);

      case 'em':
      case 'i':
        final style = base.copyWith(fontStyle: FontStyle.italic);
        return _childInlineSpans(context, children, style);

      case 'code':
        return [
          TextSpan(
            text: node.textContent,
            style: base.copyWith(
              fontFamily: 'monospace',
              backgroundColor: scheme.surfaceContainerHighest,
            ),
          ),
        ];

      case 'a':
        final linkStyle = base.copyWith(
          color: scheme.primary,
          decoration: TextDecoration.underline,
        );
        // Non-navigating: render the visible link text in primary color.
        if (children.isEmpty) {
          return [TextSpan(text: node.textContent, style: linkStyle)];
        }
        return _childInlineSpans(context, children, linkStyle);

      case 'br':
        return const [TextSpan(text: '\n')];

      default:
        // Unknown inline tag: render its children with the current style.
        if (children.isEmpty) {
          final t = node.textContent;
          return t.isEmpty ? const [] : [TextSpan(text: t, style: base)];
        }
        return _childInlineSpans(context, children, base);
    }
  }

  List<InlineSpan> _childInlineSpans(
    BuildContext context,
    List<md.Node> children,
    TextStyle style,
  ) {
    final spans = <InlineSpan>[];
    for (final child in children) {
      spans.addAll(_inlineSpansFor(context, child, style));
    }
    return spans;
  }
}

// =============================================================================
// Pure plain-text flattening (no Flutter dependency).
// =============================================================================

/// Flattens GitHub-flavored [markdown] to plain text.
///
/// Headings and paragraphs are separated by blank lines, list items are
/// prefixed with `- `, fenced/inline code is stripped of its backticks, and
/// links are reduced to their visible text. Used by "copy" actions.
///
/// Pure: no Flutter dependency, no I/O, no network calls.
String mdToPlainText(String markdown) {
  if (markdown.trim().isEmpty) {
    return '';
  }
  final nodes = _parseBlocks(markdown);
  final blocks = <String>[];
  for (final node in nodes) {
    final rendered = _plainBlock(node, depth: 0);
    if (rendered.trim().isNotEmpty) {
      blocks.add(rendered);
    }
  }
  return blocks.join('\n\n').trim();
}

String _plainBlock(md.Node node, {required int depth}) {
  if (node is md.Text) {
    return node.text.trim();
  }
  if (node is! md.Element) {
    return '';
  }

  final children = node.children ?? const <md.Node>[];

  switch (node.tag) {
    case 'h1':
    case 'h2':
    case 'h3':
    case 'h4':
    case 'h5':
    case 'h6':
    case 'p':
      return _plainInline(children);

    case 'ul':
    case 'ol':
      final lines = <String>[];
      final items = children.whereType<md.Element>().where((e) => e.tag == 'li');
      for (final item in items) {
        lines.add(_plainListItem(item, depth: depth));
      }
      return lines.join('\n');

    case 'pre':
      final codeChild = children
          .whereType<md.Element>()
          .firstWhere((e) => e.tag == 'code', orElse: () => md.Element.text('code', ''));
      var code = codeChild.textContent;
      if (code.isEmpty) code = node.textContent;
      if (code.endsWith('\n')) {
        code = code.substring(0, code.length - 1);
      }
      return code;

    case 'blockquote':
      final inner = <String>[];
      for (final child in children) {
        final rendered = _plainBlock(child, depth: depth);
        if (rendered.trim().isNotEmpty) inner.add(rendered);
      }
      return inner.join('\n\n');

    case 'table':
      return _plainTable(node);

    case 'hr':
      return '';

    case 'code':
      return node.textContent;

    default:
      return _plainInline(children);
  }
}

String _plainListItem(md.Element item, {required int depth}) {
  final indent = '  ' * depth;
  final inlineChildren = <md.Node>[];
  final nestedLists = <md.Element>[];
  for (final child in item.children ?? const <md.Node>[]) {
    if (child is md.Element && (child.tag == 'ul' || child.tag == 'ol')) {
      nestedLists.add(child);
    } else if (child is md.Element && child.tag == 'p') {
      inlineChildren.addAll(child.children ?? const <md.Node>[]);
    } else {
      inlineChildren.add(child);
    }
  }
  final buffer = StringBuffer('$indent- ${_plainInline(inlineChildren)}');
  for (final nested in nestedLists) {
    final rendered = _plainBlock(nested, depth: depth + 1);
    if (rendered.trim().isNotEmpty) {
      buffer.write('\n$rendered');
    }
  }
  return buffer.toString();
}

String _plainTable(md.Element table) {
  final rows = <String>[];
  for (final section in (table.children ?? const <md.Node>[]).whereType<md.Element>()) {
    for (final tr in (section.children ?? const <md.Node>[]).whereType<md.Element>()) {
      if (tr.tag != 'tr') continue;
      final cells = <String>[];
      for (final cell in (tr.children ?? const <md.Node>[]).whereType<md.Element>()) {
        cells.add(_plainInline(cell.children ?? const <md.Node>[]));
      }
      rows.add(cells.join(' | '));
    }
  }
  return rows.join('\n');
}

String _plainInline(List<md.Node> nodes) {
  final buffer = StringBuffer();
  for (final node in nodes) {
    buffer.write(_plainInlineNode(node));
  }
  return buffer.toString().trim();
}

String _plainInlineNode(md.Node node) {
  if (node is md.Text) {
    return node.text;
  }
  if (node is! md.Element) {
    return '';
  }
  switch (node.tag) {
    case 'br':
      return '\n';
    case 'code':
      // Strip backticks: the AST text content already excludes them.
      return node.textContent;
    default:
      // strong/em/a/etc.: reduce to visible text.
      final children = node.children;
      if (children == null || children.isEmpty) {
        return node.textContent;
      }
      final buffer = StringBuffer();
      for (final child in children) {
        buffer.write(_plainInlineNode(child));
      }
      return buffer.toString();
  }
}
