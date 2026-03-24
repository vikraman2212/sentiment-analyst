import 'dart:convert';
import 'package:http/http.dart' as http;
import 'exceptions.dart';
import 'config.dart';

class ApiClient {
  Future<Map<String, dynamic>> get(String path) async {
    final uri = await _buildUri(path);
    final response = await http.get(uri, headers: _headers());
    return _decode(response);
  }

  Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final uri = await _buildUri(path);
    final response = await http.post(
      uri,
      headers: _headers(),
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> patch(
    String path,
    Map<String, dynamic> body,
  ) async {
    final uri = await _buildUri(path);
    final response = await http.patch(
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
    final uri = await _buildUri(path);
    final response = await http.get(uri, headers: _headers());
    return _decodeList(response);
  }

  Future<Uri> _buildUri(String path) async {
    final base = await getBaseUrl();
    final baseUri = Uri.parse(base.endsWith('/') ? base : '$base/');
    var normalizedPath = path.startsWith('/') ? path.substring(1) : path;
    final basePath = baseUri.path.startsWith('/')
        ? baseUri.path.substring(1)
        : baseUri.path;

    if (basePath.isNotEmpty && normalizedPath.startsWith(basePath)) {
      normalizedPath = normalizedPath.substring(basePath.length);
      if (normalizedPath.startsWith('/')) {
        normalizedPath = normalizedPath.substring(1);
      }
    }

    return baseUri.resolve(normalizedPath);
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
