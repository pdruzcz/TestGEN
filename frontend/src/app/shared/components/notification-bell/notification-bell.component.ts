import { DatePipe } from "@angular/common";
import {
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  computed,
  inject,
  signal,
} from "@angular/core";
import { takeUntilDestroyed, toObservable } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { RouterLink } from "@angular/router";
import { catchError, filter, map, of, switchMap, timer } from "rxjs";

import { AuthService } from "../../../core/services/auth.service";
import {
  AppNotification,
  NotificationService,
} from "../../services/notification.service";

/**
 * Dzwonek powiadomień w navbarze (Story 7.11, AC3): ikona z badge liczby
 * nieprzeczytanych (polling co 30 s po zalogowaniu), dropdown z listą —
 * ikona koloru progu (żółty 80% / pomarańczowy 90% / czerwony 100%),
 * tekst, data, link do szczegółów; oznaczanie przeczytanymi pojedynczo
 * lub wszystkie.
 *
 * Polling startuje dopiero po hydratacji profilu (isAuthenticatedSignal)
 * — bez zalogowanego użytkownika dzwonek nie odpytuje API.
 */
@Component({
  selector: "app-notification-bell",
  standalone: true,
  imports: [DatePipe, RouterLink, MatButtonModule, MatIconModule],
  templateUrl: "./notification-bell.component.html",
  styleUrl: "./notification-bell.component.scss",
})
export class NotificationBellComponent {
  private readonly api = inject(NotificationService);
  private readonly authService = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject(ElementRef<HTMLElement>);

  readonly unreadCount = signal(0);
  readonly open = signal(false);
  readonly loading = signal(false);
  readonly notifications = signal<AppNotification[]>([]);

  /** aria-label przycisku dzwonka (WCAG 2.1 AA). */
  readonly bellAriaLabel = computed(() =>
    this.unreadCount() > 0
      ? `Powiadomienia, nieprzeczytane: ${this.unreadCount()}`
      : "Powiadomienia",
  );

  readonly hasUnread = computed(() =>
    this.notifications().some((n) => !n.isRead),
  );

  constructor() {
    // Polling badge: natychmiast po zalogowaniu, potem co 30 s (Dev Notes).
    // Gate na currentUserSignal (hydratacja profilu) — bez usera brak zapytań.
    toObservable(this.authService.currentUserSignal)
      .pipe(
        map((user) => !!user),
        filter((authenticated) => authenticated),
        switchMap(() => timer(0, 30_000)),
        switchMap(() =>
          this.api.getUnreadCount().pipe(catchError(() => of({ count: 0 }))),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ count }) => this.unreadCount.set(count));
  }

  toggle(): void {
    this.open.update((v) => !v);
    if (this.open()) {
      this.loadList();
    }
  }

  /** Zamykanie dropdownu kliknięciem poza komponent. */
  @HostListener("document:click", ["$event.target"])
  onDocumentClick(target: EventTarget | null): void {
    const node = target as HTMLElement | null;
    if (!node || !this.host.nativeElement.contains(node)) {
      this.open.set(false);
    }
  }

  refreshCount(): void {
    this.api.getUnreadCount().subscribe({
      next: ({ count }) => this.unreadCount.set(count),
      error: () => this.unreadCount.set(0),
    });
  }

  loadList(): void {
    this.loading.set(true);
    this.api.getNotifications().subscribe({
      next: (list) => {
        this.notifications.set(list.items);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  /** Kolor ikony progu (AC3): 100% czerwony, 90% pomarańczowy, 80% żółty. */
  severityClass(n: AppNotification): string {
    if (n.thresholdPercentage === null) {
      return n.severity === "critical" ? "critical" : "medium";
    }
    if (n.thresholdPercentage >= 100) return "critical";
    if (n.thresholdPercentage >= 90) return "high";
    return "medium";
  }

  markAsRead(n: AppNotification, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    if (n.isRead) return;
    this.api.markAsRead(n.id).subscribe({
      next: () => {
        n.isRead = true;
        this.notifications.update((list) => [...list]);
        this.unreadCount.update((c) => Math.max(c - 1, 0));
      },
    });
  }

  markAllAsRead(): void {
    this.api.markAllAsRead().subscribe({
      next: ({ updated }) => {
        this.notifications.update((list) =>
          list.map((n) => ({ ...n, isRead: true })),
        );
        this.unreadCount.update((c) => Math.max(c - updated, 0));
      },
    });
  }
}
