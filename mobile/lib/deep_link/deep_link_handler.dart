import 'dart:async';

import 'package:app_links/app_links.dart';

/// Story 6.12 (AC5) — obsługa deep linków `testgen://`.
///
/// Schemat URL zarejestrowany w AndroidManifest.xml (intent-filter) oraz
/// ios/Runner/Info.plist (CFBundleURLTypes). Linki są tłumaczone na ścieżki
/// aplikacji Angular i przekazywane do WebView przez JS bridge.
class DeepLinkHandler {
  DeepLinkHandler({AppLinks? appLinks}) : _appLinks = appLinks ?? AppLinks();

  final AppLinks _appLinks;
  StreamSubscription<Uri>? _subscription;

  /// Schemat deep linków aplikacji.
  static const String scheme = 'testgen';

  /// Dozwolone korzenie ścieżek (`/projects/:id`, `/analysis/:id`,
  /// `/reports/:id`, `/dashboard`).
  static const Set<String> allowedRoots = {
    'projects',
    'analysis',
    'reports',
    'dashboard',
  };

  /// Tłumaczy deep link na ścieżkę Angulara.
  ///
  /// `testgen://analysis/123` -> `/analysis/123`
  /// `testgen://projects/42/upload` -> `/projects/42/upload`
  ///
  /// Zwraca `null` dla nieobsługiwanego schematu lub korzenia ścieżki.
  static String? parse(Uri uri) {
    if (uri.scheme != scheme) return null;
    final segments = <String>[
      if (uri.host.isNotEmpty) uri.host,
      ...uri.pathSegments.where((s) => s.isNotEmpty),
    ];
    if (segments.isEmpty || !allowedRoots.contains(segments.first)) {
      return null;
    }
    final path = '/${segments.join('/')}';
    return uri.hasQuery ? '$path?${uri.query}' : path;
  }

  /// Nasłuchuje deep linków: link startowy (zimny start) + strumień linków
  /// przy działającej aplikacji. Poprawne linki trafiają do [onPath].
  Future<void> init(void Function(String path) onPath) async {
    final initial = await _appLinks.getInitialLink();
    if (initial != null) {
      final path = parse(initial);
      if (path != null) onPath(path);
    }
    _subscription = _appLinks.uriLinkStream.listen((uri) {
      final path = parse(uri);
      if (path != null) onPath(path);
    });
  }

  void dispose() {
    _subscription?.cancel();
    _subscription = null;
  }
}
