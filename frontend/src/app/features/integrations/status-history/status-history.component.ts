import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import { IntegrationEvent, IntegrationService } from '../../../core/services/integration.service';

/**
 * Historia status checków jednej integracji (Story 8.3, AC6).
 *
 * Trasa niesie dostawcę, bo zdarzenia są wystawione per dostawca
 * (`/github/events`, `/gitlab/events`) — jedna lista dla obu maskowałaby,
 * z którego repozytorium przyszło zdarzenie.
 */
@Component({
  selector: 'app-status-history',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: './status-history.component.html',
  styleUrls: ['./status-history.component.scss'],
})
export class StatusHistoryComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly events = signal<IntegrationEvent[]>([]);
  readonly isLoading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly provider = signal<'github' | 'gitlab'>('github');

  ngOnInit(): void {
    const integrationId = this.route.snapshot.paramMap.get('integrationId') ?? '';
    const provider = this.route.snapshot.queryParamMap.get('provider') === 'gitlab' ? 'gitlab' : 'github';
    this.provider.set(provider);

    const request$ =
      provider === 'gitlab'
        ? this.integrationService.getGitLabRecentEvents(integrationId, 50)
        : this.integrationService.getRecentEvents(integrationId, 50);

    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (events) => {
        this.events.set(events);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.errorMessage.set('Nie udało się wczytać historii status checków.');
      },
    });
  }

  get backLink(): string {
    return `/settings/integrations/${this.provider()}`;
  }

  eventLabel(event: IntegrationEvent): string {
    if (event.eventType === 'push') {
      return `Push na ${event.branch ?? '?'}`;
    }
    if (event.prNumber) {
      const prefix = event.eventType === 'merge_request' ? 'Merge request !' : 'Pull request #';
      return `${prefix}${event.prNumber} (${event.action ?? '?'})`;
    }
    return event.eventType;
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'completed':
        return 'Zakończone';
      case 'processing':
        return 'W trakcie';
      case 'failed':
        return 'Błąd';
      case 'skipped':
        return 'Pominięte';
      default:
        return 'Oczekuje';
    }
  }

  /** Czy analiza faktycznie się odbyła — pominięte zdarzenia nie ustawiają statusu. */
  hasStatusCheck(event: IntegrationEvent): boolean {
    return event.status === 'completed' || event.status === 'failed';
  }

  shortSha(sha: string | null): string {
    return sha ? sha.slice(0, 7) : '—';
  }

  durationLabel(event: IntegrationEvent): string {
    if (!event.completedAt) {
      return '—';
    }
    const seconds = Math.round((new Date(event.completedAt).getTime() - new Date(event.createdAt).getTime()) / 1000);
    if (seconds < 0) {
      return '—';
    }
    if (seconds < 60) {
      return `${seconds} s`;
    }
    return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
  }
}
