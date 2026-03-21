import '../core/api_client.dart';
import '../models/client.dart';
import '../models/draft.dart';

class ApiService {
  final ApiClient _client;

  ApiService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<Client>> getClients() async {
    final list = await _client.getList('/api/v1/clients');
    return list.map((e) => Client.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> presignUpload({
    required String clientId,
    required String filename,
    required String contentType,
  }) async {
    return _client.post('/api/v1/audio/presign', {
      'client_id': clientId,
      'filename': filename,
      'content_type': contentType,
    });
  }

  Future<Map<String, dynamic>> processAudio({
    required String clientId,
    required String objectKey,
  }) async {
    return _client.post('/api/v1/audio/process', {
      'client_id': clientId,
      'object_key': objectKey,
    });
  }

  Future<List<Draft>> getPendingDrafts() async {
    final data = await _client.get('/api/v1/drafts/pending');
    final list = data['drafts'] as List<dynamic>;
    return list.map((e) => Draft.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> approveDraft(String draftId) async {
    await _client.post('/api/v1/drafts/$draftId/approve', {});
  }
}
