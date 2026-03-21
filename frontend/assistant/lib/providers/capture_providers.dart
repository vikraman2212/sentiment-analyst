import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/client.dart';
import '../services/api_service.dart';
import '../services/audio_service.dart';

enum RecordingState { idle, recording, uploading, done, error }

final apiClientProvider = Provider<ApiClient>((_) => ApiClient());

final apiServiceProvider = Provider<ApiService>(
  (ref) => ApiService(client: ref.watch(apiClientProvider)),
);

final audioServiceProvider = Provider.autoDispose<AudioService>((ref) {
  final svc = AudioService(
    apiService: ref.watch(apiServiceProvider),
    apiClient: ref.watch(apiClientProvider),
  );
  ref.onDispose(svc.dispose);
  return svc;
});

final clientListProvider = FutureProvider<List<Client>>((ref) {
  return ref.watch(apiServiceProvider).getClients();
});

final selectedClientProvider = StateProvider<Client?>((_) => null);

final recordingStateProvider = StateProvider<RecordingState>(
  (_) => RecordingState.idle,
);
