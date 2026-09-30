import 'dart:convert';

/// Story 6.12 (AC5, AC7) — dwukierunkowy JavaScript bridge Flutter <-> Angular.
///
/// Kierunki komunikacji:
/// - Flutter -> Angular: wykonanie skryptu wywołującego `window.testgenBridge`
///   (rejestrowany przez `FlutterBridgeService` po stronie Angulara).
/// - Angular -> Flutter: `window.flutter_bridge.postMessage(json)` (kanał
///   JavaScript na iOS/Android) lub `window.chrome.webview.postMessage(json)`
///   (Edge WebView2 na Windows).

/// Nazwa kanału JavaScript rejestrowanego w WebView (iOS/Android).
const String kBridgeChannelName = 'flutter_bridge';

/// Funkcja wykonująca JavaScript w aktywnym WebView.
typedef JavaScriptRunner = Future<void> Function(String script);

/// Handler wiadomości przychodzących z Angulara.
typedef BridgeMessageHandler = void Function(BridgeMessage message);

/// Wiadomość bridge'a — JSON `{"type": "...", "payload": {...}}`.
class BridgeMessage {
  const BridgeMessage({required this.type, this.payload = const {}});

  final String type;
  final Map<String, dynamic> payload;

  /// Dekoduje wiadomość z JSON; zwraca `null` dla nieprawidłowego formatu.
  static BridgeMessage? tryParse(String source) {
    try {
      final decoded = jsonDecode(source);
      if (decoded is! Map<String, dynamic>) return null;
      final type = decoded['type'];
      if (type is! String || type.isEmpty) return null;
      final payload = decoded['payload'];
      return BridgeMessage(
        type: type,
        payload: payload is Map<String, dynamic> ? payload : const {},
      );
    } on FormatException {
      return null;
    }
  }

  String toJson() => jsonEncode({'type': type, 'payload': payload});
}

/// Dwukierunkowy bridge — niezależny od implementacji WebView
/// (webview_flutter / webview_windows) dzięki wstrzykniętemu [JavaScriptRunner].
class JsBridge {
  JsBridge({required JavaScriptRunner runJavaScript, this.onMessage})
      : _runJavaScript = runJavaScript;

  final JavaScriptRunner _runJavaScript;
  final BridgeMessageHandler? onMessage;

  /// Skrypt nawigacji wykonywany po stronie Angulara.
  static String navigationScript(String path) =>
      'window.testgenBridge && window.testgenBridge.navigateTo(${jsonEncode(path)});';

  /// Skrypt przekazujący dane powiadomienia do Angulara.
  static String notificationScript(Map<String, dynamic> data) =>
      'window.testgenBridge && window.testgenBridge.receiveNotification(${jsonEncode(data)});';

  /// Skrypt przekazujący informacje o urządzeniu (odpowiedź na `getDeviceInfo`).
  static String deviceInfoScript(Map<String, dynamic> info) =>
      'window.testgenBridge && window.testgenBridge.setDeviceInfo(${jsonEncode(info)});';

  /// AC5 — nawigacja deep linka w aplikacji Angular.
  Future<void> navigateTo(String path) => _runJavaScript(navigationScript(path));

  /// AC7 — przekazanie danych powiadomienia push.
  Future<void> sendNotification(Map<String, dynamic> data) =>
      _runJavaScript(notificationScript(data));

  /// Odpowiedź na żądanie `getDeviceInfo` z Angulara.
  Future<void> sendDeviceInfo(Map<String, dynamic> info) =>
      _runJavaScript(deviceInfoScript(info));

  /// Obsługa surowej wiadomości z Angulara (JavaScriptChannel / WebMessage).
  void handleRawMessage(String raw) {
    final message = BridgeMessage.tryParse(raw);
    if (message == null) return;
    onMessage?.call(message);
  }
}
