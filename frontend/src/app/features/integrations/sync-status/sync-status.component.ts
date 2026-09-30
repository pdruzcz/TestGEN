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
import {
  ConflictResolution,
  ConflictStrategy,
  IntegrationService,
  SyncConflict,
  SyncDirection,
  SyncStatus,
} from '../../../core/services/integration.service';

/** Opisy po polsku — backend oddaje same identyfikatory. */
const DIRECTION_LABELS: Record<SyncDirection, string> = {
  push: 'TestGEN → TMS',
  pull: 'TMS → TestGEN',
  bidirectional: 'W obie strony',
};

const STRATEGY_LABELS: Record<ConflictStrategy, string> = {
  last_write_wins: 'Wygrywa nowsza zmiana',
  manual: 'Rozstrzygam ręcznie',
};

const RESOLUTION_LABELS: Record<ConflictResolution, string> = {
  pending: 'Czeka na decyzję',
  testgen_wins: 'Wygrał TestGEN',
  tms_wins: 'Wygrał TMS',
  manual: 'Rozstrzygnięty ręcznie',
};

/** Dozwolone odstępy. Minimum 5 minut narzuca backend (AC1). */
const INTERVALS = [5, 15, 30, 60, 240, 1440];

/**
 * Ekran synchronizacji dwukierunkowej z TMS (Story 8.11, AC5).
 *
 * Konfiguracja i włącznik są rozdzielone, tak jak w API: zapis ustawień
 * nie może po cichu zacząć wysyłać przypadków do TMS-a.
 */
@Component({
  selector: 'app-sync-status',
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
  templateUrl: './sync-status.component.html',
  styleUrls: ['./sync-status.component.scss'],
})
export class SyncStatusComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly integrationService = inject(IntegrationService);

  readonly integrationId = signal('');
  readonly status = signal<SyncStatus | null>(null);
  readonly conflicts = signal<SyncConflict[]>([]);
  readonly isLoading = signal(true);
  readonly isSaving = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly infoMessage = signal<string | null>(null);

  readonly intervals = INTERVALS;
  readonly directions: SyncDirection[] = ['push', 'pull', 'bidirectional'];
  readonly strategies: ConflictStrategy[] = ['last_write_wins', 'manual'];

  /** Formularz — kopia stanu, żeby niezapisane zmiany nie udawały zapisanych. */
  draftDirection: SyncDirection = 'bidirectional';
  draftInterval = 15;
  draftStrategy: ConflictStrategy = 'last_write_wins';

  readonly isConfigured = computed(() => this.status() !== null);
  readonly isDegraded = computed(() => this.status()?.health === 'degraded');
  readonly pendingConflicts = computed(() => this.conflicts().filter((c) => c.resolution === 'pending'));

  ngOnInit(): void {
    const integrationId = this.route.snapshot.paramMap.get('integrationId') ?? '';
    this.integrationId.set(integrationId);
    this.loadStatus();
  }

  directionLabel(direction: SyncDirection): string {
    return DIRECTION_LABELS[direction];
  }

  strategyLabel(strategy: ConflictStrategy): string {
    return STRATEGY_LABELS[strategy];
  }

  resolutionLabel(resolution: ConflictResolution): string {
    return RESOLUTION_LABELS[resolution];
  }

  intervalLabel(minutes: number): string {
    if (minutes >= 1440) {
      return 'co 24 godziny';
    }
    if (minutes >= 60) {
      const hours = minutes / 60;
      return `co ${hours} ${hours === 1 ? 'godzinę' : 'godziny'}`;
    }
    return `co ${minutes} minut`;
  }

  versionTitle(version: Record<string, unknown>): string {
    return String(version?.['title'] ?? '—');
  }

  loadStatus(): void {
    this.isLoading.set(true);
    this.integrationService
      .getSyncStatus(this.integrationId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (status) => {
          this.applyStatus(status);
          this.isLoading.set(false);
          this.loadConflicts();
        },
        error: (error) => {
          // 404 nie jest awarią: znaczy tylko, że synchronizacji jeszcze
          // nie skonfigurowano — ekran pokazuje wtedy sam formularz.
          this.status.set(null);
          this.isLoading.set(false);
          if (error?.status !== 404) {
            this.errorMessage.set('Nie udało się pobrać stanu synchronizacji.');
          }
        },
      });
  }

  loadConflicts(): void {
    this.integrationService
      .getSyncConflicts(this.integrationId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (list) => this.conflicts.set(list.items ?? []),
        error: () => this.conflicts.set([]),
      });
  }

  saveConfig(): void {
    this.isSaving.set(true);
    this.clearMessages();
    this.integrationService
      .configureSync(this.integrationId(), {
        direction: this.draftDirection,
        intervalMinutes: this.draftInterval,
        conflictStrategy: this.draftStrategy,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (status) => {
          this.applyStatus(status);
          this.isSaving.set(false);
          this.infoMessage.set('Zapisano ustawienia synchronizacji.');
        },
        error: () => {
          this.isSaving.set(false);
          this.errorMessage.set('Nie udało się zapisać ustawień synchronizacji.');
        },
      });
  }

  toggleActive(): void {
    const status = this.status();
    if (!status) {
      return;
    }
    this.isSaving.set(true);
    this.clearMessages();
    const request$ = status.isActive
      ? this.integrationService.deactivateSync(this.integrationId())
      : this.integrationService.activateSync(this.integrationId());

    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (updated) => {
        this.applyStatus(updated);
        this.isSaving.set(false);
        this.infoMessage.set(updated.isActive ? 'Synchronizacja włączona.' : 'Synchronizacja wyłączona.');
      },
      error: () => {
        this.isSaving.set(false);
        this.errorMessage.set('Nie udało się zmienić stanu synchronizacji.');
      },
    });
  }

  runNow(): void {
    this.isSaving.set(true);
    this.clearMessages();
    this.integrationService
      .runSyncNow(this.integrationId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isSaving.set(false);
          this.infoMessage.set('Synchronizacja uruchomiona — wynik pojawi się po jej zakończeniu.');
        },
        error: () => {
          this.isSaving.set(false);
          this.errorMessage.set('Nie udało się uruchomić synchronizacji.');
        },
      });
  }

  resolve(conflict: SyncConflict, resolution: ConflictResolution): void {
    this.clearMessages();
    this.integrationService
      .resolveSyncConflict(conflict.id, resolution)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.conflicts.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
          this.infoMessage.set('Konflikt rozstrzygnięty.');
        },
        error: () => this.errorMessage.set('Nie udało się rozstrzygnąć konfliktu.'),
      });
  }

  private applyStatus(status: SyncStatus): void {
    this.status.set(status);
    this.draftDirection = status.direction;
    this.draftInterval = status.intervalMinutes;
    this.draftStrategy = status.conflictStrategy;
  }

  private clearMessages(): void {
    this.errorMessage.set(null);
    this.infoMessage.set(null);
  }
}
