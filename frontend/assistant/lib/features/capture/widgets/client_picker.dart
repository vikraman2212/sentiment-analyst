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
  static const int _pageSize = 20;

  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  String _query = '';
  int _visibleCount = _pageSize;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleScroll);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_handleScroll)
      ..dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _handleScroll() {
    if (!_scrollController.hasClients) {
      return;
    }

    final position = _scrollController.position;
    if (position.pixels < position.maxScrollExtent - 160) {
      return;
    }

    setState(() {
      _visibleCount += _pageSize;
    });
  }

  void _resetVisibleCount() {
    setState(() {
      _visibleCount = _pageSize;
    });

    if (_scrollController.hasClients) {
      _scrollController.jumpTo(0);
    }
  }

  @override
  Widget build(BuildContext context) {
    final selected = ref.watch(selectedClientProvider);
    final advisorIdAsync = ref.watch(advisorIdProvider);
    final clientsAsync = ref.watch(clientListProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        advisorIdAsync.when(
          data: (advisorId) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              advisorId == null || advisorId.isEmpty
                  ? 'Showing all clients'
                  : 'Filtered by advisor: $advisorId',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          loading: () => const SizedBox.shrink(),
          error: (_, _) => const SizedBox.shrink(),
        ),
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
            onChanged: (value) {
              _query = value;
              _resetVisibleCount();
            },
          ),
        if (selected == null) const SizedBox(height: 12),
        if (selected == null)
          Expanded(
            child: clientsAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (err, _) => Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
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
                final visible = filtered.take(_visibleCount).toList();

                if (filtered.isEmpty) {
                  return Center(
                    child: Text(
                      _query.isEmpty
                          ? 'No clients found for the current advisor filter'
                          : 'No matching clients',
                    ),
                  );
                }

                final hasMore = visible.length < filtered.length;

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        'Showing ${visible.length} of ${filtered.length} clients',
                      ),
                    ),
                    Expanded(
                      child: ListView.builder(
                        controller: _scrollController,
                        itemCount: visible.length + (hasMore ? 1 : 0),
                        itemBuilder: (_, index) {
                          if (index >= visible.length) {
                            return const Padding(
                              padding: EdgeInsets.symmetric(vertical: 16),
                              child: Center(
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              ),
                            );
                          }

                          final client = visible[index];
                          return ListTile(
                            title: Text(client.fullName),
                            onTap: () {
                              ref.read(selectedClientProvider.notifier).state =
                                  client;
                              _searchController.clear();
                              _query = '';
                              _resetVisibleCount();
                            },
                          );
                        },
                      ),
                    ),
                  ],
                );
              },
            ),
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
