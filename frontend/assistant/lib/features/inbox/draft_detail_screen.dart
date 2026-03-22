import 'package:flutter/material.dart';
import '../../models/draft.dart';

class DraftDetailScreen extends StatelessWidget {
  final Draft draft;

  const DraftDetailScreen({super.key, required this.draft});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final grouped = _groupByCategory(draft.contextUsed);

    return Scaffold(
      appBar: AppBar(
        title: Text(draft.clientName),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(32),
          child: Padding(
            padding: const EdgeInsets.only(left: 16, bottom: 8),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Chip(
                label: Text(_formatTriggerType(draft.triggerType)),
                labelStyle: theme.textTheme.labelSmall,
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
              ),
            ),
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionHeader(title: 'Generated Draft'),
            const SizedBox(height: 8),
            Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: SelectableText(
                  draft.generatedContent,
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
            if (draft.contextUsed.isNotEmpty) ...[
              const SizedBox(height: 24),
              _SectionHeader(title: 'Context Used'),
              const SizedBox(height: 8),
              ...grouped.entries.map(
                (entry) => _ContextGroup(
                  category: entry.key,
                  items: entry.value,
                ),
              ),
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  String _formatTriggerType(String raw) {
    return raw
        .split('_')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  Map<String, List<String>> _groupByCategory(List<ClientContext> items) {
    final result = <String, List<String>>{};
    for (final item in items) {
      result.putIfAbsent(item.category, () => []).add(item.content);
    }
    return result;
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;

  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: Theme.of(context)
          .textTheme
          .titleSmall
          ?.copyWith(fontWeight: FontWeight.bold),
    );
  }
}

class _ContextGroup extends StatelessWidget {
  final String category;
  final List<String> items;

  const _ContextGroup({required this.category, required this.items});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _formatCategory(category),
            style: theme.textTheme.labelMedium?.copyWith(
              color: theme.colorScheme.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: items
                .map(
                  (content) => Chip(
                    label: Text(
                      content,
                      style: theme.textTheme.bodySmall,
                    ),
                    backgroundColor:
                        theme.colorScheme.secondaryContainer.withValues(alpha: 0.5),
                    side: BorderSide.none,
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    visualDensity: VisualDensity.compact,
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  String _formatCategory(String raw) {
    return raw
        .split('_')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }
}

