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
import { IntegrationService, TestRailConnectionResult } from '../../../core/services/integration.service';

/** Priorytety i typy TestGEN w kolejności, w jakiej mają się pokazać w tabeli mapowania. */
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

@Component({
  selector: 'app-testrail-config',
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
  templateUrl: './testrail-config.component.html',
  styleUrls: ['./testrail-config.component.scss'],
})
export class TestrailConfigComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly priorities = PRIORITIES;
  readonly types = TYPES;

  readonly projectId = signal('');
  readonly isLoading = signal(true);
  readonly isSaving = signal(false);
  readonly isTesting = signal(false);

  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);
  readonly testResult = signal<TestRailConnectionResult | null>(null);

  /** Czy konfiguracja już istnieje — wtedy klucz API jest opcjonalny. */
  readonly isConfigured = signal(false);
  /** Identyfikator integracji — potrzebny ekranowi synchronizacji (Story 8.11). */
  readonly integrationId = signal<string | null>(null);

  readonly baseUrl = signal('');
  readonly email = signal('');
  readonly apiKey = signal('');
  readonly testrailProjectId = signal<number | null>(null);
  readonly suiteId = signal<number | null>(null);
  readonly priorityMap = signal<Record<string, number>>({});
  readonly typeMap = signal<Record<string, number>>({});

  readonly isFormValid = computed(() => {
    const urlOk = this.baseUrl().trim().startsWith('https://');
    const emailOk = this.email().trim().includes('@');
    const projectOk = (this.testrailProjectId() ?? 0) > 0;
    // Przy istniejącej konfiguracji puste pole klucza znaczy „nie zmieniaj".
    const keyOk = this.isConfigured() || this.apiKey().trim().length > 0;
    return urlOk && emailOk && projectOk && keyOk;
  });

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('projectId') ?? '';
    this.projectId.set(projectId);

    this.integrationService
      .getTestRailConfig(projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.isConfigured.set(true);
          this.integrationId.set(config.id);
          this.baseUrl.set(config.baseUrl);
          this.email.set(config.email);
          this.testrailProjectId.set(config.testrailProjectId);
          this.suiteId.set(config.suiteId);
          this.priorityMap.set({ ...config.priorityMap });
          this.typeMap.set({ ...config.typeMap });
          this.isLoading.set(false);
        },
        error: (err: { status?: number }) => {
          this.isLoading.set(false);
          // 404 to normalny stan „jeszcze nieskonfigurowane", nie awaria.
          if (err?.status !== 404) {
            this.errorMessage.set('Nie udało się wczytać konfiguracji TestRail.');
          }
        },
      });
  }

  priorityLabel(priority: string): string {
    return PRIORITY_LABELS[priority] ?? priority;
  }

  typeLabel(type: string): string {
    return TYPE_LABELS[type] ?? type;
  }

  priorityValue(priority: string): number | null {
    return this.priorityMap()[priority] ?? null;
  }

  typeValue(type: string): number | null {
    return this.typeMap()[type] ?? null;
  }

  setPriorityValue(priority: string, value: string | number): void {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 1) {
      return;
    }
    this.priorityMap.set({ ...this.priorityMap(), [priority]: Math.trunc(parsed) });
  }

  setTypeValue(type: string, value: string | number): void {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 1) {
      return;
    }
    this.typeMap.set({ ...this.typeMap(), [type]: Math.trunc(parsed) });
  }

  setNumber(target: 'project' | 'suite', value: string | number): void {
    const raw = String(value).trim();
    if (!raw) {
      if (target === 'suite') {
        this.suiteId.set(null);
      }
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 1) {
      return;
    }
    const truncated = Math.trunc(parsed);
    if (target === 'project') {
      this.testrailProjectId.set(truncated);
    } else {
      this.suiteId.set(truncated);
    }
  }

  save(): void {
    if (!this.isFormValid() || this.isSaving()) {
      return;
    }
    this.isSaving.set(true);
    this.errorMessage.set(null);
    this.testResult.set(null);

    this.integrationService
      .saveTestRailConfig(this.projectId(), {
        baseUrl: this.baseUrl().trim(),
        email: this.email().trim(),
        apiKey: this.apiKey().trim(),
        testrailProjectId: this.testrailProjectId() ?? 0,
        suiteId: this.suiteId(),
        priorityMap: this.priorityMap(),
        typeMap: this.typeMap(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isSaving.set(false);
          this.isConfigured.set(true);
          this.apiKey.set('');
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
      .testTestRailConnection(this.projectId())
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
