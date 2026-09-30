import { TestBed } from "@angular/core/testing";
import { Router, provideRouter } from "@angular/router";
import { FlutterBridgeService } from "./flutter-bridge.service";

interface TestWindow extends Window {
  flutter_bridge?: { postMessage(message: string): void };
  testgenBridge?: {
    navigateTo(url: string): void;
    receiveNotification(data: Record<string, unknown>): void;
    setDeviceInfo(info: Record<string, unknown>): void;
  };
}

const testWindow = window as TestWindow;

describe("FlutterBridgeService", () => {
  let service: FlutterBridgeService;
  let router: Router;

  beforeEach(() => {
    delete testWindow.flutter_bridge;
    delete testWindow.testgenBridge;
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    service = TestBed.inject(FlutterBridgeService);
    router = TestBed.inject(Router);
    vi.spyOn(router, "navigateByUrl").mockResolvedValue(true);
  });

  afterEach(() => {
    delete testWindow.flutter_bridge;
    delete testWindow.testgenBridge;
  });

  it("isFlutterEnvironment wykrywa kanał flutter_bridge", () => {
    expect(service.isFlutterEnvironment()).toBe(false);
    testWindow.flutter_bridge = { postMessage: () => undefined };
    expect(service.isFlutterEnvironment()).toBe(true);
  });

  it("initialize rejestruje window.testgenBridge (AC5)", () => {
    service.initialize();
    expect(testWindow.testgenBridge).toBeDefined();

    testWindow.testgenBridge!.navigateTo("/analysis/123");
    expect(router.navigateByUrl).toHaveBeenCalledWith("/analysis/123");
  });

  it("receiveNotification zapisuje dane i nawiguje do deep linka (AC7)", () => {
    service.initialize();
    testWindow.testgenBridge!.receiveNotification({ deepLink: "/reports/7" });

    expect(service.lastNotificationSignal()).toEqual({
      deepLink: "/reports/7",
    });
    expect(router.navigateByUrl).toHaveBeenCalledWith("/reports/7");
  });

  it("setDeviceInfo aktualizuje deviceInfoSignal", () => {
    service.initialize();
    testWindow.testgenBridge!.setDeviceInfo({ platform: "android" });
    expect(service.deviceInfoSignal()).toEqual({ platform: "android" });
  });

  it("getDeviceInfo wysyła wiadomość do kanału Fluttera", () => {
    const posted: string[] = [];
    testWindow.flutter_bridge = {
      postMessage: (message: string) => posted.push(message),
    };

    service.getDeviceInfo();

    expect(posted).toEqual([
      JSON.stringify({ type: "getDeviceInfo", payload: {} }),
    ]);
  });

  it("postMessage jest no-op w zwykłej przeglądarce", () => {
    expect(() =>
      service.postMessage({ type: "share", payload: { url: "/x" } }),
    ).not.toThrow();
  });
});
