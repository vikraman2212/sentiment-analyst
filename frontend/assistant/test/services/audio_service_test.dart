import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:record/record.dart';

import 'package:assistant/core/exceptions.dart';
import 'package:assistant/core/api_client.dart';
import 'package:assistant/services/api_service.dart';
import 'package:assistant/services/audio_service.dart';

// ── Mock declarations ─────────────────────────────────────────────────────────

class _MockAudioRecorder extends Mock implements AudioRecorder {}

class _MockApiService extends Mock implements ApiService {}

class _MockApiClient extends Mock implements ApiClient {}

// ── Tests ─────────────────────────────────────────────────────────────────────

void main() {
  // path_provider (used by AudioService.startRecording) requires the Flutter
  // binding when accessed from a plain test().
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AudioService', () {
    late _MockAudioRecorder mockRecorder;
    late _MockApiService mockApiService;
    late _MockApiClient mockApiClient;
    late AudioService sut;
    late File tempFile;

    setUpAll(() {
      // Fallback values required by mocktail for custom / generic types used
      // with any() matchers.
      registerFallbackValue(const RecordConfig());
      registerFallbackValue(<int>[]);

      // path_provider is not registered as a native plugin in unit tests.
      // Intercept its MethodChannel and return the host temp directory so
      // AudioService.startRecording() can build a valid recording path.
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            const MethodChannel('plugins.flutter.io/path_provider'),
            (MethodCall call) async {
              if (call.method == 'getTemporaryDirectory') {
                return Directory.systemTemp.path;
              }
              return null;
            },
          );
    });

    setUp(() async {
      mockRecorder = _MockAudioRecorder();
      mockApiService = _MockApiService();
      mockApiClient = _MockApiClient();

      sut = AudioService(
        recorder: mockRecorder,
        apiService: mockApiService,
        apiClient: mockApiClient,
      );

      // A real temp file that stands in for the recorded .m4a during tests.
      // The service calls File(stopPath).delete() in its finally block, so the
      // file must actually exist for the deletion to succeed.
      tempFile = File(
        '${Directory.systemTemp.path}'
        '/test_audio_${DateTime.now().millisecondsSinceEpoch}.m4a',
      );
      await tempFile.writeAsBytes([0xFF, 0xFB]); // minimal non-empty bytes
    });

    tearDown(() async {
      // Guard: clean up if a test skipped deletion deliberately.
      if (await tempFile.exists()) {
        await tempFile.delete();
      }
    });

    // ── startRecording ─────────────────────────────────────────────────────

    group('startRecording', () {
      test(
        'starts recorder with AAC-LC config and .m4a path when permitted',
        () async {
          when(
            () => mockRecorder.hasPermission(),
          ).thenAnswer((_) async => true);
          when(
            () => mockRecorder.start(any(), path: any(named: 'path')),
          ).thenAnswer((_) async {});

          await sut.startRecording();

          // Verify permission was checked first.
          verify(() => mockRecorder.hasPermission()).called(1);

          // Capture and assert the RecordConfig and path shape.
          final captured = verify(
            () => mockRecorder.start(
              captureAny(),
              path: captureAny(named: 'path'),
            ),
          ).captured;

          final config = captured[0] as RecordConfig;
          final path = captured[1] as String;

          expect(
            config.encoder,
            equals(AudioEncoder.aacLc),
            reason: 'must encode to AAC-LC for .m4a compatibility',
          );
          expect(
            path,
            endsWith('.m4a'),
            reason: 'temp file must have .m4a extension',
          );
        },
      );

      test('throws RecordingException(microphone_permission_denied) when '
          'permission is denied', () async {
        when(() => mockRecorder.hasPermission()).thenAnswer((_) async => false);

        await expectLater(
          sut.startRecording(),
          throwsA(
            isA<RecordingException>().having(
              (e) => e.message,
              'message',
              'microphone_permission_denied',
            ),
          ),
        );

        verifyNever(() => mockRecorder.start(any(), path: any(named: 'path')));
      });
    });

    // ── stopAndUpload ──────────────────────────────────────────────────────

    group('stopAndUpload', () {
      const clientId = 'client-uuid-123';
      const uploadUrl = 'http://localhost:9000/audio/presigned-put';
      const objectKey = 'client-uuid-123/recording.m4a';

      setUp(() {
        // Default: recorder returns our pre-created temp file path so the
        // service can read and then delete it.
        when(() => mockRecorder.stop()).thenAnswer((_) async => tempFile.path);
      });

      test(
        'executes presign and PUT steps and returns AudioUploadResult',
        () async {
          _stubPresign(
            mockApiService,
            uploadUrl: uploadUrl,
            objectKey: objectKey,
          );
          _stubPut(mockApiClient);

          final result = await sut.stopAndUpload(clientId);

          expect(result.objectKey, equals(objectKey));
        },
      );

      test('fires presign → PUT in strict sequence', () async {
        _stubPresign(
          mockApiService,
          uploadUrl: uploadUrl,
          objectKey: objectKey,
        );
        _stubPut(mockApiClient);

        await sut.stopAndUpload(clientId);

        verifyInOrder([
          () => mockApiService.presignUpload(
            clientId: clientId,
            filename: any(named: 'filename'),
            contentType: any(named: 'contentType'),
          ),
          () => mockApiClient.putBytes(uploadUrl, any(), 'audio/m4a'),
        ]);
      });

      test('passes raw file bytes to the PUT call', () async {
        _stubPresign(
          mockApiService,
          uploadUrl: uploadUrl,
          objectKey: objectKey,
        );
        _stubPut(mockApiClient);

        await sut.stopAndUpload(clientId);

        final captured = verify(
          () => mockApiClient.putBytes(any(), captureAny(), any()),
        ).captured;

        final sentBytes = captured.first as List<int>;
        expect(
          sentBytes,
          equals([0xFF, 0xFB]),
          reason: 'must send the exact bytes from the temp file',
        );
      });

      test('deletes temp file after successful upload', () async {
        _stubPresign(
          mockApiService,
          uploadUrl: uploadUrl,
          objectKey: objectKey,
        );
        _stubPut(mockApiClient);

        await sut.stopAndUpload(clientId);

        expect(
          await tempFile.exists(),
          isFalse,
          reason: 'temp file must be cleaned up on success',
        );
      });

      test('deletes temp file and rethrows when presign fails; '
          'PUT is never called', () async {
        when(
          () => mockApiService.presignUpload(
            clientId: any(named: 'clientId'),
            filename: any(named: 'filename'),
            contentType: any(named: 'contentType'),
          ),
        ).thenThrow(const ApiException('presign_failed', statusCode: 500));

        await expectLater(
          sut.stopAndUpload(clientId),
          throwsA(isA<ApiException>()),
        );

        expect(
          await tempFile.exists(),
          isFalse,
          reason: 'temp file must be cleaned up even when presign fails',
        );
        verifyNever(() => mockApiClient.putBytes(any(), any(), any()));
      });

      test('deletes temp file and rethrows when MinIO PUT fails', () async {
        _stubPresign(
          mockApiService,
          uploadUrl: uploadUrl,
          objectKey: objectKey,
        );
        when(
          () => mockApiClient.putBytes(any(), any(), any()),
        ).thenThrow(const ApiException('storage_upload_failed', statusCode: 0));

        await expectLater(
          sut.stopAndUpload(clientId),
          throwsA(
            isA<ApiException>().having(
              (e) => e.message,
              'message',
              'storage_upload_failed',
            ),
          ),
        );

        expect(
          await tempFile.exists(),
          isFalse,
          reason: 'temp file must be cleaned up even when PUT fails',
        );
      });

      test('throws RecordingException(recording_not_started) when recorder '
          'stop returns null', () async {
        when(() => mockRecorder.stop()).thenAnswer((_) async => null);

        await expectLater(
          sut.stopAndUpload(clientId),
          throwsA(
            isA<RecordingException>().having(
              (e) => e.message,
              'message',
              'recording_not_started',
            ),
          ),
        );

        verifyNever(
          () => mockApiService.presignUpload(
            clientId: any(named: 'clientId'),
            filename: any(named: 'filename'),
            contentType: any(named: 'contentType'),
          ),
        );
      });
    });
  });
}

// ── Stub helpers ──────────────────────────────────────────────────────────────

void _stubPresign(
  _MockApiService mock, {
  required String uploadUrl,
  required String objectKey,
}) {
  when(
    () => mock.presignUpload(
      clientId: any(named: 'clientId'),
      filename: any(named: 'filename'),
      contentType: any(named: 'contentType'),
    ),
  ).thenAnswer(
    (_) async => {
      'upload_url': uploadUrl,
      'object_key': objectKey,
      'expires_in': 300,
    },
  );
}

void _stubPut(_MockApiClient mock) {
  when(() => mock.putBytes(any(), any(), any())).thenAnswer((_) async {});
}
