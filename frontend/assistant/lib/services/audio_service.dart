import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import '../core/api_client.dart';
import '../core/exceptions.dart';
import 'api_service.dart';

class AudioUploadResult {
  final String objectKey;

  const AudioUploadResult({required this.objectKey});
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
  }) : _recorder = recorder ?? AudioRecorder(),
       _apiService = apiService ?? ApiService(),
       _apiClient = apiClient ?? ApiClient();

  Future<void> startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      throw const RecordingException('microphone_permission_denied');
    }

    if (kIsWeb) {
      _tempFilePath =
          'recording_${DateTime.now().millisecondsSinceEpoch}.$_recordingExtension';
      await _recorder.start(_recordConfig, path: _tempFilePath!);
      return;
    }

    final dir = await getTemporaryDirectory();
    _tempFilePath =
        '${dir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.$_recordingExtension';
    await _recorder.start(_recordConfig, path: _tempFilePath!);
  }

  Future<AudioUploadResult> stopAndUpload(String clientId) async {
    final localPath = await _recorder.stop();
    if (localPath == null) {
      throw const RecordingException('recording_not_started');
    }

    try {
      // Step 1: presign
      final presign = await _apiService.presignUpload(
        clientId: clientId,
        filename: 'recording.$_recordingExtension',
        contentType: _recordingContentType,
      );
      final uploadUrl = presign['upload_url'] as String;
      final objectKey = presign['object_key'] as String;

      // Step 2: PUT to MinIO
      final bytes = await _readRecordedBytes(localPath);
      await _apiClient.putBytes(uploadUrl, bytes, _recordingContentType);

      return AudioUploadResult(objectKey: objectKey);
    } finally {
      if (!kIsWeb && localPath.isNotEmpty) {
        final file = File(localPath);
        if (await file.exists()) {
          await file.delete();
        }
      }
      _tempFilePath = null;
    }
  }

  Future<Uint8List> _readRecordedBytes(String localPath) async {
    if (kIsWeb) {
      final response = await http.get(Uri.parse(localPath));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw const RecordingException('recording_blob_read_failed');
      }
      return response.bodyBytes;
    }

    return File(localPath).readAsBytes();
  }

  RecordConfig get _recordConfig => kIsWeb
      ? const RecordConfig(encoder: AudioEncoder.opus)
      : const RecordConfig(encoder: AudioEncoder.aacLc);

  String get _recordingContentType => kIsWeb ? 'audio/webm' : 'audio/m4a';

  String get _recordingExtension => kIsWeb ? 'webm' : 'm4a';

  void dispose() {
    _recorder.dispose();
  }
}
