import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import '../core/api_client.dart';
import '../core/exceptions.dart';
import 'api_service.dart';

class AudioUploadResult {
  final String interactionId;
  final int extractedTagsCount;

  const AudioUploadResult({
    required this.interactionId,
    required this.extractedTagsCount,
  });
}

class AudioService {
  final AudioRecorder _recorder;
  final ApiService _apiService;
  final ApiClient _apiClient;
  String? _tempFilePath;

  AudioService({
    AudioRecorder? recorder,
    ApiService? apiService,
    ApiClient? apiClient,
  })  : _recorder = recorder ?? AudioRecorder(),
        _apiService = apiService ?? ApiService(),
        _apiClient = apiClient ?? ApiClient();

  Future<void> startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      throw const RecordingException('microphone_permission_denied');
    }
    final dir = await getTemporaryDirectory();
    _tempFilePath =
        '${dir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc),
      path: _tempFilePath!,
    );
  }

  Future<AudioUploadResult> stopAndUpload(String clientId) async {
    final localPath = await _recorder.stop();
    if (localPath == null) {
      throw const RecordingException('recording_not_started');
    }
    final file = File(localPath);
    try {
      // Step 1: presign
      final presign = await _apiService.presignUpload(
        clientId: clientId,
        filename: 'recording.m4a',
        contentType: 'audio/m4a',
      );
      final uploadUrl = presign['upload_url'] as String;
      final objectKey = presign['object_key'] as String;

      // Step 2: PUT to MinIO
      final bytes = await file.readAsBytes();
      await _apiClient.putBytes(uploadUrl, bytes, 'audio/m4a');

      // Step 3: process
      final result =
          await _apiService.processAudio(clientId: clientId, objectKey: objectKey);
      return AudioUploadResult(
        interactionId: result['interaction_id'] as String,
        extractedTagsCount: result['extracted_tags_count'] as int,
      );
    } finally {
      if (await file.exists()) {
        await file.delete();
      }
      _tempFilePath = null;
    }
  }

  void dispose() {
    _recorder.dispose();
  }
}
