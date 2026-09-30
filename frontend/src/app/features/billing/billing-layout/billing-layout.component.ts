import { Component } from "@angular/core";
import { RouterOutlet } from "@angular/router";

import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";

/**
 * Powłoka stron billingowych (E7) — navbar z aktywną pozycją „Rozliczenia"
 * oraz stopka wokół wspólnego `<router-outlet/>` (wzór: powłoka panelu
 * admina 6.15). Strony potomne (plans/checkout/payment-methods/invoices/
 * invoice-data/usage) są dziećmi tej trasy w `billing.routes.ts`.
 */
@Component({
  selector: "app-billing-layout",
  imports: [RouterOutlet, NavbarComponent, FooterComponent],
  template: `
    <div class="billing-page">
      <app-navbar activeLink="billing" />

      <main class="content" id="main-content" tabindex="-1">
        <router-outlet />
      </main>

      <app-footer />
    </div>
  `,
  styles: [
    `
      .billing-page {
        min-height: 100vh;
        background: #f7f8fa;
        display: flex;
        flex-direction: column;
      }

      .content {
        flex: 1;
      }
    `,
  ],
})
export class BillingLayoutComponent {}
