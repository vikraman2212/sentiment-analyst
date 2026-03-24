import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:assistant/core/api_client.dart';
import 'package:assistant/models/client.dart';
import 'package:assistant/providers/capture_providers.dart';
import 'package:assistant/services/api_service.dart';
import 'package:assistant/features/capture/capture_screen.dart';

class MockApiClient extends Mock implements ApiClient {}

class MockApiService extends Mock implements ApiService {}

final _testClients = [
  const Client(id: '1', firstName: 'Alice', lastName: 'Smith'),
  const Client(id: '2', firstName: 'Bob', lastName: 'Jones'),
  const Client(id: '3', firstName: 'Charlie', lastName: 'Brown'),
];

Widget _buildApp({required List<Override> overrides}) {
  return ProviderScope(
    overrides: [
      advisorIdProvider.overrideWith((_) async => null),
      ...overrides,
    ],
    child: const MaterialApp(home: Scaffold(body: CaptureScreen())),
  );
}

void main() {
  late MockApiService mockApiService;

  setUp(() {
    mockApiService = MockApiService();
  });

  group('CaptureScreen', () {
    testWidgets('shows loading spinner while clients load', (tester) async {
      final completer = Completer<List<Client>>();
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenAnswer((_) => completer.future);

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Complete the future to avoid dangling resources.
      completer.complete(_testClients);
      await tester.pumpAndSettle();
    });

    testWidgets('shows client list after load', (tester) async {
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenAnswer((_) async => _testClients);

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Alice Smith'), findsOneWidget);
      expect(find.text('Bob Jones'), findsOneWidget);
      expect(find.text('Charlie Brown'), findsOneWidget);
    });

    testWidgets('search filters client list', (tester) async {
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenAnswer((_) async => _testClients);

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'alice');
      await tester.pump();

      expect(find.text('Alice Smith'), findsOneWidget);
      expect(find.text('Bob Jones'), findsNothing);
      expect(find.text('Charlie Brown'), findsNothing);
    });

    testWidgets('shows error state with retry button', (tester) async {
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenThrow(Exception('network error'));

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Failed to load clients'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets(
      'record button shows "Select a client first" when none selected',
      (tester) async {
        when(
          () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
        ).thenAnswer((_) async => _testClients);

        await tester.pumpWidget(
          _buildApp(
            overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Select a client first'), findsOneWidget);
      },
    );

    testWidgets('selecting a client shows chip and enables record button', (
      tester,
    ) async {
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenAnswer((_) async => _testClients);

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pumpAndSettle();

      // Tap Alice Smith
      await tester.tap(find.text('Alice Smith'));
      await tester.pumpAndSettle();

      // Chip is visible
      expect(find.widgetWithText(InputChip, 'Alice Smith'), findsOneWidget);
      // Search field is gone
      expect(find.byType(TextField), findsNothing);
      // Record button says "Hold to record"
      expect(find.text('Hold to record'), findsOneWidget);
    });

    testWidgets('deselecting client via chip shows search again', (
      tester,
    ) async {
      when(
        () => mockApiService.getClients(advisorId: any(named: 'advisorId')),
      ).thenAnswer((_) async => _testClients);

      await tester.pumpWidget(
        _buildApp(
          overrides: [apiServiceProvider.overrideWithValue(mockApiService)],
        ),
      );
      await tester.pumpAndSettle();

      // Select Alice
      await tester.tap(find.text('Alice Smith'));
      await tester.pumpAndSettle();

      // Delete chip — tap the clear icon rendered by InputChip
      await tester.tap(find.byIcon(Icons.clear));
      await tester.pumpAndSettle();

      // Search field is back
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Select a client first'), findsOneWidget);
    });
  });
}
