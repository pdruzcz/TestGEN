import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { AdminComponent } from "./admin.component";
import { ADMIN_ROUTES } from "./admin.routes";

describe("AdminComponent", () => {
  let fixture: ComponentFixture<AdminComponent>;
  let component: AdminComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("tworzy się poprawnie", () => {
    expect(component).toBeTruthy();
  });

  it("udostępnia cztery sekcje nawigacji", () => {
    expect(component.navItems.map((item) => item.path)).toEqual([
      "users",
      "tenants",
      "audit-log",
      "config",
    ]);
  });

  it("opisuje sekcje po polsku", () => {
    expect(component.navItems.map((item) => item.label)).toEqual([
      "Użytkownicy",
      "Tenanci",
      "Log audytu",
      "Konfiguracja",
    ]);
  });

  it("renderuje linki nawigacji z ikonami", () => {
    const links: HTMLElement[] = Array.from(
      fixture.nativeElement.querySelectorAll("nav a"),
    );

    expect(links.length).toBe(4);
    expect(links[0].textContent).toContain("Użytkownicy");
    expect(fixture.nativeElement.querySelectorAll("nav mat-icon").length).toBe(4);
  });

  it("oznacza obszar nawigacji etykietą dostępności", () => {
    const nav: HTMLElement = fixture.nativeElement.querySelector("nav");

    expect(nav.getAttribute("aria-label")).toBe("Sekcje panelu administracyjnego");
  });
});

describe("ADMIN_ROUTES", () => {
  it("przekierowuje trasę domyślną na listę użytkowników", () => {
    const root = ADMIN_ROUTES[0];

    expect(root.children?.[0]).toMatchObject({
      path: "",
      redirectTo: "users",
      pathMatch: "full",
    });
  });

  it("definiuje leniwe trasy dla wszystkich sekcji", () => {
    const paths = ADMIN_ROUTES[0].children?.map((child) => child.path);

    expect(paths).toEqual(["", "users", "tenants", "audit-log", "config"]);
  });

  it("każda sekcja ma tytuł strony", () => {
    const sections = ADMIN_ROUTES[0].children?.filter((child) => child.path !== "");

    expect(sections?.every((child) => typeof child.title === "string")).toBe(true);
  });
});
