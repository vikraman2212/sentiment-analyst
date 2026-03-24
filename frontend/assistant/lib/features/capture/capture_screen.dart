import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'widgets/client_picker.dart';
import 'widgets/record_button.dart';

class CaptureScreen extends ConsumerWidget {
  const CaptureScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          const Expanded(child: ClientPicker()),
          const SizedBox(height: 24),
          const RecordButton(),
          const SizedBox(height: 48),
        ],
      ),
    );
  }
}
