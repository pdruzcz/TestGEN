import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

/**
 * Klient webhooków wychodzących TestGEN (Story 8.7).
 *
 * Nie mylić z `IntegrationService`, który obsługuje ruch w drugą stronę —
 * zdarzenia przychodzące z GitHuba i GitLaba.
 *
 * Sekret jest wyłącznie polem żądania: backend go nie oddaje, więc kontrakt
 * odpowiedzi celowo go nie zawiera.
 */

export type WebhookEventType =
  | 'analysis.completed'
  | 'security.finding'
  | 'gap.detected'
  | 'export.ready'
  | 'subscription.changed';

export type DeliveryStatus = 'pending' | 'delivered' | 'failed';

export interface OutboundWebhook {
  id: string;
  url: string;
  description: string | null;
  events: string[];
  isActive: boolean;
  lastDeliveryAt: string | null;
  lastDeliveryStatus: DeliveryStatus | null;
  createdAt: string;
}

export interface WebhookList {
  items: OutboundWebhook[];
  total: number;
  availableEvents: string[];
}

export interface CreateWebhookPayload {
  url: string;
  secret: string;
  events: string[];
  description?: string | null;
}

export interface UpdateWebhookPayload {
  url?: string;
  secret?: string;
  events?: string[];
  description?: string | null;
  isActive?: boolean;
}

export interface TestWebhookResult {
  success: boolean;
  statusCode: number | null;
  message: string;
  responseBody: string | null;
}

export interface WebhookDelivery {
  id: string;
  webhookId: string;
  eventType: string;
  status: DeliveryStatus;
  attemptNumber: number;
  responseStatus: number | null;
  responseBody: string | null;
  errorMessage: string | null;
  deliveredAt: string | null;
  nextRetryAt: string | null;
  createdAt: string;
}

export interface WebhookDeliveryList {
  items: WebhookDelivery[];
  total: number;
}

@Injectable({ providedIn: 'root' })
export class WebhookService {
  private readonly apiUrl = `${environment.apiUrl}/webhooks`;
  private readonly http = inject(HttpClient);

  readonly webhooksSignal = signal<OutboundWebhook[]>([]);
  readonly availableEventsSignal = signal<string[]>([]);
  readonly isLoadingSignal = signal(false);

  listWebhooks(): Observable<WebhookList> {
    this.isLoadingSignal.set(true);
    return this.http.get<WebhookList>(this.apiUrl).pipe(
      tap({
        next: (result) => {
          this.webhooksSignal.set(result.items ?? []);
          this.availableEventsSignal.set(result.availableEvents ?? []);
          this.isLoadingSignal.set(false);
        },
        error: () => this.isLoadingSignal.set(false),
      }),
    );
  }

  createWebhook(payload: CreateWebhookPayload): Observable<OutboundWebhook> {
    return this.http.post<OutboundWebhook>(this.apiUrl, payload);
  }

  updateWebhook(webhookId: string, payload: UpdateWebhookPayload): Observable<OutboundWebhook> {
    return this.http.put<OutboundWebhook>(`${this.apiUrl}/${webhookId}`, payload);
  }

  deleteWebhook(webhookId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${webhookId}`);
  }

  testWebhook(webhookId: string): Observable<TestWebhookResult> {
    return this.http.post<TestWebhookResult>(`${this.apiUrl}/${webhookId}/test`, {});
  }

  getDeliveries(
    webhookId: string,
    filters: { status?: string; eventType?: string; limit?: number } = {},
  ): Observable<WebhookDeliveryList> {
    let params = new HttpParams().set('limit', String(filters.limit ?? 100));
    if (filters.status) {
      params = params.set('status', filters.status);
    }
    if (filters.eventType) {
      params = params.set('event_type', filters.eventType);
    }
    return this.http.get<WebhookDeliveryList>(`${this.apiUrl}/${webhookId}/deliveries`, {
      params,
    });
  }
}
