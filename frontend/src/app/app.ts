import { Component, inject, signal } from "@angular/core";
import { RouterOutlet } from "@angular/router";
import { AccessibilityToolbarComponent } from "./shared/components/accessibility-toolbar/accessibility-toolbar.component";
import { ChatbotComponent } from "./shared/components/chatbot/chatbot.component";
import { FeatureLockedBannerComponent } from "./shared/components/feature-locked-banner/feature-locked-banner.component";
import { QuotaExceededBannerComponent } from "./shared/components/quota-exceeded-banner/quota-exceeded-banner.component";
import { FlutterBridgeService } from "./shared/services/flutter-bridge.service";
import { ThemeService } from "./shared/services/theme.service";

@Component({
  selector: "app-root",
  imports: [
    RouterOutlet,
    AccessibilityToolbarComponent,
    ChatbotComponent,
    QuotaExceededBannerComponent,
    FeatureLockedBannerComponent,
  ],
  template: `
    <a class="skip-link" href="#main-content">Przejdź do treści głównej</a>
    <app-quota-exceeded-banner />
    <app-feature-locked-banner />
    <router-outlet />
    <app-accessibility-toolbar />
    <app-chatbot />
  `,
  styles: [],
})
export class App {
  protected readonly title = signal("frontend");

  constructor() {
    // Story 6.10 — inicjalizacja motywów dostępności
    // (localStorage + preferencje systemowe) przy starcie aplikacji.
    inject(ThemeService).initialize();
    // Story 6.12 — rejestracja mostka dla shellu Flutter (window.testgenBridge);
    // no-op w zwykłej przeglądarce.
    inject(FlutterBridgeService).initialize();
  }
}
