import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:assistant/app.dart';
import 'package:assistant/models/client.dart';
import 'package:assistant/providers/capture_providers.dart';
import 'package:assistant/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  testWidgets('App renders bottom navigation', (WidgetTester tester) async {
    final mockApi = MockApiService();
    when(() => mockApi.getClients()).thenAnswer((_) async => <Client>[]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiServiceProvider.overrideWithValue(mockApi)],
        child: const App(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Capture'), findsOneWidget);
    expect(find.text('Inbox'), findsOneWidget);
  });
}
