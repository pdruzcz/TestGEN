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
import { IntegrationService, JiraImportState, JiraProjectOption } from '../../../core/services/integration.service';

/** Typy zgłoszeń, które backend umie przełożyć na wymagania (AC2). */
const ISSUE_TYPES: { value: string; label: string; hint: string }[] = [
  { value: 'Story', label: 'Historyjki', hint: 'wymagania funkcjonalne' },
  { value: 'Epic', label: 'Epiki', hint: 'grupują historyjki w moduły' },
  { value: 'Bug', label: 'Błędy', hint: 'wymagania negatywne — czego system robić nie powinien' },
  { value: 'Sub-task', label: 'Podzadania', hint: 'podwymagania historyjek' },
];

const STATUS_LABELS: Record<string, string> = {
  pending: 'Oczekuje',
  running: 'W toku',
  completed: 'Zakończony',
  failed: 'Nieudany',
};

type Scope = 'incremental' | 'full' | 'since';

/**
 * Import wymagań z Jiry (Story 8.12, AC5).
 *
 * Domyślny zakres jest przyrostowy: kolejny import pobiera wyłącznie
 * zgłoszenia zmienione od ostatniego udanego przebiegu. Pełny import trzeba
 * wybrać świadomie, bo przy dużym projekcie Jiry trwa znacznie dłużej.
 */
@Component({
  selector: 'app-jira-import',
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
  templateUrl: './jira-import.component.html',
  styleUrls: ['./jira-import.component.scss'],
})
export class JiraImportComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly projectId = signal('');
  readonly jiraProjects = signal<JiraProjectOption[]>([]);
  readonly imports = signal<JiraImportState[]>([]);
  readonly isLoading = signal(true);
  readonly isImporting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);

  readonly issueTypes = ISSUE_TYPES;

  selectedProjectKey = '';
  selectedTypes: string[] = ['Story', 'Epic', 'Bug'];
  scope: Scope = 'incremental';
  sinceDate = '';

  /**
   * Metoda, a nie sygnał: `selectedProjectKey` jest zwykłym polem pod
   * `ngModel`, więc `computed` nigdy by się nie przeliczył po jego zmianie.
   */
  canImport(): boolean {
    return this.selectedProjectKey.length > 0 && !this.isImporting();
  }

  ngOnInit(): void {
    this.projectId.set(this.route.snapshot.paramMap.get('projectId') ?? '');
    this.loadJiraProjects();
    this.loadStatus();
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  isTypeSelected(value: string): boolean {
    return this.selectedTypes.includes(value);
  }

  toggleType(value: string): void {
    this.selectedTypes = this.isTypeSelected(value)
      ? this.selectedTypes.filter((item) => item !== value)
      : [...this.selectedTypes, value];
  }

  /** Podsumowanie zakończonego importu, słowami (AC5). */
  summaryOf(item: JiraImportState): string {
    const requirements = `${item.totalImported} ${plural(item.totalImported, 'wymaganie', 'wymagania', 'wymagań')}`;
    const attachments = `${item.totalAttachments} ${plural(item.totalAttachments, 'załącznik', 'załączniki', 'załączników')}`;
    const base = `Zaimportowano ${requirements} i ${attachments}`;
    if (!item.totalSkipped) {
      return `${base}.`;
    }
    const skipped = plural(item.totalSkipped, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń');
    return `${base}; pominięto ${item.totalSkipped} ${skipped}.`;
  }

  loadJiraProjects(): void {
    this.isLoading.set(true);
    this.integrationService
      .getJiraProjects(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (list) => {
          this.jiraProjects.set(list.items ?? []);
          this.isLoading.set(false);
        },
        error: (error: { status?: number; error?: { detail?: string } }) => {
          this.isLoading.set(false);
          this.jiraProjects.set([]);
          this.errorMessage.set(
            error?.status === 404
              ? 'Integracja z Jirą nie jest skonfigurowana dla tego projektu.'
              : (error?.error?.detail ?? 'Nie udało się pobrać listy projektów Jiry.'),
          );
        },
      });
  }

  loadStatus(): void {
    this.integrationService
      .getJiraImportStatus(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (items) => this.imports.set(items ?? []),
        error: () => this.imports.set([]),
      });
  }

  startImport(): void {
    if (!this.canImport()) {
      return;
    }
    this.isImporting.set(true);
    this.errorMessage.set(null);
    this.infoMessage.set(null);

    this.integrationService
      .importFromJira(this.projectId(), {
        jiraProjectKey: this.selectedProjectKey,
        issueTypes: this.selectedTypes,
        fullReimport: this.scope === 'full',
        updatedAfter: this.scope === 'since' && this.sinceDate ? `${this.sinceDate}T00:00:00Z` : null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isImporting.set(false);
          this.infoMessage.set('Import uruchomiony. Wymagania pojawią się w projekcie po jego zakończeniu.');
          this.loadStatus();
        },
        error: (error: { error?: { detail?: string } }) => {
          this.isImporting.set(false);
          this.errorMessage.set(error?.error?.detail ?? 'Nie udało się uruchomić importu.');
        },
      });
  }
}

/** Polska odmiana rzeczownika po liczebniku. */
function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) {
    return one;
  }
  const lastTwo = count % 100;
  const last = count % 10;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) {
    return few;
  }
  return many;
}
