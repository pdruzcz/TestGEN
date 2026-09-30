import 'package:flutter_test/flutter_test.dart';
import 'package:testgen_mobile/bridge/js_bridge.dart';

void main() {
  group('BridgeMessage', () {
    test('tryParse dekoduje poprawną wiadomość', () {
      final msg = BridgeMessage.tryParse(
        '{"type":"getDeviceInfo","payload":{"requestId":1}}',
      );
      expect(msg, isNotNull);
      expect(msg!.type, 'getDeviceInfo');
      expect(msg.payload['requestId'], 1);
    });

    test('tryParse zwraca null dla nieprawidłowego JSON', () {
      expect(BridgeMessage.tryParse('nie-json'), isNull);
      expect(BridgeMessage.tryParse('[1,2,3]'), isNull);
      expect(BridgeMessage.tryParse('{"payload":{}}'), isNull);
      expect(BridgeMessage.tryParse('{"type":""}'), isNull);
    });

    test('toJson serializuje typ i payload', () {
      const msg = BridgeMessage(type: 'share', payload: {'url': '/x'});
      expect(msg.toJson(), '{"type":"share","payload":{"url":"/x"}}');
    });
  });

  group('JsBridge', () {
    test('navigationScript wywołuje testgenBridge.navigateTo z escapowaną ścieżką',
        () {
      expect(
        JsBridge.navigationScript('/analysis/123'),
        'window.testgenBridge && window.testgenBridge.navigateTo("/analysis/123");',
      );
    });

    test('navigateTo wykonuje skrypt przez runner', () async {
      final executed = <String>[];
      final bridge = JsBridge(
        runJavaScript: (script) async => executed.add(script),
      );
      await bridge.navigateTo('/projects/42');
      expect(executed, hasLength(1));
      expect(executed.single, contains('navigateTo("/projects/42")'));
    });

    test('sendDeviceInfo serializuje obiekt info', () async {
      final executed = <String>[];
      final bridge = JsBridge(
        runJavaScript: (script) async => executed.add(script),
      );
      await bridge.sendDeviceInfo({'platform': 'android'});
      expect(executed.single, contains('setDeviceInfo({"platform":"android"})'));
    });

    test('handleRawMessage przekazuje poprawne wiadomości do handlera', () {
      final received = <BridgeMessage>[];
      final bridge = JsBridge(
        runJavaScript: (_) async {},
        onMessage: received.add,
      );
      bridge.handleRawMessage('{"type":"openExternal","payload":{"url":"https://x"}}');
      bridge.handleRawMessage('zepsuty json');
      expect(received, hasLength(1));
      expect(received.single.type, 'openExternal');
    });
  });
}
