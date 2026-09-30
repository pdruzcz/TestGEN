import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:testgen_mobile/webview/webview_container.dart';
import 'package:testgen_mobile/widgets/offline_message.dart';

void main() {
  group('OfflineMessage (AC6)', () {
    testWidgets('wyświetla polski komunikat i przycisk Ponów', (tester) async {
      var retried = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: OfflineMessage(onRetry: () => retried = true),
          ),
        ),
      );

      expect(
        find.text(
          'Brak połączenia z serwerem. '
          'Sprawdź połączenie internetowe i spróbuj ponownie.',
        ),
        findsOneWidget,
      );
      expect(find.text('Ponów'), findsOneWidget);

      await tester.tap(find.text('Ponów'));
      expect(retried, isTrue);
    });
  });

  group('WebViewContainer — dobór implementacji per platforma', () {
    testWidgets('Linux używa fallbacku przeglądarki systemowej', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.linux;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);

      await tester.pumpWidget(
        const MaterialApp(home: WebViewContainer()),
      );

      expect(find.byType(LinuxBrowserFallback), findsOneWidget);
      expect(find.text('Otwórz TestGEN'), findsOneWidget);
    });

    testWidgets('Windows wybiera WebView2 (WindowsWebView)', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);

      await tester.pumpWidget(
        const MaterialApp(home: WebViewContainer()),
      );

      // Inicjalizacja natywnego WebView2 nie powiedzie się w środowisku
      // testowym — widget przechodzi w stan offline (AC6) zamiast crashować.
      expect(find.byType(WindowsWebView), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.byType(OfflineMessage), findsOneWidget);
    });
  });
}
