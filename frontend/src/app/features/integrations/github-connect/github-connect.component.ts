import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import { StatusCheckConfigComponent } from '../status-check-config/status-check-config.component';
import {
  IntegrationEvent,
  IntegrationService,
  ScmIntegration,
  ScmRepoOption,
} from '../../../core/services/integration.service';

/** Komunikaty błędów, którymi backend odsyła z callbacku OAuth. */
const CALLBACK_ERRORS: Record<string, string> = {
  invalid_state: 'Autoryzacja wygasła lub została przerwana. Spróbuj połączyć konto ponownie.',
  token_exchange: 'GitHub odrzucił autoryzację. Sprawdź uprawnienia aplikacji i spróbuj ponownie.',
};

@Component({
  selector: 'app-github-connect',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
    StatusCheckConfigComponent,
  ],
  templateUrl: './github-connect.component.html',
  styleUrls: ['./github-connect.component.scss'],
})
export class GithubConnectComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly integrations = this.integrationService.integrationsSignal;
  readonly providerConfigured = this.integrationService.providerConfiguredSignal;
  readonly events = this.integrationService.eventsSignal;
  readonly isLoading = this.integrationService.isLoadingSignal;

  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);

  /** Wybór repozytoriów pojawia się dopiero po powrocie z autoryzacji. */
  readonly availableRepos = signal<ScmRepoOption[]>([]);
  readonly isRepoPickerOpen = signal(false);
  readonly isLoadingRepos = signal(false);
  readonly connectingRepo = signal<string | null>(null);

  readonly pendingRemovalId = signal<string | null>(null);

  /** Integracja, dla której otwarto ustawienia status checka (Story 8.3). */
  readonly configuringId = signal<string | null>(null);
  readonly configuringName = signal('');

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const error = params.get('error');
    if (error) {
      this.errorMessage.set(CALLBACK_ERRORS[error] ?? 'Połączenie z GitHub nie powiodło się.');
    }

    this.reload();

    // Powrót z GitHuba — token czeka po stronie serwera, więc od razu
    // pokazujemy listę repozytoriów do wyboru.
    if (params.get('connected') === '1') {
      this.openRepoPicker();
    }
  }

  connectGitHub(): void {
    this.errorMessage.set(null);
    this.integrationService
      .getGitHubAuthUrl()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ authorizationUrl }) => {
          window.location.href = authorizationUrl;
        },
        error: (err: { error?: { detail?: string } }) =>
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się rozpocząć autoryzacji GitHub.'),
      });
  }

  openRepoPicker(): void {
    this.isRepoPickerOpen.set(true);
    this.isLoadingRepos.set(true);
    this.errorMessage.set(null);
    this.integrationService
      .getAvailableRepos()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (repos) => {
          this.availableRepos.set(repos);
          this.isLoadingRepos.set(false);
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isLoadingRepos.set(false);
          this.isRepoPickerOpen.set(false);
          this.errorMessage.set(
            err?.error?.detail ?? 'Nie udało się pobrać listy repozytoriów. Połącz konto GitHub ponownie.',
          );
        },
      });
  }

  closeRepoPicker(): void {
    this.isRepoPickerOpen.set(false);
    this.availableRepos.set([]);
  }

  connectRepo(repo: ScmRepoOption): void {
    if (repo.connected || this.connectingRepo()) {
      return;
    }
    this.connectingRepo.set(repo.fullName);
    this.errorMessage.set(null);
    this.integrationService
      .connectRepo(repo.fullName)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.connectingRepo.set(null);
          this.infoMessage.set(
            `Repozytorium ${repo.fullName} zostało podłączone. Analiza uruchomi się przy najbliższym pushu na gałąź główną.`,
          );
          this.closeRepoPicker();
          this.reload();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.connectingRepo.set(null);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się podłączyć repozytorium.');
        },
      });
  }

  askRemove(integrationId: string): void {
    this.pendingRemovalId.set(integrationId);
  }

  cancelRemove(): void {
    this.pendingRemovalId.set(null);
  }

  confirmRemove(): void {
    const id = this.pendingRemovalId();
    if (!id) {
      return;
    }
    this.integrationService
      .removeIntegration(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pendingRemovalId.set(null);
          this.infoMessage.set('Repozytorium zostało odłączone.');
          this.reload();
        },
        error: () => {
          this.pendingRemovalId.set(null);
          this.errorMessage.set('Nie udało się odłączyć repozytorium.');
        },
      });
  }

  eventLabel(event: IntegrationEvent): string {
    if (event.eventType === 'push') {
      return `Push na ${event.branch ?? '?'}`;
    }
    if (event.prNumber) {
      return `Pull request #${event.prNumber} (${event.action ?? '?'})`;
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

  webhookLabel(integration: ScmIntegration): string {
    return integration.webhookActive ? 'Webhook aktywny' : 'Webhook nieaktywny';
  }

  shortSha(sha: string | null): string {
    return sha ? sha.slice(0, 7) : '—';
  }

  dismissInfo(): void {
    this.infoMessage.set(null);
  }

  openStatusConfig(integrationId: string, repoName: string): void {
    this.configuringName.set(repoName);
    this.configuringId.set(integrationId);
  }

  closeStatusConfig(): void {
    this.configuringId.set(null);
  }

  onStatusConfigSaved(): void {
    this.configuringId.set(null);
    this.infoMessage.set('Ustawienia status checka zostały zapisane.');
  }

  private reload(): void {
    this.integrationService.getConnectedRepos().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
    this.integrationService
      .getRecentEvents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
