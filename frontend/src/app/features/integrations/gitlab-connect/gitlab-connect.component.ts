import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import { StatusCheckConfigComponent } from '../status-check-config/status-check-config.component';
import {
  GitLabProjectOption,
  IntegrationEvent,
  IntegrationService,
  ScmIntegration,
} from '../../../core/services/integration.service';

/** Komunikaty błędów, którymi backend odsyła z callbacku OAuth. */
const CALLBACK_ERRORS: Record<string, string> = {
  invalid_state: 'Autoryzacja wygasła lub została przerwana. Spróbuj połączyć konto ponownie.',
  token_exchange: 'GitLab odrzucił autoryzację. Sprawdź uprawnienia aplikacji i spróbuj ponownie.',
};

const DEFAULT_GITLAB_URL = 'https://gitlab.com';

@Component({
  selector: 'app-gitlab-connect',
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
    StatusCheckConfigComponent,
  ],
  templateUrl: './gitlab-connect.component.html',
  styleUrls: ['./gitlab-connect.component.scss'],
})
export class GitlabConnectComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly integrations = this.integrationService.gitlabIntegrationsSignal;
  readonly providerConfigured = this.integrationService.gitlabConfiguredSignal;
  readonly events = this.integrationService.gitlabEventsSignal;
  readonly isLoading = this.integrationService.isLoadingGitlabSignal;

  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);

  /**
   * Adres instancji — pole edytowalne, bo GitLab bywa self-hosted.
   * Po podłączeniu pierwszego projektu podpowiadamy adres z integracji.
   */
  readonly gitlabUrl = signal(DEFAULT_GITLAB_URL);

  readonly availableProjects = signal<GitLabProjectOption[]>([]);
  readonly isProjectPickerOpen = signal(false);
  readonly isLoadingProjects = signal(false);
  readonly connectingProjectId = signal<number | null>(null);

  readonly pendingRemovalId = signal<string | null>(null);

  /** Integracja, dla której otwarto ustawienia status checka (Story 8.3). */
  readonly configuringId = signal<string | null>(null);
  readonly configuringName = signal('');

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const error = params.get('error');
    if (error) {
      this.errorMessage.set(CALLBACK_ERRORS[error] ?? 'Połączenie z GitLab nie powiodło się.');
    }

    this.reload();

    if (params.get('connected') === '1') {
      this.openProjectPicker();
    }
  }

  connectGitLab(): void {
    const url = this.normalizedUrl();
    if (!url) {
      this.errorMessage.set('Adres instancji GitLab musi zaczynać się od https://');
      return;
    }
    this.errorMessage.set(null);
    this.integrationService
      .getGitLabAuthUrl(url)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ authorizationUrl }) => {
          window.location.href = authorizationUrl;
        },
        error: (err: { error?: { detail?: string } }) =>
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się rozpocząć autoryzacji GitLab.'),
      });
  }

  openProjectPicker(): void {
    this.isProjectPickerOpen.set(true);
    this.isLoadingProjects.set(true);
    this.errorMessage.set(null);
    this.integrationService
      .getAvailableGitLabProjects(this.normalizedUrl() ?? undefined)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (projects) => {
          this.availableProjects.set(projects);
          this.isLoadingProjects.set(false);
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isLoadingProjects.set(false);
          this.isProjectPickerOpen.set(false);
          this.errorMessage.set(
            err?.error?.detail ?? 'Nie udało się pobrać listy projektów. Połącz konto GitLab ponownie.',
          );
        },
      });
  }

  closeProjectPicker(): void {
    this.isProjectPickerOpen.set(false);
    this.availableProjects.set([]);
  }

  connectProject(project: GitLabProjectOption): void {
    if (project.connected || this.connectingProjectId() !== null) {
      return;
    }
    this.connectingProjectId.set(project.projectId);
    this.errorMessage.set(null);
    this.integrationService
      .connectGitLabProject(project.projectId, this.normalizedUrl() ?? undefined)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.connectingProjectId.set(null);
          this.infoMessage.set(
            `Projekt ${project.pathWithNamespace} został podłączony. Analiza uruchomi się przy najbliższym pushu na gałąź główną.`,
          );
          this.closeProjectPicker();
          this.reload();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.connectingProjectId.set(null);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się podłączyć projektu.');
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
      .removeGitLabIntegration(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pendingRemovalId.set(null);
          this.infoMessage.set('Projekt został odłączony.');
          this.reload();
        },
        error: () => {
          this.pendingRemovalId.set(null);
          this.errorMessage.set('Nie udało się odłączyć projektu.');
        },
      });
  }

  eventLabel(event: IntegrationEvent): string {
    if (event.eventType === 'push') {
      return `Push na ${event.branch ?? '?'}`;
    }
    if (event.prNumber) {
      return `Merge request !${event.prNumber} (${event.action ?? '?'})`;
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

  /** Adres bez końcowego ukośnika; `null`, gdy nie jest to HTTPS. */
  private normalizedUrl(): string | null {
    const raw = this.gitlabUrl().trim();
    if (!raw) {
      return DEFAULT_GITLAB_URL;
    }
    if (!raw.startsWith('https://')) {
      return null;
    }
    return raw.replace(/\/+$/, '');
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
    this.integrationService
      .getGitLabProjects()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          // Podpowiadamy adres instancji już podłączonego projektu, żeby
          // dokładanie kolejnych nie wymagało wpisywania go ponownie.
          const stored = result.items?.find((i) => i.gitlabUrl)?.gitlabUrl;
          if (stored) {
            this.gitlabUrl.set(stored);
          }
        },
      });
    this.integrationService
      .getGitLabRecentEvents()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ error: () => undefined });
  }
}
