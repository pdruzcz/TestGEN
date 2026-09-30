import '../deep_link/deep_link_handler.dart';

/// Story 6.12 (AC7) — obsługa kliknięć powiadomień push.
///
/// Warstwa transportowa (FCM na iOS/Android, WNS na Windows) wymaga
/// konfiguracji projektu Firebase (google-services.json /
/// GoogleService-Info.plist) oraz rejestracji aplikacji w WNS — patrz
/// mobile/README.md. Ten handler jest od niej niezależny: przyjmuje payload
/// powiadomienia i tłumaczy go na nawigację w Angularze przez JS bridge.
class NotificationHandler {
  NotificationHandler({required this.onNavigate});

  /// Callback nawigacji — docelowo `JsBridge.navigateTo`.
  final void Function(String path) onNavigate;

  /// Klucz payloadu z deep linkiem, np. `{"deepLink": "testgen://analysis/123"}`.
  static const String deepLinkKey = 'deepLink';

  /// Obsługa kliknięcia powiadomienia: payload -> deep link -> nawigacja.
  /// Zwraca `true`, gdy payload zawierał poprawny deep link.
  bool handleNotificationTap(Map<String, dynamic> data) {
    final link = data[deepLinkKey];
    if (link is! String || link.isEmpty) return false;
    final uri = Uri.tryParse(link);
    if (uri == null) return false;
    final path = DeepLinkHandler.parse(uri);
    if (path == null) return false;
    onNavigate(path);
    return true;
  }
}
