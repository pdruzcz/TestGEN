import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { signal } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";

import { AuthService } from "../../../core/services/auth.service";
import { environment } from "../../../../environments/environment";
import { AppNotification } from "../../services/notification.service";
import { NotificationBellComponent } from "./notification-bell.component";

function makeNotification(
  overrides: Partial<AppNotification> = {},
): AppNotification {
  return {
    id: "n-1",
    type: "limit_warning",
    severity: "warning",
    title: "Zbliżasz się do limitu analiz",
    message: "Wykorzystujesz 80% limitu zasobu analiz.",
    resourceType: "analyses",
    currentValue: 8,
    limitValue: 10,
    percentage: 80,
    thresholdPercentage: 80,
    isRead: false,
    ctaUrl: "/billing/plans",
    createdAt: "2026-09-10T12:00:00Z",
    ...overrides,
  };
}

describe("NotificationBellComponent (Story 7.11, AC3)", () => {
  let fixture: ComponentFixture<NotificationBellComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotificationBellComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        NoopAnimationsModule,
        // Gate pollingu na zalogowanym użytkowniku — mock auth (Story 7.11).
        {
          provide: AuthService,
          useValue: {
            currentUserSignal: signal({ id: "u1", name: "Owner" }),
            isAuthenticatedSignal: signal(true),
          },
        },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(NotificationBellComponent);
    fixture.detectChanges();
  });

  afterEach(() => httpMock.verify());

  async function flushUnread(count: number): Promise<void> {
    // toObservable emituje asynchronicznie — czekamy na pierwszy timer(0).
    await new Promise((resolve) => setTimeout(resolve, 10));
    const req = httpMock.expectOne(
      `${environment.apiUrl}/notifications/unread-count`,
    );
    expect(req.request.method).toBe("GET");
    req.flush({ count });
    fixture.detectChanges();
  }

  async function openDropdown(): Promise<void> {
    await flushUnread(2);
    const button = fixture.nativeElement.querySelector(
      ".bell-button",
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
  }

  function flushList(items: AppNotification[]): void {
    const req = httpMock.expectOne(
      `${environment.apiUrl}/notifications?page=1&size=20`,
    );
    expect(req.request.method).toBe("GET");
    req.flush({ items, total: items.length, page: 1, size: 20 });
    fixture.detectChanges();
  }

  it("badge pokazuje liczbę nieprzeczytanych (polling unread-count)", async () => {
    await flushUnread(3);

    const badge = fixture.nativeElement.querySelector(".bell-badge");
    expect(badge.textContent.trim()).toBe("3");
  });

  it("bez nieprzeczytanych brak badge, aria-label bez licznika", async () => {
    await flushUnread(0);

    expect(fixture.nativeElement.querySelector(".bell-badge")).toBeNull();
    const button = fixture.nativeElement.querySelector(".bell-button");
    expect(button.getAttribute("aria-label")).toBe("Powiadomienia");
  });

  it("klik otwiera dropdown z listą powiadomień", async () => {
    await openDropdown();
    flushList([makeNotification()]);

    const dropdown = fixture.nativeElement.querySelector(".bell-dropdown");
    expect(dropdown).toBeTruthy();
    const text = dropdown.textContent;
    expect(text).toContain("Zbliżasz się do limitu analiz");
    expect(text).toContain("Wykorzystujesz 80% limitu");
    expect(text).toContain("10.09.2026");
  });

  it("ikona koloru progu: 80 żółty, 90 pomarańczowy, 100 czerwony", async () => {
    await openDropdown();
    flushList([
      makeNotification({ id: "n-80", thresholdPercentage: 80 }),
      makeNotification({ id: "n-90", thresholdPercentage: 90 }),
      makeNotification({
        id: "n-100",
        thresholdPercentage: 100,
        severity: "critical",
        title: "Limit analiz osiągnięty",
      }),
    ]);

    const dots = fixture.nativeElement.querySelectorAll(".severity-dot");
    expect(dots[0].className).toContain("medium");
    expect(dots[1].className).toContain("high");
    expect(dots[2].className).toContain("critical");
  });

  it("link do szczegółów prowadzi do /billing/plans", async () => {
    await openDropdown();
    flushList([makeNotification()]);

    const link = fixture.nativeElement.querySelector(".item-link");
    expect(link.getAttribute("href")).toBe("/billing/plans");
  });

  it("oznacz pojedyncze jako przeczytane dekrementuje badge", async () => {
    await openDropdown();
    flushList([makeNotification()]);

    const markButton = fixture.nativeElement.querySelector(
      ".mark-read",
    ) as HTMLButtonElement;
    markButton.click();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/notifications/n-1/read`,
    );
    expect(req.request.method).toBe("POST");
    req.flush(makeNotification({ isRead: true }));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector(".mark-read")).toBeNull();
    expect(
      fixture.nativeElement.querySelector(".bell-item").className,
    ).not.toContain("unread");
    // 2 nieprzeczytane − 1 oznaczone = badge „1".
    expect(
      fixture.nativeElement.querySelector(".bell-badge").textContent.trim(),
    ).toBe("1");
  });

  it("oznacz wszystkie jako przeczytane czyści badge", async () => {
    await openDropdown();
    flushList([
      makeNotification({ id: "a" }),
      makeNotification({ id: "b", isRead: true }),
    ]);

    const markAll = fixture.nativeElement.querySelector(
      ".mark-all",
    ) as HTMLButtonElement;
    markAll.click();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/notifications/read-all`,
    );
    expect(req.request.method).toBe("POST");
    req.flush({ updated: 2 });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector(".bell-badge")).toBeNull();
    const unread = fixture.nativeElement.querySelectorAll(".bell-item.unread");
    expect(unread.length).toBe(0);
  });

  it("brak powiadomień pokazuje stan pusty", async () => {
    await openDropdown();
    flushList([]);

    const state = fixture.nativeElement.querySelector(".bell-state");
    expect(state.textContent).toContain("Brak powiadomień");
  });
});
