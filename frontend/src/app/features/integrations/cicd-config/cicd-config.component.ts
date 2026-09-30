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
import {
  CicdConfig,
  CicdPlatform,
  CicdService,
  CicdTemplateInfo,
  EngineMode,
  SeverityThreshold,
} from '../../../core/services/cicd.service';

/** Opisy parametrów po polsku — backend oddaje same identyfikatory. */
const MODULE_LABELS: Record<string, string> = {
  code_analysis: 'Analiza kodu',
  doc_analysis: 'Analiza dokumentacji',
  security_scan: 'Skan bezpieczeństwa',
  uml_analysis: 'Analiza UML',
};

const THRESHOLD_LABELS: Record<string, string> = {
  critical: 'Krytyczny',
  high: 'Wysoki',
  medium: 'Średni',
};

const ENGINE_LABELS: Record<string, string> = {
  native: 'Natywny (deterministyczny)',
  llm: 'LLM (semantyczny)',
  hybrid: 'Hybrydowy',
};

@Component({
  selector: 'app-cicd-config',
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
  templateUrl: './cicd-config.component.html',
  styleUrls: ['./cicd-config.component.scss'],
})
export class CicdConfigComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly cicdService = inject(CicdService);

  readonly platforms = this.cicdService.templatesSignal;
  readonly isLoading = this.cicdService.isLoadingSignal;

  readonly projectId = signal('');
  readonly errorMessage = signal<string | null>(null);
  readonly copyMessage = signal<string | null>(null);

  readonly availableModules = signal<string[]>([]);
  readonly availableThresholds = signal<SeverityThreshold[]>([]);
  readonly availableEngineModes = signal<EngineMode[]>([]);
  readonly apiKeyVariable = signal('TESTGEN_API_KEY');

  readonly platform = signal<CicdPlatform>('github_actions');
  readonly threshold = signal<SeverityThreshold>('critical');
  readonly engineMode = signal<EngineMode>('native');
  readonly modules = signal<string[]>(['code_analysis']);
  readonly timeoutMinutes = signal(30);

  readonly config = signal<CicdConfig | null>(null);
  readonly isGenerating = signal(false);

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('projectId') ?? '';
    this.projectId.set(projectId);

    this.cicdService
      .getTemplates(projectId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.availableModules.set(result.availableModules ?? []);
          this.availableThresholds.set(result.availableThresholds ?? []);
          this.availableEngineModes.set(result.availableEngineModes ?? []);
          this.apiKeyVariable.set(result.apiKeyVariable);
          // Pierwsza konfiguracja od razu — podgląd nie powinien być pusty.
          this.regenerate();
        },
        error: () => this.errorMessage.set('Nie udało się wczytać listy platform CI/CD.'),
      });
  }

  moduleLabel(module: string): string {
    return MODULE_LABELS[module] ?? module;
  }

  thresholdLabel(threshold: string): string {
    return THRESHOLD_LABELS[threshold] ?? threshold;
  }

  engineLabel(mode: string): string {
    return ENGINE_LABELS[mode] ?? mode;
  }

  platformInfo(): CicdTemplateInfo | undefined {
    return this.platforms().find((p) => p.platform === this.platform());
  }

  isModuleSelected(module: string): boolean {
    return this.modules().includes(module);
  }

  /** Ostatni wybrany moduł zostaje — analiza bez modułów nie ma sensu. */
  toggleModule(module: string): void {
    const current = this.modules();
    if (current.includes(module)) {
      if (current.length === 1) {
        return;
      }
      this.modules.set(current.filter((m) => m !== module));
    } else {
      this.modules.set([...current, module]);
    }
    this.regenerate();
  }

  selectPlatform(platform: CicdPlatform): void {
    this.platform.set(platform);
    this.regenerate();
  }

  setThreshold(value: string): void {
    this.threshold.set(value as SeverityThreshold);
    this.regenerate();
  }

  setEngineMode(value: string): void {
    this.engineMode.set(value as EngineMode);
    this.regenerate();
  }

  setTimeout(value: string | number): void {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > 180) {
      return;
    }
    this.timeoutMinutes.set(Math.trunc(parsed));
    this.regenerate();
  }

  /** Regeneracja po każdej zmianie parametru (AC6). */
  regenerate(): void {
    const projectId = this.projectId();
    if (!projectId || this.isGenerating()) {
      return;
    }
    this.isGenerating.set(true);
    this.errorMessage.set(null);
    this.copyMessage.set(null);

    this.cicdService
      .generateConfig(projectId, {
        platform: this.platform(),
        severityThreshold: this.threshold(),
        modules: this.modules(),
        engineMode: this.engineMode(),
        timeoutMinutes: this.timeoutMinutes(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (config) => {
          this.config.set(config);
          this.isGenerating.set(false);
        },
        error: (err: { error?: { detail?: string } }) => {
          this.isGenerating.set(false);
          this.errorMessage.set(err?.error?.detail ?? 'Nie udało się wygenerować konfiguracji.');
        },
      });
  }

  copy(): void {
    const config = this.config();
    if (!config) {
      return;
    }
    void this.cicdService.copyToClipboard(config.content).then((ok) => {
      this.copyMessage.set(
        ok ? 'Skopiowano do schowka.' : 'Przeglądarka odmówiła dostępu do schowka — zaznacz i skopiuj ręcznie.',
      );
    });
  }

  download(): void {
    const config = this.config();
    if (config) {
      this.cicdService.downloadFile(config.filename, config.content);
    }
  }
}
