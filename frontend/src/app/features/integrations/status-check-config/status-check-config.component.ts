import { Component, DestroyRef, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { IntegrationService, StatusCheckConfig } from '../../../core/services/integration.service';

type Threshold = 'critical' | 'high' | 'medium';

/**
 * Ustawienia status checka dla jednego repozytorium (Story 8.3, AC6).
 *
 * Wspólny dla ekranów GitHuba i GitLaba — konfiguracja jest adresowana
 * identyfikatorem integracji, więc różnice między dostawcami nie sięgają
 * tego poziomu.
 */
@Component({
  selector: 'app-status-check-config',
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  template: `
    <div class="dialog-backdrop">
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="status-config-title">
        <h2 id="status-config-title" class="dialog-title">Status check — {{ repoName }}</h2>

        @if (isLoading()) {
          <div class="loading">
            <mat-spinner diameter="24" aria-label="Ładowanie"></mat-spinner>
            Wczytuję ustawienia...
          </div>
        } @else {
          <fieldset class="field">
            <legend class="field-label">Próg blokowania</legend>
            <p class="field-hint">
              Analiza zakończy się niepowodzeniem, gdy znajdzie problem co najmniej tak poważny jak wybrany poziom.
            </p>
            @for (option of thresholds; track option.value) {
              <label class="radio">
                <input
                  type="radio"
                  name="threshold"
                  [value]="option.value"
                  [checked]="threshold() === option.value"
                  (change)="threshold.set(option.value)"
                />
                <span>
                  <strong>{{ option.label }}</strong> — {{ option.hint }}
                </span>
              </label>
            }
          </fieldset>

          <label class="toggle">
            <input type="checkbox" [checked]="failOnThreshold()" (change)="failOnThreshold.set(!failOnThreshold())" />
            <span>
              <strong>Blokuj merge po przekroczeniu progu</strong> — gdy wyłączone, status pozostaje zielony, a liczby i
              tak są widoczne.
            </span>
          </label>

          <label class="toggle">
            <input type="checkbox" [checked]="postComment()" (change)="postComment.set(!postComment())" />
            <span> <strong>Dodawaj komentarz na PR/MR</strong> — podsumowanie znalezisk i link do raportu. </span>
          </label>

          @if (statusContext()) {
            <p class="context-hint">
              W regułach ochrony gałęzi wpisz nazwę:
              <code>{{ statusContext() }}</code>
            </p>
          }
        }

        @if (errorMessage()) {
          <p class="form-error" role="alert">{{ errorMessage() }}</p>
        }

        <div class="dialog-actions">
          <button mat-button type="button" (click)="closed.emit()">Anuluj</button>
          <button
            mat-raised-button
            color="primary"
            type="button"
            [disabled]="isLoading() || isSaving()"
            (click)="save()"
          >
            {{ isSaving() ? 'Zapisuję...' : 'Zapisz' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .dialog-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.45);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: 16px;
      }
      .dialog {
        background: #fff;
        border-radius: 16px;
        padding: 24px;
        width: 100%;
        max-width: 560px;
        max-height: 80vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .dialog-title {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #1a1a1a;
        word-break: break-all;
      }
      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #6b7280;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        border: none;
        padding: 0;
        margin: 0;
      }
      .field-label {
        font-size: 13px;
        font-weight: 500;
        color: #4b5563;
        padding: 0;
      }
      .field-hint {
        font-size: 12px;
        color: #6b7280;
        margin: 0 0 4px;
      }
      .radio,
      .toggle {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        font-size: 14px;
        color: #4b5563;
        padding: 6px 0;
      }
      .radio strong,
      .toggle strong {
        color: #1a1a1a;
      }
      .context-hint {
        margin: 0;
        font-size: 13px;
        color: #4b5563;
        background: #f7f8fa;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 10px 12px;
      }
      .context-hint code {
        font-family: 'SFMono-Regular', Menlo, Consolas, monospace;
      }
      .form-error {
        color: #b71c1c;
        font-size: 14px;
        margin: 0;
      }
      .dialog-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
      }
    `,
  ],
})
export class StatusCheckConfigComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly integrationService = inject(IntegrationService);

  @Input({ required: true }) integrationId!: string;
  @Input() repoName = '';

  @Output() readonly closed = new EventEmitter<void>();
  @Output() readonly saved = new EventEmitter<StatusCheckConfig>();

  readonly thresholds: { value: Threshold; label: string; hint: string }[] = [
    { value: 'critical', label: 'Krytyczny', hint: 'blokuje tylko problemy krytyczne' },
    { value: 'high', label: 'Wysoki', hint: 'blokuje krytyczne i wysokie' },
    { value: 'medium', label: 'Średni', hint: 'blokuje krytyczne, wysokie i średnie' },
  ];

  readonly threshold = signal<Threshold>('critical');
  readonly postComment = signal(true);
  readonly failOnThreshold = signal(true);
  readonly statusContext = signal('');

  readonly isLoading = signal(true);
  readonly isSaving = signal(false);
  readonly errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.integrationService
      .getStatusCheckConfig(this.integrationId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.threshold.set(config.severityThreshold);
          this.postComment.set(config.postComment);
          this.failOnThreshold.set(config.failOnThreshold);
          this.statusContext.set(config.statusContext);
          this.isLoading.set(false);
        },
        error: () => {
          this.isLoading.set(false);
          this.errorMessage.set('Nie udało się wczytać ustawień status checka.');
        },
      });
  }

  save(): void {
    this.isSaving.set(true);
    this.errorMessage.set(null);
    this.integrationService
      .updateStatusCheckConfig(this.integrationId, {
        severityThreshold: this.threshold(),
        postComment: this.postComment(),
        failOnThreshold: this.failOnThreshold(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.isSaving.set(false);
          this.saved.emit(config);
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isSaving.set(false);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się zapisać ustawień.');
        },
      });
  }
}
