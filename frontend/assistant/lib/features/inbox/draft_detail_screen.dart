import 'package:flutter/material.dart';
import '../../models/draft.dart';

/// Placeholder target for inbox list navigation.
/// Full implementation is delivered in issue #24.
class DraftDetailScreen extends StatelessWidget {
  final Draft draft;

  const DraftDetailScreen({super.key, required this.draft});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(draft.clientName)),
      body: const Center(child: Text('Draft detail — coming soon')),
    );
  }
}
