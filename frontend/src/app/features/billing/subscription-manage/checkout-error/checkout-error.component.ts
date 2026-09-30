import { Component } from "@angular/core";
import { MatButton } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { RouterLink } from "@angular/router";

/**
 * Strona powrotu tpay po rezygnacji/błędzie płatności (Story 7.4, AC6).
 *
 * Tenant zachowuje dotychczasowy plan z jego limitami i może ponowić
 * checkout — transakcje nieopłacone w tpay po prostu wygasają (nie
 * generują notyfikacji błędu), rekord pozostaje `pending`.
 */
@Component({
  selector: "app-checkout-error",
  imports: [MatCardModule, MatButton, RouterLink],
  templateUrl: "./checkout-error.component.html",
  styleUrl: "./checkout-error.component.scss",
})
export class CheckoutErrorComponent {}
