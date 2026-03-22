import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/draft.dart';
import '../../services/api_service.dart';

class DraftDetailScreen extends StatefulWidget {
  final Draft draft;

  const DraftDetailScreen({super.key, required this.draft});

  @override
  State<DraftDetailScreen> createState() => _DraftDetailScreenState();
}

class _DraftDetailScreenState extends State<DraftDetailScreen>
    with WidgetsBindingObserver {
  final _service = ApiService();
  bool _isSending = false;
  bool _waitingForResume = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _waitingForResume) {
      _waitingForResume = false;
      _showConfirmationDialog();
    }
  }

  Future<void> _handleApproveAndSend() async {
    if (_isSending) return;
    setState(() => _isSending = true);

    final uri = Uri(
      scheme: 'mailto',
      queryParameters: {
        'subject': 'Message for ${widget.draft.clientName}',
        'body': widget.draft.generatedContent,
      },
    );

    final canLaunch = await canLaunchUrl(uri);
    if (!canLaunch) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not open mail client. Please check your email app.',
            ),
          ),
        );
      }
      setState(() => _isSending = false);
      return;
    }

    _waitingForResume = true;
    await launchUrl(uri);
  }

  Future<void> _showConfirmationDialog() async {
    if (!mounted) return;

    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('Did you send the email?'),
        content: const Text(
          'Please confirm that the message was submitted before marking this draft as sent.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Not yet'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Yes, sent'),
          ),
        ],
      ),
    );

    if (confirmed != true) {
      setState(() => _isSending = false);
      return;
    }

    await _markAsSent();
  }

  Future<void> _markAsSent() async {
    try {
      await _service.updateDraftStatus(widget.draft.draftId, 'sent');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Draft marked as sent')));
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update status: ${e.toString()}'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
        setState(() => _isSending = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final grouped = _groupByCategory(widget.draft.contextUsed);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.draft.clientName),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(32),
          child: Padding(
            padding: const EdgeInsets.only(left: 16, bottom: 8),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Chip(
                label: Text(_formatTriggerType(widget.draft.triggerType)),
                labelStyle: theme.textTheme.labelSmall,
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
              ),
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isSending ? null : _handleApproveAndSend,
        icon: _isSending
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.send),
        label: const Text('Approve & Send'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: 88,
        ),
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
                  widget.draft.generatedContent,
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
            if (widget.draft.contextUsed.isNotEmpty) ...[
              const SizedBox(height: 24),
              _SectionHeader(title: 'Context Used'),
              const SizedBox(height: 8),
              ...grouped.entries.map(
                (entry) =>
                    _ContextGroup(category: entry.key, items: entry.value),
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
      style: Theme.of(
        context,
      ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
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
                    label: Text(content, style: theme.textTheme.bodySmall),
                    backgroundColor: theme.colorScheme.secondaryContainer
                        .withValues(alpha: 0.5),
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
