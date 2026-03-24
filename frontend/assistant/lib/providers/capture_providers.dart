import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../core/config.dart';
import '../models/client.dart';
import '../services/api_service.dart';
import '../services/audio_service.dart';

enum RecordingState { idle, recording, uploading, done, error }

final apiClientProvider = Provider<ApiClient>((_) => ApiClient());

final apiServiceProvider = Provider<ApiService>(
  (ref) => ApiService(client: ref.watch(apiClientProvider)),
);

final audioServiceProvider = Provider<AudioService>((ref) {
  final svc = AudioService(
    apiService: ref.watch(apiServiceProvider),
    apiClient: ref.watch(apiClientProvider),
  );
  ref.onDispose(svc.dispose);
  return svc;
});

final advisorIdProvider = FutureProvider<String?>((_) => getAdvisorId());

final clientListProvider = FutureProvider<List<Client>>((ref) async {
  final advisorId = await ref.watch(advisorIdProvider.future);
  return ref.watch(apiServiceProvider).getClients(advisorId: advisorId);
});

final selectedClientProvider = StateProvider<Client?>((_) => null);

final recordingStateProvider = StateProvider<RecordingState>(
  (_) => RecordingState.idle,
);
