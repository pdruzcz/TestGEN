class AppConfig {
  static const String devUrl = 'http://localhost:4200';

  /// URL serwera dla buildów release — wybierany przy budowie (--dart-define):
  ///   produkcja (domyślne, realny tpay):
  ///     flutter build apk --release
  ///   środowisko TESTOWE (tpay sandbox):
  ///     flutter build apk --release --dart-define=TESTGEN_URL=https://testgen.nexio.pl
  static const String prodUrl = String.fromEnvironment(
    'TESTGEN_URL',
    defaultValue: 'https://test-gen.pl',
  );

  static const bool isProduction = bool.fromEnvironment('dart.vm.product');

  static String get baseUrl => isProduction ? prodUrl : devUrl;
}
