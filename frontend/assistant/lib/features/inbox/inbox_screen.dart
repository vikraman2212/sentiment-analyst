import 'package:flutter/material.dart';
import '../../models/draft.dart';
import '../../services/api_service.dart';
import 'draft_detail_screen.dart';

class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key});

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  final _service = ApiService();
  late Future<List<Draft>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.getPendingDrafts();
  }

  void _reload() {
    setState(() {
      _future = _service.getPendingDrafts();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Draft>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 48, color: Colors.red),
                const SizedBox(height: 12),
                Text(
                  'Failed to load drafts',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                TextButton(onPressed: _reload, child: const Text('Retry')),
              ],
            ),
          );
        }

        final drafts = snapshot.data ?? [];

        if (drafts.isEmpty) {
          return const Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.inbox, size: 64, color: Colors.grey),
                SizedBox(height: 12),
                Text('No pending drafts'),
              ],
            ),
          );
        }

        return RefreshIndicator(
          onRefresh: () async {
            _reload();
            await _future;
          },
          child: ListView.separated(
            itemCount: drafts.length,
            separatorBuilder: (_, i) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final draft = drafts[index];
              return ListTile(
                leading: const CircleAvatar(child: Icon(Icons.person)),
                title: Text(draft.clientName),
                subtitle: Text(_formatTriggerType(draft.triggerType)),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => DraftDetailScreen(draft: draft),
                  ),
                ),
              );
            },
          ),
        );
      },
    );
  }

  String _formatTriggerType(String raw) {
    return raw
        .split('_')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }
}
