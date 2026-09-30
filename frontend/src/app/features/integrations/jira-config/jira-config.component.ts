import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NavbarComponent } from '../../../shared/components/navbar.component';
import { FooterComponent } from '../../../shared/components/footer.component';
import { IntegrationService, JiraPlugin, JiraTmsConnectionResult } from '../../../core/services/integration.service';

const PRIORITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const;
const TYPES = ['FUNCTIONAL', 'REGRESSION', 'SECURITY', 'PERFORMANCE', 'ACCESSIBILITY'] as const;

const PRIORITY_LABELS: Record<string, string> = {
  CRITICAL: 'Krytyczny',
  HIGH: 'Wysoki',
  MEDIUM: 'Średni',
  LOW: 'Niski',
};

const TYPE_LABELS: Record<string, string> = {
  FUNCTIONAL: 'Funkcjonalny',
  REGRESSION: 'Regresyjny',
  SECURITY: 'Bezpieczeństwa',
  PERFORMANCE: 'Wydajnościowy',
  ACCESSIBILITY: 'Dostępności',
};

/** Czym różnią się wtyczki z punktu widzenia użytkownika. */
const PLUGIN_INFO: Record<JiraPlugin, { label: string; hint: string }> = {
  xray: {
    label: 'Jira Xray',
    hint: 'Testy są zgłoszeniami Jiry; powiązanie z TestGEN idzie w etykiecie.',
  },
  zephyr: {
    label: 'Zephyr Scale',
    hint: 'Testy mają własny magazyn i foldery; powiązanie w polu własnym testgen_id.',
  },
};

@Component({
  selector: 'app-jira-config',
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
  templateUrl: './jira-config.component.html',
  styleUrls: ['./jira-config.component.scss'],
})
export class JiraConfigComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly priorities = PRIORITIES;
  readonly types = TYPES;
  readonly plugins: JiraPlugin[] = ['xray', 'zephyr'];

  readonly projectId = signal('');
  readonly isLoading = signal(true);
  readonly isSaving = signal(false);
  readonly isTesting = signal(false);

  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);
  readonly testResult = signal<JiraTmsConnectionResult | null>(null);

  readonly isConfigured = signal(false);
  /** Identyfikator integracji — potrzebny ekranowi synchronizacji (Story 8.11). */
  readonly integrationId = signal<string | null>(null);

  readonly baseUrl = signal('');
  readonly email = signal('');
  readonly apiToken = signal('');
  readonly projectKey = signal('');
  readonly plugin = signal<JiraPlugin>('xray');
  readonly linkedIssue = signal('');
  readonly priorityMap = signal<Record<string, string>>({});
  readonly typeLabels = signal<Record<string, string>>({});

  readonly isFormValid = computed(() => {
    const urlOk = this.baseUrl().trim().startsWith('https://');
    const emailOk = this.email().trim().includes('@');
    const keyOk = this.projectKey().trim().length > 0;
    // Przy istniejącej konfiguracji puste pole tokenu znaczy „nie zmieniaj".
    const tokenOk = this.isConfigured() || this.apiToken().trim().length > 0;
    return urlOk && emailOk && keyOk && tokenOk;
  });

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('projectId') ?? '';
    this.projectId.set(projectId);

    this.integrationService
      .getJiraTmsConfig(projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.isConfigured.set(true);
          this.integrationId.set(config.id);
          this.baseUrl.set(config.baseUrl);
          this.email.set(config.email);
          this.projectKey.set(config.projectKey);
          this.plugin.set(config.plugin);
          this.linkedIssue.set(config.linkedIssue ?? '');
          this.priorityMap.set({ ...config.priorityMap });
          this.typeLabels.set({ ...config.typeLabels });
          this.isLoading.set(false);
        },
        error: (err: { status?: number }) => {
          this.isLoading.set(false);
          // 404 to normalny stan „jeszcze nieskonfigurowane", nie awaria.
          if (err?.status !== 404) {
            this.errorMessage.set('Nie udało się wczytać konfiguracji Jira.');
          }
        },
      });
  }

  pluginLabel(plugin: JiraPlugin): string {
    return PLUGIN_INFO[plugin].label;
  }

  pluginHint(plugin: JiraPlugin): string {
    return PLUGIN_INFO[plugin].hint;
  }

  priorityLabel(priority: string): string {
    return PRIORITY_LABELS[priority] ?? priority;
  }

  typeLabel(type: string): string {
    return TYPE_LABELS[type] ?? type;
  }

  priorityValue(priority: string): string {
    return this.priorityMap()[priority] ?? '';
  }

  typeLabelValue(type: string): string {
    return this.typeLabels()[type] ?? '';
  }

  setPriorityValue(priority: string, value: string): void {
    this.priorityMap.set({ ...this.priorityMap(), [priority]: value });
  }

  setTypeLabelValue(type: string, value: string): void {
    this.typeLabels.set({ ...this.typeLabels(), [type]: value });
  }

  selectPlugin(plugin: JiraPlugin): void {
    this.plugin.set(plugin);
  }

  save(): void {
    if (!this.isFormValid() || this.isSaving()) {
      return;
    }
    this.isSaving.set(true);
    this.errorMessage.set(null);
    this.testResult.set(null);

    this.integrationService
      .saveJiraTmsConfig(this.projectId(), {
        baseUrl: this.baseUrl().trim(),
        email: this.email().trim(),
        apiToken: this.apiToken().trim(),
        projectKey: this.projectKey().trim(),
        plugin: this.plugin(),
        linkedIssue: this.linkedIssue().trim() || null,
        priorityMap: this.priorityMap(),
        typeLabels: this.typeLabels(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.isSaving.set(false);
          this.isConfigured.set(true);
          this.apiToken.set('');
          this.projectKey.set(config.projectKey);
          this.infoMessage.set('Konfiguracja została zapisana.');
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isSaving.set(false);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się zapisać konfiguracji.');
        },
      });
  }

  testConnection(): void {
    this.isTesting.set(true);
    this.testResult.set(null);
    this.errorMessage.set(null);

    this.integrationService
      .testJiraTmsConnection(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.isTesting.set(false);
          this.testResult.set(result);
        },
        error: () => {
          this.isTesting.set(false);
          this.errorMessage.set('Nie udało się wykonać testu połączenia.');
        },
      });
  }

  dismissInfo(): void {
    this.infoMessage.set(null);
  }
}
