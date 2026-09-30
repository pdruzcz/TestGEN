import { Injectable, NgZone, inject, signal } from "@angular/core";
import { Router } from "@angular/router";

/**
 * Story 6.12 (AC5, AC7) — mostek Angular <-> Flutter WebView shell.
 *
 * Kierunki komunikacji:
 * - Angular -> Flutter: `window.flutter_bridge.postMessage(json)`
 *   (JavaScriptChannel na iOS/Android) lub
 *   `window.chrome.webview.postMessage(json)` (Edge WebView2 na Windows).
 * - Flutter -> Angular: Flutter wykonuje skrypt wywołujący
 *   `window.testgenBridge.*` (rejestrowane w `initialize()`).
 *
 * W zwykłej przeglądarce wszystkie metody są no-op (brak kanałów Fluttera).
 */

/** Wiadomość Angular -> Flutter: `{"type": "...", "payload": {...}}`. */
export interface FlutterBridgeMessage {
  type: string;
  payload?: Record<string, unknown>;
}

/** Payload powiadomienia push przekazany z Fluttera (AC7). */
export interface FlutterNotificationData {
  deepLink?: string;
  [key: string]: unknown;
}

interface BridgeChannel {
  postMessage(message: string): void;
}

interface FlutterHostWindow extends Window {
  flutter_bridge?: BridgeChannel;
  chrome?: { webview?: BridgeChannel };
  testgenBridge?: {
    navigateTo(url: string): void;
    receiveNotification(data: FlutterNotificationData): void;
    setDeviceInfo(info: Record<string, unknown>): void;
  };
}

@Injectable({ providedIn: "root" })
export class FlutterBridgeService {
  private readonly router = inject(Router);
  private readonly zone = inject(NgZone);

  /** Informacje o urządzeniu przekazane przez Fluttera (odpowiedź na getDeviceInfo). */
  readonly deviceInfoSignal = signal<Record<string, unknown> | null>(null);

  /** Ostatnie powiadomienie push przekazane przez Fluttera. */
  readonly lastNotificationSignal = signal<FlutterNotificationData | null>(
    null,
  );

  private get hostWindow(): FlutterHostWindow | null {
    return typeof window === "undefined"
      ? null
      : (window as FlutterHostWindow);
  }

  /** Czy aplikacja działa wewnątrz shellu Flutter (mobile lub Windows). */
  isFlutterEnvironment(): boolean {
    const w = this.hostWindow;
    return !!(w && (w.flutter_bridge || w.chrome?.webview));
  }

  /**
   * Rejestruje `window.testgenBridge` — punkt wejścia dla skryptów
   * wykonywanych przez Fluttera. Bezpieczne w przeglądarce (obiekt jest
   * nieużywany, gdy nie ma shellu).
   */
  initialize(): void {
    const w = this.hostWindow;
    if (!w) return;
    w.testgenBridge = {
      navigateTo: (url: string) => this.navigateTo(url),
      receiveNotification: (data: FlutterNotificationData) =>
        this.receiveNotification(data),
      setDeviceInfo: (info: Record<string, unknown>) =>
        this.zone.run(() => this.deviceInfoSignal.set(info)),
    };
  }

  /** AC5 — nawigacja wywołana przez Fluttera (deep link testgen://...). */
  navigateTo(url: string): void {
    this.zone.run(() => void this.router.navigateByUrl(url));
  }

  /** AC7 — powiadomienie push: zapis + nawigacja do deep linka (jeśli jest). */
  receiveNotification(data: FlutterNotificationData): void {
    this.zone.run(() => {
      this.lastNotificationSignal.set(data);
      if (typeof data.deepLink === "string" && data.deepLink.startsWith("/")) {
        void this.router.navigateByUrl(data.deepLink);
      }
    });
  }

  /** Prośba o informacje o urządzeniu — Flutter odpowiada przez setDeviceInfo. */
  getDeviceInfo(): void {
    this.postMessage({ type: "getDeviceInfo" });
  }

  /** Otwarcie linku w zewnętrznej przeglądarce/aplikacji systemowej. */
  openExternal(url: string): void {
    this.postMessage({ type: "openExternal", payload: { url } });
  }

  /** Udostępnianie natywne (protokół gotowy po stronie shellu). */
  share(payload: Record<string, unknown>): void {
    this.postMessage({ type: "share", payload });
  }

  /** Wysyłka wiadomości do Fluttera; no-op poza shellem. */
  postMessage(message: FlutterBridgeMessage): void {
    const w = this.hostWindow;
    if (!w) return;
    const channel = w.flutter_bridge ?? w.chrome?.webview;
    if (!channel) return;
    channel.postMessage(
      JSON.stringify({ type: message.type, payload: message.payload ?? {} }),
    );
  }
}
