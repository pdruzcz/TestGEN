import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import {
  OutboundWebhook,
  TestWebhookResult,
  WebhookDelivery,
  WebhookService,
} from '../../../core/services/webhook.service';

/** Opisy zdarzeń po polsku — backend oddaje same identyfikatory. */
const EVENT_LABELS: Record<string, { label: string; hint: string }> = {
  'analysis.completed': {
    label: 'Analiza zakończona',
    hint: 'po każdym przebiegu analizy projektu',
  },
  'security.finding': {
    label: 'Podatność krytyczna lub wysoka',
    hint: 'tylko te dwa poziomy — niższe zostają w raporcie',
  },
  'gap.detected': {
    label: 'Wykryta luka funkcjonalna',
    hint: 'rozbieżność między dokumentacją a kodem',
  },
  'export.ready': {
    label: 'Raport gotowy',
    hint: 'plik eksportu czeka do pobrania',
  },
  'subscription.changed': {
    label: 'Zmiana planu',
    hint: 'upgrade lub downgrade subskrypcji',
  },
};

const MIN_SECRET_LENGTH = 16;

@Component({
  selector: 'app-webhook-config',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: './webhook-config.component.html',
  styleUrls: ['./webhook-config.component.scss'],
})
export class WebhookConfigComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly webhookService = inject(WebhookService);

  readonly webhooks = this.webhookService.webhooksSignal;
  readonly availableEvents = this.webhookService.availableEventsSignal;
  readonly isLoading = this.webhookService.isLoadingSignal;

  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);

  readonly isFormOpen = signal(false);
  readonly isSubmitting = signal(false);
  /** Id edytowanego webhooka; `null` gdy formularz tworzy nowy. */
  readonly editingId = signal<string | null>(null);

  readonly formUrl = signal('');
  readonly formSecret = signal('');
  readonly formDescription = signal('');
  readonly formEvents = signal<string[]>([]);

  readonly testingId = signal<string | null>(null);
  readonly testResult = signal<(TestWebhookResult & { webhookId: string }) | null>(null);

  readonly pendingRemovalId = signal<string | null>(null);

  readonly deliveriesFor = signal<string | null>(null);
  readonly deliveries = signal<WebhookDelivery[]>([]);
  readonly isLoadingDeliveries = signal(false);
  readonly deliveryStatusFilter = signal('');
  readonly deliveryEventFilter = signal('');

  /** Przy edycji sekret jest opcjonalny — puste pole znaczy „nie zmieniaj". */
  readonly isFormValid = computed(() => {
    const urlOk = this.formUrl().trim().startsWith('https://');
    const eventsOk = this.formEvents().length > 0;
    const secret = this.formSecret().trim();
    const secretOk = this.editingId()
      ? secret.length === 0 || secret.length >= MIN_SECRET_LENGTH
      : secret.length >= MIN_SECRET_LENGTH;
    return urlOk && eventsOk && secretOk;
  });

  ngOnInit(): void {
    this.reload();
  }

  eventLabel(event: string): string {
    return EVENT_LABELS[event]?.label ?? event;
  }

  eventHint(event: string): string {
    return EVENT_LABELS[event]?.hint ?? '';
  }

  statusLabel(status: string | null): string {
    switch (status) {
      case 'delivered':
        return 'Dostarczony';
      case 'failed':
        return 'Nieudany';
      case 'pending':
        return 'Oczekuje';
      default:
        return 'Brak dostaw';
    }
  }

  // ── formularz ─────────────────────────────────────────────────────────────

  openCreateForm(): void {
    this.editingId.set(null);
    this.formUrl.set('');
    this.formSecret.set('');
    this.formDescription.set('');
    this.formEvents.set([]);
    this.errorMessage.set(null);
    this.isFormOpen.set(true);
  }

  openEditForm(webhook: OutboundWebhook): void {
    this.editingId.set(webhook.id);
    this.formUrl.set(webhook.url);
    this.formSecret.set('');
    this.formDescription.set(webhook.description ?? '');
    this.formEvents.set([...webhook.events]);
    this.errorMessage.set(null);
    this.isFormOpen.set(true);
  }

  closeForm(): void {
    this.isFormOpen.set(false);
    this.errorMessage.set(null);
  }

  toggleEvent(event: string): void {
    const current = this.formEvents();
    this.formEvents.set(current.includes(event) ? current.filter((e) => e !== event) : [...current, event]);
  }

  isEventSelected(event: string): boolean {
    return this.formEvents().includes(event);
  }

  submit(): void {
    if (!this.isFormValid() || this.isSubmitting()) {
      return;
    }
    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const editingId = this.editingId();
    const secret = this.formSecret().trim();
    const request$ = editingId
      ? this.webhookService.updateWebhook(editingId, {
          url: this.formUrl().trim(),
          events: this.formEvents(),
          description: this.formDescription().trim() || null,
          ...(secret ? { secret } : {}),
        })
      : this.webhookService.createWebhook({
          url: this.formUrl().trim(),
          secret,
          events: this.formEvents(),
          description: this.formDescription().trim() || null,
        });

    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.isFormOpen.set(false);
        this.infoMessage.set(editingId ? 'Webhook został zaktualizowany.' : 'Webhook został dodany.');
        this.reload();
      },
      error: (err: { error?: { detail?: string } }) => {
        this.isSubmitting.set(false);
        this.errorMessage.set(err?.error?.detail ?? 'Nie udało się zapisać webhooka.');
      },
    });
  }

  // ── akcje na liście ───────────────────────────────────────────────────────

  toggleActive(webhook: OutboundWebhook): void {
    this.webhookService
      .updateWebhook(webhook.id, { isActive: !webhook.isActive })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.reload(),
        error: () => this.errorMessage.set('Nie udało się zmienić stanu webhooka.'),
      });
  }

  testWebhook(webhook: OutboundWebhook): void {
    this.testingId.set(webhook.id);
    this.testResult.set(null);
    this.webhookService
      .testWebhook(webhook.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.testingId.set(null);
          this.testResult.set({ ...result, webhookId: webhook.id });
        },
        error: () => {
          this.testingId.set(null);
          this.errorMessage.set('Nie udało się wykonać testu połączenia.');
        },
      });
  }

  testResultFor(webhookId: string): TestWebhookResult | null {
    const result = this.testResult();
    return result && result.webhookId === webhookId ? result : null;
  }

  askRemove(webhookId: string): void {
    this.pendingRemovalId.set(webhookId);
  }

  cancelRemove(): void {
    this.pendingRemovalId.set(null);
  }

  confirmRemove(): void {
    const id = this.pendingRemovalId();
    if (!id) {
      return;
    }
    this.webhookService
      .deleteWebhook(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pendingRemovalId.set(null);
          this.infoMessage.set('Webhook został usunięty.');
          if (this.deliveriesFor() === id) {
            this.deliveriesFor.set(null);
          }
          this.reload();
        },
        error: () => {
          this.pendingRemovalId.set(null);
          this.errorMessage.set('Nie udało się usunąć webhooka.');
        },
      });
  }

  // ── historia dostaw ───────────────────────────────────────────────────────

  showDeliveries(webhookId: string): void {
    this.deliveriesFor.set(webhookId);
    this.loadDeliveries();
  }

  closeDeliveries(): void {
    this.deliveriesFor.set(null);
    this.deliveries.set([]);
    this.deliveryStatusFilter.set('');
    this.deliveryEventFilter.set('');
  }

  applyDeliveryFilters(): void {
    this.loadDeliveries();
  }

  deliveryStatusLabel(status: string): string {
    return this.statusLabel(status);
  }

  dismissInfo(): void {
    this.infoMessage.set(null);
  }

  private loadDeliveries(): void {
    const webhookId = this.deliveriesFor();
    if (!webhookId) {
      return;
    }
    this.isLoadingDeliveries.set(true);
    this.webhookService
      .getDeliveries(webhookId, {
        status: this.deliveryStatusFilter() || undefined,
        eventType: this.deliveryEventFilter() || undefined,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.deliveries.set(result.items ?? []);
          this.isLoadingDeliveries.set(false);
        },
        error: () => {
          this.isLoadingDeliveries.set(false);
          this.errorMessage.set('Nie udało się wczytać historii dostaw.');
        },
      });
  }

  private reload(): void {
    this.webhookService.listWebhooks().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }
}
