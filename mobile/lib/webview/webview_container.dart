import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_windows/webview_windows.dart' as windows;

import '../bridge/js_bridge.dart';
import '../config.dart';
import '../deep_link/deep_link_handler.dart';
import '../notifications/notification_handler.dart';
import '../widgets/offline_message.dart';

/// Story 6.12 (AC1–AC4) — kontener WebView dobierający implementację
/// do platformy:
/// - iOS (WKWebView) i Android (WebView) — `webview_flutter`,
/// - Windows (Edge WebView2) — `webview_windows`,
/// - Linux — fallback do przeglądarki systemowej (brak stabilnego pluginu
///   WebKitGTK dla webview_flutter; patrz README).
class WebViewContainer extends StatelessWidget {
  const WebViewContainer({super.key});

  @override
  Widget build(BuildContext context) {
    switch (defaultTargetPlatform) {
      case TargetPlatform.windows:
        return const WindowsWebView();
      case TargetPlatform.linux:
        return const LinuxBrowserFallback();
      case TargetPlatform.android:
      case TargetPlatform.iOS:
      default:
        return const MobileWebView();
    }
  }
}

/// Wspólna obsługa wiadomości Angular -> Flutter (AC5/AC7 + device info).
Future<void> handleBridgeMessage(
  BridgeMessage message,
  JsBridge bridge,
) async {
  switch (message.type) {
    case 'getDeviceInfo':
      await bridge.sendDeviceInfo({
        'platform': defaultTargetPlatform.name,
        'operatingSystem': Platform.operatingSystem,
        'operatingSystemVersion': Platform.operatingSystemVersion,
        'appName': 'TestGEN',
      });
    case 'openExternal':
      final url = message.payload['url'];
      if (url is String) {
        final uri = Uri.tryParse(url);
        if (uri != null && (uri.scheme == 'https' || uri.scheme == 'http')) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      }
    case 'share':
      // Udostępnianie natywne wymaga dodatkowego pluginu (share_plus) —
      // poza zakresem zależności story; protokół bridge'a jest gotowy.
      debugPrint('Bridge share: ${message.payload}');
    default:
      debugPrint('Nieznany typ wiadomości bridge: ${message.type}');
  }
}

/// iOS/Android — WKWebView / Android WebView przez `webview_flutter`.
class MobileWebView extends StatefulWidget {
  const MobileWebView({super.key});

  @override
  State<MobileWebView> createState() => _MobileWebViewState();
}

class _MobileWebViewState extends State<MobileWebView> {
  late final WebViewController _controller;
  late final JsBridge _bridge;
  late final DeepLinkHandler _deepLinks;
  late final NotificationHandler _notifications;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    _bridge = JsBridge(
      runJavaScript: (script) => _controller.runJavaScript(script),
      onMessage: (message) => handleBridgeMessage(message, _bridge),
    );
    _notifications = NotificationHandler(onNavigate: _bridge.navigateTo);
    _controller = WebViewController()
      // JavaScript + localStorage wymagane przez aplikację Angular;
      // cookies (HttpOnly JWT) obsługiwane natywnie przez WKWebView/WebView.
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..addJavaScriptChannel(
        kBridgeChannelName,
        onMessageReceived: (msg) => _bridge.handleRawMessage(msg.message),
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (_offline && mounted) setState(() => _offline = false);
          },
          onWebResourceError: (error) {
            // AC6 — tylko błędy głównej ramki oznaczają brak połączenia.
            if (error.isForMainFrame ?? true) {
              if (mounted) setState(() => _offline = true);
            }
          },
        ),
      )
      ..loadRequest(Uri.parse(AppConfig.baseUrl));
    _deepLinks = DeepLinkHandler();
    _deepLinks.init(_bridge.navigateTo);
  }

  @override
  void dispose() {
    _deepLinks.dispose();
    super.dispose();
  }

  void _retry() {
    setState(() => _offline = false);
    _controller.loadRequest(Uri.parse(AppConfig.baseUrl));
  }

  /// Publiczny punkt wejścia dla warstwy powiadomień (FCM onMessageOpenedApp).
  NotificationHandler get notifications => _notifications;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            WebViewWidget(controller: _controller),
            if (_offline) Positioned.fill(child: OfflineMessage(onRetry: _retry)),
          ],
        ),
      ),
    );
  }
}

/// Windows — Edge WebView2 przez `webview_windows`.
class WindowsWebView extends StatefulWidget {
  const WindowsWebView({super.key});

  @override
  State<WindowsWebView> createState() => _WindowsWebViewState();
}

class _WindowsWebViewState extends State<WindowsWebView> {
  final windows.WebviewController _controller = windows.WebviewController();
  late final JsBridge _bridge;
  bool _initialized = false;
  bool _offline = false;

  @override
  void initState() {
    super.initState();
    _bridge = JsBridge(
      runJavaScript: (script) => _controller.executeScript(script),
      onMessage: (message) => handleBridgeMessage(message, _bridge),
    );
    _init();
  }

  Future<void> _init() async {
    try {
      await _controller.initialize();
      // Angular -> Flutter na Windows: window.chrome.webview.postMessage(json).
      _controller.webMessage.listen((dynamic message) {
        final raw = message is String ? message : jsonEncode(message);
        _bridge.handleRawMessage(raw);
      });
      await _controller.loadUrl(AppConfig.baseUrl);
      if (mounted) setState(() => _initialized = true);
    } catch (e) {
      debugPrint('Błąd inicjalizacji WebView2: $e');
      if (mounted) setState(() => _offline = true);
    }
  }

  Future<void> _retry() async {
    setState(() => _offline = false);
    if (_initialized) {
      await _controller.loadUrl(AppConfig.baseUrl);
    } else {
      await _init();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          if (_initialized)
            windows.Webview(_controller)
          else if (!_offline)
            const Center(child: CircularProgressIndicator()),
          if (_offline) Positioned.fill(child: OfflineMessage(onRetry: _retry)),
        ],
      ),
    );
  }
}

/// Linux — brak stabilnego WebView (WebKitGTK) w webview_flutter;
/// fallback otwiera aplikację w przeglądarce systemowej.
class LinuxBrowserFallback extends StatelessWidget {
  const LinuxBrowserFallback({super.key});

  static const String message =
      'Wersja dla systemu Linux otwiera TestGEN w przeglądarce systemowej.';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.public, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => launchUrl(
                  Uri.parse(AppConfig.baseUrl),
                  mode: LaunchMode.externalApplication,
                ),
                icon: const Icon(Icons.open_in_browser),
                label: const Text('Otwórz TestGEN'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
