import { Component, DestroyRef, OnInit, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  FormControl,
  FormRecord,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";

import {
  AdminService,
  PlatformConfig,
  PlatformConfigUpdate,
} from "../../services/admin.service";

export const LLM_PROVIDERS = ["anthropic", "openai"] as const;

const FEATURE_FLAG_LABELS: Record<string, string> = {
  aiAssistant: "Asystent AI",
  selfHealing: "Self-healing testów",
  visualRegression: "Regresja wizualna",
  securityScan: "Skanowanie bezpieczeństwa",
};

/**
 * Globalna konfiguracja platformy: limity, LLM, tryb serwisowy, flagi funkcji
 * (Story 6.15, AC7).
 *
 * Zapis jest częściowy — wysyłamy wyłącznie sekcje, które faktycznie się
 * zmieniły, dzięki czemu log audytu nie rejestruje pustych aktualizacji.
 */
@Component({
  selector: "app-platform-config",
  standalone: true,
  imports: [
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSlideToggleModule,
    ReactiveFormsModule,
  ],
  templateUrl: "./platform-config.component.html",
  styleUrls: ["./platform-config.component.scss"],
})
export class PlatformConfigComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  readonly providers = LLM_PROVIDERS;
  readonly isLoading = this.adminService.isLoadingSignal;
  readonly errorMessage = this.adminService.errorSignal;
  readonly infoMessage = signal<string | null>(null);

  private readonly config = this.adminService.configSignal;
  readonly featureFlagKeys = computed(() =>
    Object.keys(this.config()?.featureFlags ?? {}),
  );

  readonly featureFlags = new FormRecord<FormControl<boolean>>({});

  readonly form = this.fb.group({
    limits: this.fb.group({
      maxFileSizeMb: [100, [Validators.required, Validators.min(1)]],
      maxProjectsPerTenant: [50, [Validators.required, Validators.min(1)]],
      maxUsersPerTenant: [25, [Validators.required, Validators.min(1)]],
      llmCostLimitUsd: [100, [Validators.required, Validators.min(0)]],
    }),
    llm: this.fb.group({
      provider: ["anthropic", Validators.required],
      model: ["", [Validators.required, Validators.maxLength(200)]],
      temperature: [
        0.2,
        [Validators.required, Validators.min(0), Validators.max(2)],
      ],
      maxTokens: [4096, [Validators.required, Validators.min(256)]],
      timeoutSeconds: [60, [Validators.required, Validators.min(5)]],
    }),
    maintenance: this.fb.group({
      enabled: [false],
      message: ["", Validators.maxLength(500)],
    }),
  });

  ngOnInit(): void {
    this.adminService
      .getConfig()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (config) => this.fill(config), error: () => undefined });
  }

  flagLabel(key: string): string {
    return FEATURE_FLAG_LABELS[key] ?? key;
  }

  save(): void {
    this.infoMessage.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const sections = this.changedSections();
    if (Object.keys(sections).length === 0) {
      this.infoMessage.set("Brak zmian do zapisania.");
      return;
    }

    this.adminService
      .updateConfig(sections)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.fill(config);
          this.infoMessage.set("Konfiguracja została zapisana.");
        },
        error: () => undefined,
      });
  }

  private changedSections(): PlatformConfigUpdate {
    const current = this.config();
    if (!current) return {};

    const value = this.form.getRawValue();
    const sections: PlatformConfigUpdate = {};

    if (!this.same(value.limits, current.limits)) sections.limits = value.limits;
    if (!this.same(value.llm, current.llm)) sections.llm = value.llm;
    if (!this.same(value.maintenance, current.maintenance)) {
      sections.maintenance = value.maintenance;
    }

    const flags = this.featureFlags.getRawValue();
    if (!this.same(flags, current.featureFlags)) sections.featureFlags = flags;

    return sections;
  }

  private same(left: unknown, right: unknown): boolean {
    return JSON.stringify(left) === JSON.stringify(right);
  }

  private fill(config: PlatformConfig): void {
    this.form.patchValue({
      limits: config.limits,
      llm: config.llm,
      maintenance: config.maintenance,
    });

    // Zestaw flag pochodzi z backendu — kontrolki budujemy dynamicznie.
    for (const key of Object.keys(this.featureFlags.controls)) {
      if (!(key in config.featureFlags)) this.featureFlags.removeControl(key);
    }
    for (const [key, enabled] of Object.entries(config.featureFlags)) {
      const control = this.featureFlags.controls[key];
      if (control) {
        control.setValue(enabled);
      } else {
        this.featureFlags.addControl(key, new FormControl(enabled, { nonNullable: true }));
      }
    }
  }
}
