import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatChipsModule } from "@angular/material/chips";
import { MatSnackBarModule, MatSnackBar } from "@angular/material/snack-bar";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import {
  IntegrationsService,
  SyncLog,
} from "./services/integrations.service";

@Component({
  selector: "app-integrations",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    ReactiveFormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatSnackBarModule,
    NavbarComponent,
    FooterComponent,
  ],
  template: `
    <div class="int-page">
      <app-navbar activeLink="projects" />
      <main class="int-content" id="main-content" tabindex="-1">
        <a mat-button routerLink="/projects" class="back-link">
          <mat-icon>arrow_back</mat-icon>
          Wróć do projektów
        </a>

        <h1 class="page-title">Integracje</h1>

        <!-- Provider tabs -->
        <div class="provider-tabs">
          <button
            mat-stroked-button
            [color]="selectedProvider() === 'jira' ? 'primary' : ''"
            (click)="switchProvider('jira')"
          >
            <mat-icon>bug_report</mat-icon>
            Jira
          </button>
          <button
            mat-stroked-button
            [color]="selectedProvider() === 'azure_devops' ? 'primary' : ''"
            (click)="switchProvider('azure_devops')"
          >
            <mat-icon>cloud</mat-icon>
            Azure DevOps
          </button>
        </div>

        <!-- Configuration form -->
        <div class="config-card">
          <h2 class="section-title">
            <mat-icon>settings</mat-icon>
            {{ selectedProvider() === "jira" ? "Konfiguracja Jira" : "Konfiguracja Azure DevOps" }}
          </h2>

          <form [formGroup]="configForm" (ngSubmit)="saveConfig()">
            @if (selectedProvider() === "jira") {
              <div class="form-row">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>URL instancji Jira</mat-label>
                  <input matInput formControlName="baseUrl" placeholder="https://twoj-projekt.atlassian.net" />
                </mat-form-field>
              </div>
              <div class="form-row two-col">
                <mat-form-field appearance="outline">
                  <mat-label>Email</mat-label>
                  <input matInput formControlName="email" type="email" placeholder="ty@firma.pl" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>API Token</mat-label>
                  <input matInput formControlName="apiToken" type="password" placeholder="ATATT3x..." />
                </mat-form-field>
              </div>
              <div class="form-row two-col">
                <mat-form-field appearance="outline">
                  <mat-label>Klucz projektu (Project Key)</mat-label>
                  <input matInput formControlName="projectKey" placeholder="PROJ" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Typ zgłoszenia</mat-label>
                  <mat-select formControlName="issueType">
                    <mat-option value="Task">Task</mat-option>
                    <mat-option value="Bug">Bug</mat-option>
                    <mat-option value="Story">Story</mat-option>
                    <mat-option value="Sub-task">Sub-task</mat-option>
                  </mat-select>
                </mat-form-field>
              </div>
            } @else {
              <div class="form-row two-col">
                <mat-form-field appearance="outline">
                  <mat-label>Organizacja</mat-label>
                  <input matInput formControlName="organization" placeholder="my-org" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Projekt</mat-label>
                  <input matInput formControlName="project" placeholder="MyProject" />
                </mat-form-field>
              </div>
              <div class="form-row">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Personal Access Token (PAT)</mat-label>
                  <input matInput formControlName="apiToken" type="password" placeholder="xxxxxxxx..." />
                </mat-form-field>
              </div>
              <div class="form-row">
                <mat-form-field appearance="outline">
                  <mat-label>Typ work item</mat-label>
                  <mat-select formControlName="issueType">
                    <mat-option value="Task">Task</mat-option>
                    <mat-option value="Bug">Bug</mat-option>
                    <mat-option value="User Story">User Story</mat-option>
                    <mat-option value="Issue">Issue</mat-option>
                  </mat-select>
                </mat-form-field>
              </div>
            }

            <div class="form-actions">
              <button mat-raised-button color="primary" type="submit" [disabled]="saving()">
                <mat-icon>{{ saving() ? "hourglass_empty" : "save" }}</mat-icon>
                Zapisz konfigurację
              </button>
              <button mat-stroked-button type="button" (click)="testConnection()" [disabled]="testing()">
                <mat-icon>{{ testing() ? "hourglass_empty" : "wifi_tethering" }}</mat-icon>
                Test połączenia
              </button>
            </div>
          </form>

          @if (testResult()) {
            <div class="test-result" [class.success]="testResult()!.connected" [class.error]="!testResult()!.connected">
              <mat-icon>{{ testResult()!.connected ? "check_circle" : "error" }}</mat-icon>
              {{ testResult()!.message }}
            </div>
          }
        </div>

        <!-- Sync section -->
        <div class="sync-card">
          <h2 class="section-title">
            <mat-icon>sync</mat-icon>
            Synchronizacja ({{ selectedProvider() === "jira" ? "Jira" : "Azure DevOps" }})
          </h2>

          <div class="sync-actions">
            <button mat-raised-button color="primary" (click)="sync('gap_findings')" [disabled]="syncing()">
              <mat-icon>{{ syncing() ? "hourglass_empty" : "cloud_upload" }}</mat-icon>
              Sync luk funkcjonalnych
            </button>
            <button mat-raised-button color="accent" (click)="sync('recommendations')" [disabled]="syncing()">
              <mat-icon>{{ syncing() ? "hourglass_empty" : "cloud_upload" }}</mat-icon>
              Sync rekomendacji
            </button>
          </div>

          @if (syncResult()) {
            @let r = syncResult()!;
            <div class="sync-result">
              <mat-chip-set>
                <mat-chip>
                  <mat-icon matChipAvatar class="chip-info">analytics</mat-icon>
                  Wysłano: {{ r.synced }} / {{ r.total }}
                </mat-chip>
                @if (r.errors.length > 0) {
                  <mat-chip>
                    <mat-icon matChipAvatar class="chip-red">error</mat-icon>
                    Błędy: {{ r.errors.length }}
                  </mat-chip>
                }
              </mat-chip-set>
              @if (r.errors.length > 0) {
                <ul class="error-list">
                  @for (e of r.errors; track $index) {
                    <li>{{ e | json }}</li>
                  }
                </ul>
              }
            </div>
          }
        </div>

        <!-- Story 8.8/8.9 — ekrany TMS żyją pod własnymi trasami; bez tych
             odnośników dało się do nich trafić wyłącznie z paska adresu,
             choć komunikat błędu eksportu odsyła do ustawień projektu. -->
        <div class="tms-card">
          <h2 class="section-title">
            <mat-icon>fact_check</mat-icon>
            Systemy zarządzania testami
          </h2>
          <p class="tms-hint">
            Połączenie potrzebne do eksportu przypadków testowych prosto z listy testów
            i do synchronizacji dwukierunkowej.
          </p>
          <div class="tms-links">
            <a mat-stroked-button color="primary" [routerLink]="['/projects', projectId(), 'integrations', 'testrail']">
              <mat-icon>checklist</mat-icon>
              TestRail
            </a>
            <a mat-stroked-button color="primary" [routerLink]="['/projects', projectId(), 'integrations', 'jira']">
              <mat-icon>bug_report</mat-icon>
              Jira Xray / Zephyr Scale
            </a>
            <a mat-stroked-button color="primary" [routerLink]="['/projects', projectId(), 'import', 'jira']">
              <mat-icon>download</mat-icon>
              Import wymagań z Jiry
            </a>
          </div>
        </div>

        <!-- Sync logs -->
        @if (logs().length > 0) {
          <div class="logs-card">
            <h2 class="section-title">
              <mat-icon>history</mat-icon>
              Historia synchronizacji
            </h2>
            <div class="logs-list">
              @for (log of logs(); track log.id) {
                <div class="log-item">
                  <mat-icon [class.success]="log.status === 'success'" [class.error]="log.status === 'failed'" [class.warning]="log.status === 'partial'">
                    {{ log.status === "success" ? "check_circle" : log.status === "failed" ? "cancel" : "warning" }}
                  </mat-icon>
                  <div class="log-info">
                    <span class="log-type">{{ log.syncType }}</span>
                    <span class="log-date">{{ log.createdAt | date: "short" }}</span>
                  </div>
                  <span class="log-counts">{{ log.itemsSynced }}/{{ log.itemsTotal }}</span>
                </div>
              }
            </div>
          </div>
        }
      </main>
      <app-footer />
    </div>
  `,
  styles: [`
    .int-page { min-height: 100vh; display: flex; flex-direction: column; }
    .int-content { max-width: 800px; width: 100%; margin: 0 auto; padding: 24px; flex: 1; }
    .back-link { margin-bottom: 16px; }
    .page-title { font-size: 24px; margin: 0 0 24px; }
    .config-card, .sync-card, .logs-card, .tms-card {
      background: white; border-radius: 12px; padding: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px;
    }
    .section-title {
      display: flex; align-items: center; gap: 8px;
      font-size: 18px; margin: 0 0 16px;
    }
    .form-row { margin-bottom: 12px; }
    .form-row.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .full-width { width: 100%; }
    .form-actions { display: flex; gap: 12px; margin-top: 16px; }
    .test-result {
      display: flex; align-items: center; gap: 8px;
      padding: 12px; border-radius: 8px; margin-top: 12px;
    }
    .test-result.success { background: #e8f5e9; color: #2e7d32; }
    .test-result.error { background: #ffebee; color: #c62828; }
    .sync-actions { display: flex; gap: 12px; margin-bottom: 16px; }
    .sync-result { margin-top: 12px; }
    .chip-info { color: #1976d2; }
    .chip-red { color: #f44336; }
    .error-list { color: #c62828; font-size: 13px; margin-top: 8px; padding-left: 20px; }
    .tms-hint { font-size: 14px; color: #555; margin: 0 0 16px; }
    .tms-links { display: flex; flex-wrap: wrap; gap: 12px; }
    .logs-list { display: flex; flex-direction: column; gap: 8px; }
    .log-item {
      display: flex; align-items: center; gap: 12px;
      padding: 8px 12px; border-radius: 8px; background: #fafafa;
    }
    .log-info { flex: 1; display: flex; flex-direction: column; }
    .log-type { font-weight: 500; }
    .log-date { font-size: 12px; color: #666; }
    .log-counts { font-weight: 600; }
    .success { color: #4caf50; }
    .error { color: #f44336; }
    .warning { color: #ff9800; }
  `],
})
export class IntegrationsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly intService = inject(IntegrationsService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = signal<string>("");
  readonly selectedProvider = signal<"jira" | "azure_devops">("jira");
  readonly saving = signal(false);
  readonly testing = signal(false);
  readonly syncing = signal(false);
  readonly testResult = signal<{ connected: boolean; message: string } | null>(null);
  readonly syncResult = signal<{ total: number; synced: number; errors: Array<Record<string, string>> } | null>(null);
  readonly logs = signal<SyncLog[]>([]);

  readonly configForm = this.fb.group({
    baseUrl: ["", [Validators.required]],
    email: ["", [Validators.email]],
    apiToken: ["", [Validators.required]],
    projectKey: ["", []],
    issueType: ["Task", []],
    organization: ["", []],
    project: ["", []],
  });

  ngOnInit(): void {
    const pid = this.route.snapshot.paramMap.get("projectId") ?? "";
    this.projectId.set(pid);
    this.loadConfig();
    this.loadLogs();
  }

  switchProvider(provider: "jira" | "azure_devops"): void {
    if (this.selectedProvider() === provider) return;
    this.selectedProvider.set(provider);
    this.testResult.set(null);
    this.syncResult.set(null);
    this.configForm.reset({ issueType: "Task" });
    this.loadConfig();
    this.loadLogs();
  }

  loadConfig(): void {
    this.intService.getConfig(this.projectId(), this.selectedProvider()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (cfg) => {
          if (cfg) {
            this.configForm.patchValue({
              baseUrl: cfg.baseUrl,
              projectKey: (cfg.settings as any)?.project_key ?? "",
              issueType: (cfg.settings as any)?.issue_type ?? "Task",
              organization: (cfg.settings as any)?.organization ?? "",
              project: (cfg.settings as any)?.project ?? "",
            });
          }
        },
      });
  }

  saveConfig(): void {
    if (this.configForm.invalid) return;
    this.saving.set(true);
    const v = this.configForm.value;
    const provider = this.selectedProvider();
    this.intService.configure(this.projectId(), {
      provider,
      baseUrl: provider === "jira" ? v.baseUrl! : `https://dev.azure.com/${v.organization}`,
      email: v.email ?? "",
      apiToken: v.apiToken!,
      projectKey: v.projectKey ?? "",
      issueType: v.issueType ?? "Task",
      organization: v.organization ?? "",
      project: v.project ?? "",
    }).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.snackBar.open("Konfiguracja zapisana", "OK", { duration: 3000 });
        },
        error: () => {
          this.saving.set(false);
          this.snackBar.open("Błąd zapisu konfiguracji", "OK", { duration: 3000 });
        },
      });
  }

  testConnection(): void {
    this.testing.set(true);
    this.testResult.set(null);
    this.intService.testConnection(this.projectId(), this.selectedProvider()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (r) => {
          this.testing.set(false);
          this.testResult.set(r);
        },
        error: () => {
          this.testing.set(false);
          this.testResult.set({ connected: false, message: "Błąd połączenia" });
        },
      });
  }

  sync(syncType: "gap_findings" | "recommendations"): void {
    this.syncing.set(true);
    this.syncResult.set(null);
    this.intService.sync(this.projectId(), { syncType }, this.selectedProvider()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (r) => {
          this.syncing.set(false);
          this.syncResult.set(r);
          this.snackBar.open(`Zsynchronizowano ${r.synced}/${r.total}`, "OK", { duration: 3000 });
          this.loadLogs();
        },
        error: () => {
          this.syncing.set(false);
          this.snackBar.open("Błąd synchronizacji", "OK", { duration: 3000 });
        },
      });
  }

  loadLogs(): void {
    this.intService.getLogs(this.projectId(), this.selectedProvider()).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: (l) => this.logs.set(l) });
  }
}
