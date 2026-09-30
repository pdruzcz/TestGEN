import { expect, test } from "./fixtures/test-fixtures";
import { LoginPage, RegisterPage } from "./pages/auth.page";
import { DashboardPage } from "./pages/dashboard.page";

/**
 * Story 6.13, AC1 — pełny user journey: rejestracja, logowanie, wylogowanie.
 * Backend zamockowany przez page.route() (patrz fixtures/test-fixtures.ts).
 */
test.describe("AC1 — autentykacja", () => {
  test("rejestracja poprawna — pokazuje ekran potwierdzenia email", async ({
    page,
    mockApi,
  }) => {
    await mockApi.mock(
      "**/api/v1/auth/register",
      {
        email: "nowy@firma.pl",
        message: "Sprawdź swoją skrzynkę email, aby potwierdzić rejestrację.",
      },
      { method: "POST", status: 201 },
    );

    const registerPage = new RegisterPage(page);
    await registerPage.goto();
    await expect(registerPage.heading).toBeVisible();

    await registerPage.register({
      email: "nowy@firma.pl",
      password: "BezpieczneHaslo1!",
      companyName: "Firma Testowa Sp. z o.o.",
      nip: "1234567890",
    });

    // Sukces — baner z instrukcją weryfikacji email (register.component.ts)
    await expect(
      page.getByRole("heading", { name: "Sprawdź swoją skrzynkę email" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Przejdź do logowania" }),
    ).toBeVisible();
  });

  test("rejestracja z błędem (email zajęty — 409) — komunikat błędu PL", async ({
    page,
    mockApi,
  }) => {
    // [~] deviation: komponent rejestracji pokazuje generyczny komunikat
    // "Wystąpił błąd rejestracji. Spróbuj ponownie." dla każdego błędu HTTP
    // (brak dedykowanego tekstu "email zajęty" w realnym szablonie).
    await mockApi.mock(
      "**/api/v1/auth/register",
      { detail: "Email already registered" },
      { method: "POST", status: 409 },
    );

    const registerPage = new RegisterPage(page);
    await registerPage.goto();
    await registerPage.register({
      email: "zajety@firma.pl",
      password: "BezpieczneHaslo1!",
      companyName: "Firma Testowa",
    });

    await expect(registerPage.errorBanner).toContainText(
      "Wystąpił błąd rejestracji. Spróbuj ponownie.",
    );
  });

  test("logowanie poprawne — redirect na /dashboard i powitanie", async ({
    page,
    mockApi,
  }) => {
    await mockApi.mockLoginSuccess();
    await mockApi.mockDashboard();

    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await expect(loginPage.heading).toBeVisible();

    await loginPage.login("jan.kowalski@example.com", "BezpieczneHaslo1!");

    await expect(page).toHaveURL(/\/dashboard$/);
    // Powitanie z imieniem z profilu (GET /users/me)
    await expect(
      page.getByRole("heading", { name: "Witaj, Jan" }),
    ).toBeVisible();
  });

  test("logowanie ze złym hasłem — komunikat 'Nieprawidłowy email lub hasło'", async ({
    page,
    mockApi,
  }) => {
    await mockApi.mock(
      "**/api/v1/auth/login",
      { detail: "Invalid credentials" },
      { method: "POST", status: 401 },
    );

    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login("jan.kowalski@example.com", "zle-haslo");

    await expect(loginPage.errorBanner).toContainText(
      "Nieprawidłowy email lub hasło",
    );
    // Pozostajemy na stronie logowania
    await expect(page).toHaveURL(/\/login$/);
  });

  test("wylogowanie — powrót na stronę logowania", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDashboard();
    await mockApi.mock(
      "**/api/v1/auth/logout",
      { message: "Wylogowano" },
      { method: "POST" },
    );

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(dashboardPage.welcomeTitle).toBeVisible();

    await dashboardPage.logoutButton.click();

    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Logowanie" }),
    ).toBeVisible();
  });

  test("odzyskiwanie hasła — link 'Nie pamiętasz hasła?' prowadzi na /reset-password", async ({
    page,
    mockApi,
  }) => {
    void mockApi; // fallback 404 wystarcza — strona resetu nie woła API na starcie

    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.forgotPasswordLink.click();

    await expect(page).toHaveURL(/\/reset-password$/);
  });
});
