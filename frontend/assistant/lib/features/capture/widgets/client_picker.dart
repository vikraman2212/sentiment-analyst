import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../models/client.dart';
import '../../../providers/capture_providers.dart';

class ClientPicker extends ConsumerStatefulWidget {
  const ClientPicker({super.key});

  @override
  ConsumerState<ClientPicker> createState() => _ClientPickerState();
}

class _ClientPickerState extends ConsumerState<ClientPicker> {
  final _searchController = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final selected = ref.watch(selectedClientProvider);
    final clientsAsync = ref.watch(clientListProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (selected != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: InputChip(
              label: Text(selected.fullName),
              deleteIcon: const Icon(Icons.clear, size: 18),
              onDeleted: () =>
                  ref.read(selectedClientProvider.notifier).state = null,
            ),
          ),
        if (selected == null)
          TextField(
            controller: _searchController,
            decoration: const InputDecoration(
              hintText: 'Search clients…',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: (v) => setState(() => _query = v),
          ),
        if (selected == null)
          clientsAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (err, _) => Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Text(
                    'Failed to load clients',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.tonal(
                    onPressed: () => ref.invalidate(clientListProvider),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
            data: (clients) {
              final filtered = _filterClients(clients);
              if (filtered.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No matching clients'),
                );
              }
              return Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: filtered.length,
                  itemBuilder: (_, i) => ListTile(
                    title: Text(filtered[i].fullName),
                    onTap: () {
                      ref.read(selectedClientProvider.notifier).state =
                          filtered[i];
                      _searchController.clear();
                      setState(() => _query = '');
                    },
                  ),
                ),
              );
            },
          ),
      ],
    );
  }

  List<Client> _filterClients(List<Client> clients) {
    if (_query.isEmpty) return clients;
    final lower = _query.toLowerCase();
    return clients
        .where((c) => c.fullName.toLowerCase().contains(lower))
        .toList();
  }
}
