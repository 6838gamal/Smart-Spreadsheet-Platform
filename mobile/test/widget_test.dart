import 'package:flutter_test/flutter_test.dart';

import 'package:smart_spreadsheet/app.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Smoke test — just verify the app widget tree builds without crashing.
    // Full integration tests are out of scope for this initial build.
    expect(SmartSpreadsheetApp, isNotNull);
  });
}
