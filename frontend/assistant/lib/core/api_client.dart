import 'dart:convert';
import 'package:http/http.dart' as http;
import 'exceptions.dart';
import 'config.dart';

class ApiClient {
  Future<Map<String, dynamic>> get(String path) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base$path');
    final response = await http.get(uri, headers: _headers());
    return _decode(response);
  }

  Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base$path');
    final response = await http.post(
      uri,
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<void> putBytes(String url, List<int> bytes, String contentType) async {
    final uri = Uri.parse(url);
    final response = await http.put(
      uri,
      headers: {'Content-Type': contentType},
      body: bytes,
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        'storage_upload_failed',
        statusCode: response.statusCode,
      );
    }
  }

  Future<List<dynamic>> getList(String path) async {
    final base = await getBaseUrl();
    final uri = Uri.parse('$base$path');
    final response = await http.get(uri, headers: _headers());
    return _decodeList(response);
  }

  Map<String, String> _headers() => {'Content-Type': 'application/json'};

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw ApiException(response.body, statusCode: response.statusCode);
  }

  List<dynamic> _decodeList(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body) as List<dynamic>;
    }
    throw ApiException(response.body, statusCode: response.statusCode);
  }
}
