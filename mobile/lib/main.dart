import 'package:flutter/material.dart';

import 'webview/webview_container.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TestGENApp());
}

class TestGENApp extends StatelessWidget {
  const TestGENApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TestGEN',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF1A1A2E),
        useMaterial3: true,
      ),
      home: const WebViewContainer(),
    );
  }
}
