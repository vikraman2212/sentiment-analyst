import '../core/api_client.dart';
import '../models/client.dart';
import '../models/draft.dart';

class ApiService {
  final ApiClient _client;

  ApiService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<List<Client>> getClients({String? advisorId}) async {
    final path = Uri(
      path: '/api/v1/clients/',
      queryParameters: advisorId != null && advisorId.isNotEmpty
          ? {'advisor_id': advisorId}
          : null,
    ).toString();
    final list = await _client.getList(path);
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

  Future<List<Draft>> getPendingDrafts() async {
    final list = await _client.getList('/api/v1/drafts/pending');
    return list.map((e) => Draft.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> updateDraftStatus(String draftId, String status) async {
    await _client.patch('/api/v1/message-drafts/$draftId/status', {
      'status': status,
    });
  }
}
