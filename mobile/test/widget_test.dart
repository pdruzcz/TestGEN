import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:testgen_mobile/main.dart';
import 'package:testgen_mobile/webview/webview_container.dart';

void main() {
  testWidgets('TestGEN app renderuje kontener WebView', (tester) async {
    // Linux — jedyna platforma renderowalna bez natywnego pluginu WebView.
    debugDefaultTargetPlatformOverride = TargetPlatform.linux;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);

    await tester.pumpWidget(const TestGENApp());

    expect(find.byType(WebViewContainer), findsOneWidget);
  });
}
