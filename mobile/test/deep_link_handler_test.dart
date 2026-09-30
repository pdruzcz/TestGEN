import 'package:flutter_test/flutter_test.dart';
import 'package:testgen_mobile/deep_link/deep_link_handler.dart';
import 'package:testgen_mobile/notifications/notification_handler.dart';

void main() {
  group('DeepLinkHandler.parse', () {
    test('tłumaczy testgen://analysis/123 na /analysis/123', () {
      expect(
        DeepLinkHandler.parse(Uri.parse('testgen://analysis/123')),
        '/analysis/123',
      );
    });

    test('obsługuje zagnieżdżone ścieżki projektów', () {
      expect(
        DeepLinkHandler.parse(Uri.parse('testgen://projects/42/upload')),
        '/projects/42/upload',
      );
    });

    test('zachowuje query string', () {
      expect(
        DeepLinkHandler.parse(Uri.parse('testgen://reports/7?format=pdf')),
        '/reports/7?format=pdf',
      );
    });

    test('odrzuca nieznany schemat i korzeń ścieżki', () {
      expect(DeepLinkHandler.parse(Uri.parse('https://analysis/1')), isNull);
      expect(DeepLinkHandler.parse(Uri.parse('testgen://admin/panel')), isNull);
      expect(DeepLinkHandler.parse(Uri.parse('testgen://')), isNull);
    });
  });

  group('NotificationHandler', () {
    test('kliknięcie powiadomienia nawiguje przez deep link', () {
      final navigated = <String>[];
      final handler = NotificationHandler(onNavigate: navigated.add);
      final handled = handler.handleNotificationTap({
        'deepLink': 'testgen://analysis/123',
      });
      expect(handled, isTrue);
      expect(navigated, ['/analysis/123']);
    });

    test('ignoruje payload bez poprawnego deep linka', () {
      final navigated = <String>[];
      final handler = NotificationHandler(onNavigate: navigated.add);
      expect(handler.handleNotificationTap({}), isFalse);
      expect(handler.handleNotificationTap({'deepLink': ''}), isFalse);
      expect(
        handler.handleNotificationTap({'deepLink': 'https://zewnetrzny'}),
        isFalse,
      );
      expect(navigated, isEmpty);
    });
  });
}
