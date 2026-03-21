class ApiException implements Exception {
  final String message;
  final int? statusCode;

  const ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class RecordingException implements Exception {
  final String message;

  const RecordingException(this.message);

  @override
  String toString() => 'RecordingException: $message';
}
