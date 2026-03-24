import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../providers/capture_providers.dart';

class RecordButton extends ConsumerStatefulWidget {
  const RecordButton({super.key});

  @override
  ConsumerState<RecordButton> createState() => _RecordButtonState();
}

class _RecordButtonState extends ConsumerState<RecordButton>
    with SingleTickerProviderStateMixin {
  final _stopwatch = Stopwatch();
  Timer? _timer;
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  void _startTimer() {
    _stopwatch.reset();
    _stopwatch.start();
    _timer = Timer.periodic(const Duration(milliseconds: 100), (_) {
      setState(() {});
    });
  }

  void _stopTimer() {
    _stopwatch.stop();
    _timer?.cancel();
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  Future<void> _onRecordStart() async {
    final audioService = ref.read(audioServiceProvider);
    ref.read(recordingStateProvider.notifier).state = RecordingState.recording;
    _pulseController.repeat(reverse: true);
    _startTimer();
    try {
      await audioService.startRecording();
    } catch (e) {
      _stopTimer();
      _pulseController.stop();
      ref.read(recordingStateProvider.notifier).state = RecordingState.error;
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Recording failed: $e')));
      }
      ref.read(recordingStateProvider.notifier).state = RecordingState.idle;
    }
  }

  Future<void> _onRecordStop() async {
    _stopTimer();
    _pulseController.stop();
    final client = ref.read(selectedClientProvider);
    if (client == null) return;

    ref.read(recordingStateProvider.notifier).state = RecordingState.uploading;
    try {
      final audioService = ref.read(audioServiceProvider);
      final result = await audioService.stopAndUpload(client.id);
      ref.read(recordingStateProvider.notifier).state = RecordingState.done;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload complete: ${result.objectKey}')),
        );
      }
    } catch (e) {
      ref.read(recordingStateProvider.notifier).state = RecordingState.error;
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Upload failed: $e')));
      }
    } finally {
      ref.read(recordingStateProvider.notifier).state = RecordingState.idle;
    }
  }

  @override
  Widget build(BuildContext context) {
    final selected = ref.watch(selectedClientProvider);
    final recordingState = ref.watch(recordingStateProvider);
    final isDisabled = selected == null;
    final isRecording = recordingState == RecordingState.recording;
    final isUploading = recordingState == RecordingState.uploading;

    final theme = Theme.of(context);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (isRecording)
          Text(
            _formatDuration(_stopwatch.elapsed),
            style: theme.textTheme.headlineMedium,
          ),
        if (isRecording) const SizedBox(height: 16),
        GestureDetector(
          onLongPressStart: isDisabled || isUploading
              ? null
              : (_) => _onRecordStart(),
          onLongPressEnd: isDisabled || !isRecording
              ? null
              : (_) => _onRecordStop(),
          child: AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              final scale = isRecording
                  ? 1.0 + _pulseController.value * 0.15
                  : 1.0;
              return Transform.scale(scale: scale, child: child);
            },
            child: Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isUploading
                    ? theme.colorScheme.surfaceContainerHighest
                    : isRecording
                    ? theme.colorScheme.error
                    : isDisabled
                    ? theme.colorScheme.surfaceContainerHighest
                    : theme.colorScheme.primary,
              ),
              child: Center(
                child: isUploading
                    ? SizedBox(
                        width: 32,
                        height: 32,
                        child: CircularProgressIndicator(
                          strokeWidth: 3,
                          color: theme.colorScheme.primary,
                        ),
                      )
                    : Icon(
                        Icons.mic,
                        size: 40,
                        color: isDisabled
                            ? theme.colorScheme.onSurfaceVariant
                            : isRecording
                            ? theme.colorScheme.onError
                            : theme.colorScheme.onPrimary,
                      ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          isUploading
              ? 'Uploading…'
              : isRecording
              ? 'Release to stop'
              : isDisabled
              ? 'Select a client first'
              : 'Hold to record',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}
