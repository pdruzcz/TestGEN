import { Locator, Page } from "@playwright/test";

/**
 * Page Object — /login (login.component.ts).
 * Lokatory oparte o role/aria-label/teksty PL z realnego szablonu.
 */
export class LoginPage {
  readonly heading: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorBanner: Locator;
  readonly forgotPasswordLink: Locator;
  readonly registerLink: Locator;

  constructor(readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "Logowanie" });
    this.emailInput = page.getByLabel("Adres email", { exact: true });
    this.passwordInput = page.getByLabel("Hasło", { exact: true });
    this.submitButton = page.getByRole("button", { name: "Zaloguj się" });
    this.errorBanner = page.getByRole("alert");
    this.forgotPasswordLink = page.getByRole("link", {
      name: "Nie pamiętasz hasła?",
    });
    this.registerLink = page.getByRole("link", { name: "Zarejestruj się" });
  }

  async goto(): Promise<void> {
    await this.page.goto("/login");
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}

/**
 * Page Object — /register (register.component.ts).
 */
export class RegisterPage {
  readonly heading: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly confirmPasswordInput: Locator;
  readonly companyNameInput: Locator;
  readonly nipInput: Locator;
  readonly submitButton: Locator;
  readonly errorBanner: Locator;
  readonly successBanner: Locator;

  constructor(readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "Rejestracja" });
    this.emailInput = page.getByLabel("Adres email firmowy", { exact: true });
    this.passwordInput = page.getByLabel("Hasło", { exact: true });
    this.confirmPasswordInput = page.getByLabel("Potwierdź hasło", {
      exact: true,
    });
    this.companyNameInput = page.getByLabel("Nazwa firmy", { exact: true });
    this.nipInput = page.getByLabel("NIP", { exact: true });
    this.submitButton = page.getByRole("button", { name: "Zarejestruj się" });
    this.errorBanner = page.getByRole("alert");
    // Baner sukcesu ma role="status" i nagłówek "Sprawdź swoją skrzynkę email"
    this.successBanner = page.getByRole("status");
  }

  async goto(): Promise<void> {
    await this.page.goto("/register");
  }

  async register(data: {
    email: string;
    password: string;
    companyName: string;
    nip?: string;
  }): Promise<void> {
    await this.emailInput.fill(data.email);
    await this.passwordInput.fill(data.password);
    await this.confirmPasswordInput.fill(data.password);
    await this.companyNameInput.fill(data.companyName);
    if (data.nip) {
      await this.nipInput.fill(data.nip);
    }
    await this.submitButton.click();
  }
}
