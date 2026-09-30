import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";

/** Typ powiadomienia — „limit_warning" z progów zużycia (Story 7.11). */
export type AppNotificationType =
  | "limit_warning"
  | "payment_failed"
  | "subscription_changed"
  | "invoice_ready";

/** Waga powiadomienia: 80/90% → warning, 100% → critical. */
export type AppNotificationSeverity = "info" | "warning" | "critical";

/** Rekord powiadomienia in-app (klucze po konwersji snake→camel). */
export interface AppNotification {
  id: string;
  type: AppNotificationType;
  severity: AppNotificationSeverity;
  title: string;
  message: string;
  resourceType: string | null;
  currentValue: number | null;
  limitValue: number | null;
  percentage: number | null;
  thresholdPercentage: number | null;
  isRead: boolean;
  ctaUrl: string | null;
  createdAt: string;
}

/** Strona listy GET /notifications. */
export interface NotificationList {
  items: AppNotification[];
  total: number;
  page: number;
  size: number;
}

/** Serwis HTTP powiadomień (Story 7.11, Task 6.4) — dzwonek w navbarze. */
@Injectable({ providedIn: "root" })
export class NotificationService {
  private readonly apiUrl = environment.apiUrl;
  private readonly http = inject(HttpClient);

  /** Lista powiadomień użytkownika — najnowsze pierwsze. */
  getNotifications(page = 1, size = 20): Observable<NotificationList> {
    return this.http.get<NotificationList>(`${this.apiUrl}/notifications`, {
      params: { page, size },
    });
  }

  /** Liczba nieprzeczytanych — badge dzwonka (polling co 30 s). */
  getUnreadCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(
      `${this.apiUrl}/notifications/unread-count`,
    );
  }

  /** Oznacz pojedyncze jako przeczytane. */
  markAsRead(id: string): Observable<AppNotification> {
    return this.http.post<AppNotification>(
      `${this.apiUrl}/notifications/${id}/read`,
      {},
    );
  }

  /** „Oznacz wszystkie jako przeczytane". */
  markAllAsRead(): Observable<{ updated: number }> {
    return this.http.post<{ updated: number }>(
      `${this.apiUrl}/notifications/read-all`,
      {},
    );
  }
}
