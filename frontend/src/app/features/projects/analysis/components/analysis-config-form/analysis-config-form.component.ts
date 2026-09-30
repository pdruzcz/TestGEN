import { Component, DestroyRef, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import {
  AVAILABLE_FRAMEWORKS,
  AVAILABLE_MODULES,
  AnalysisConfig,
  DEFAULT_ANALYSIS_CONFIG,
} from '../../../services/analysis.service';

/**
 * Analysis configuration form — Story 6.3 AC1, AC8.
 *
 * Reactive Form with:
 * - modules multi-checkbox (AC1)
 * - testFramework dropdown (AC1)
 * - persisted to localStorage on every change; restored on init (AC8)
 * - emits `configChange` on every valid change so parent can drive the start
 *   button enabled state.
 *
 * Story 6.3-zakończenie: pole „Tryb silnika" oraz opcje zaawansowane LLM
 * usunięte z GUI — `engine_mode` to konfiguracja systemu (config-only,
 * decyzja `engine_mode_not_user_controllable`), transparentna dla usera.
 */
@Component({
  selector: 'app-analysis-config-form',
  standalone: true,
  imports: [ReactiveFormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatSelectModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="onSubmit()" class="config-form">
      <h2 class="form-title">Parametry analizy</h2>

      <!-- Modules (AC1) -->
      <fieldset class="form-section">
        <legend>Moduły do analizy</legend>
        <div class="checkbox-grid">
          @for (mod of moduleOptions; track mod.value) {
            <mat-checkbox [checked]="isModuleSelected(mod.value)" (change)="toggleModule(mod.value, $event.checked)">
              {{ mod.label }}
            </mat-checkbox>
          }
        </div>
        @if (form.controls.modules.hasError('required')) {
          <p class="field-error" role="alert">Wybierz co najmniej jeden moduł.</p>
        }
      </fieldset>

      <!-- Test framework (AC1) -->
      <div class="form-section">
        <mat-form-field appearance="outline">
          <mat-label>Framework testowy</mat-label>
          <mat-select formControlName="testFramework">
            <mat-option [value]="null">— Automatyczny —</mat-option>
            @for (fw of frameworkOptions; track fw.value) {
              <mat-option [value]="fw.value">{{ fw.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>

      <!-- Story 1.53 (FR70) — zakresy generowanych testów (§6a) -->
      <fieldset class="form-section">
        <legend>Zakres generowanych testów</legend>
        <div class="checkbox-grid scopes">
          @for (scope of testScopeOptions; track scope.value) {
            <mat-checkbox
              [checked]="isScopeSelected(scope.value)"
              (change)="toggleScope(scope.value, $event.checked)"
              [title]="scope.description"
            >
              <span class="scope-label">{{ scope.label }}</span>
              <span class="scope-desc">{{ scope.description }}</span>
            </mat-checkbox>
          }
        </div>
        <p class="scope-hint">
          Aktywne, gdy projekt zawiera warstwę danych (pliki
          <code>.sql</code>, migracje, modele ORM). Brak warstwy danych → opcja bez efektu.
        </p>
      </fieldset>
    </form>
  `,
  styles: [
    `
      .config-form {
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .form-title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #1a1a1a;
      }
      .form-section {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px;
        margin: 0;
      }
      .form-section legend {
        padding: 0 8px;
        font-size: 13px;
        font-weight: 600;
        color: #374151;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .checkbox-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 8px 16px;
      }
      .field-error {
        margin: 8px 0 0;
        color: #b91c1c;
        font-size: 12px;
      }
      mat-form-field {
        width: 100%;
      }
      /* Story 1.53 (FR70) — scope selector (§6a) */
      .scopes {
        grid-template-columns: 1fr;
      }
      .scope-label {
        font-weight: 600;
      }
      .scope-desc {
        display: block;
        font-size: 12px;
        color: #5b6473;
        font-weight: 400;
        margin-top: 2px;
      }
      .scope-hint {
        margin: 8px 0 0;
        font-size: 12px;
        color: #7a8494;
      }
      .scope-hint code {
        background: #eef1f5;
        padding: 1px 5px;
        border-radius: 4px;
        font-size: 0.92em;
      }
    `,
  ],
})
export class AnalysisConfigFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  @Input() projectId = '';
  @Input() set config(value: AnalysisConfig) {
    this.initialConfig = value;
    if (this.form) {
      this.form.patchValue({
        testFramework: value.testFramework,
        testScopes: value.testScopes ?? [],
      });
      this.selectedModules = new Set(value.modules);
      this.selectedTestScopes = new Set(value.testScopes ?? []);
    }
  }
  @Output() readonly configChange = new EventEmitter<AnalysisConfig>();
  @Output() readonly submitConfig = new EventEmitter<AnalysisConfig>();

  readonly moduleOptions = AVAILABLE_MODULES;
  readonly frameworkOptions = AVAILABLE_FRAMEWORKS;
  /** Story 1.53 (FR70) — zakresy generowanych testów (multi-select, §6a). */
  readonly testScopeOptions: ReadonlyArray<{
    value: string;
    label: string;
    description: string;
  }> = [
    {
      value: 'database',
      label: 'Testy warstwy danych (SQL/DB)',
      description: 'Schemat, klucze obce, ograniczenia, migracje, transakcje (test_type: database)',
    },
  ];

  private initialConfig: AnalysisConfig = { ...DEFAULT_ANALYSIS_CONFIG };
  private selectedModules = new Set<string>(DEFAULT_ANALYSIS_CONFIG.modules);
  private selectedTestScopes = new Set<string>(DEFAULT_ANALYSIS_CONFIG.testScopes ?? []);

  form!: FormGroup<{
    modules: FormControl<string[]>;
    testFramework: FormControl<string | null>;
    testScopes: FormControl<string[]>;
  }>;

  ngOnInit(): void {
    // Load persisted config from localStorage (AC8)
    const stored = this.loadFromStorage();
    const initial = stored ?? this.initialConfig;
    this.selectedModules = new Set(initial.modules);
    this.selectedTestScopes = new Set(initial.testScopes ?? []);

    this.form = this.fb.nonNullable.group({
      modules: this.fb.nonNullable.control<string[]>(initial.modules, {
        validators: [this.atLeastOneModuleValidator],
      }),
      testFramework: this.fb.control<string | null>(initial.testFramework),
      testScopes: this.fb.nonNullable.control<string[]>(initial.testScopes ?? []),
    });

    // Persist to localStorage on every change (AC8)
    this.form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const cfg = this.currentConfig();
      this.saveToStorage(cfg);
      this.configChange.emit(cfg);
    });

    // Initial emission so parent can enable/disable button
    this.configChange.emit(this.currentConfig());
  }

  isModuleSelected(value: string): boolean {
    return this.selectedModules.has(value);
  }

  toggleModule(value: string, checked: boolean): void {
    if (checked) this.selectedModules.add(value);
    else this.selectedModules.delete(value);
    const arr = Array.from(this.selectedModules);
    this.form.controls.modules.setValue(arr);
    this.form.controls.modules.markAsDirty();
    this.form.controls.modules.updateValueAndValidity();
  }

  /** Story 1.53 (FR70) — zakresy testów (§6a). */
  isScopeSelected(value: string): boolean {
    return this.selectedTestScopes.has(value);
  }

  toggleScope(value: string, checked: boolean): void {
    if (checked) this.selectedTestScopes.add(value);
    else this.selectedTestScopes.delete(value);
    this.form.controls.testScopes.setValue(Array.from(this.selectedTestScopes));
    this.form.controls.testScopes.markAsDirty();
  }

  onSubmit(): void {
    if (this.form.invalid) return;
    const cfg = this.currentConfig();
    this.saveToStorage(cfg);
    this.submitConfig.emit(cfg);
  }

  private currentConfig(): AnalysisConfig {
    const v = this.form.getRawValue();
    return {
      modules: v.modules,
      testFramework: v.testFramework ?? null,
      testScopes: v.testScopes ?? [],
    };
  }

  private atLeastOneModuleValidator: ValidatorFn = (control: AbstractControl) => {
    const value = control.value as string[] | null;
    return !value || value.length === 0 ? { required: true } : null;
  };

  private storageKey(): string {
    return `testgen:analysis-config:${this.projectId || 'default'}`;
  }

  private loadFromStorage(): AnalysisConfig | null {
    try {
      const raw = localStorage.getItem(this.storageKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw) as Partial<AnalysisConfig>;
      return { ...DEFAULT_ANALYSIS_CONFIG, ...parsed };
    } catch {
      return null;
    }
  }

  private saveToStorage(cfg: AnalysisConfig): void {
    try {
      localStorage.setItem(this.storageKey(), JSON.stringify(cfg));
    } catch {
      // localStorage unavailable or quota exceeded — ignore.
    }
  }
}
