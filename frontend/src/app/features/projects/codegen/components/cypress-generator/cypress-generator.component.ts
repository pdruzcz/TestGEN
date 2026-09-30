import {
  Component,
  inject,
  signal,
  computed,
  OnInit,
  DestroyRef,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { TestCaseService } from "../../../../test-cases/services/test-case.service";
import { TestCase } from "../../../../test-cases/models/test-case.model";
import {
  CodegenService,
  CodeGenFramework,
  GeneratedTestCode,
} from "../../services/codegen.service";

/**
 * Story 3.12: Cypress code generator view. Lets the user pick e2e/GUI test
 * cases, supply a base URL, launch asynchronous Cypress (.cy.ts) generation
 * and preview a generated file fetched by its code id.
 *
 * Story 1.56: universal E2E generator — the framework select also offers
 * Selenium (.py), Playwright (.spec.ts) and Appium (.py + platform); each
 * dispatches its own /codegen endpoint.
 */
interface GeneratorFrameworkOption {
  value: CodeGenFramework;
  label: string;
  buttonLabel: string;
}

/** Stories 1.56/1.57 — fallbackowe nazwy plików pobierania per framework. */
const DOWNLOAD_FILE_NAMES: Record<string, string> = {
  cypress: "test.cy.ts",
  sikulix: "test.py",
  selenium: "test.py",
  playwright: "test.spec.ts",
  appium: "test.py",
  unittest: "test.py",
  testng: "test.java",
  mstest: "test.cs",
};

@Component({
  selector: "app-cypress-generator",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatCheckboxModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./cypress-generator.component.html",
  styleUrls: ["./cypress-generator.component.scss"],
})
export class CypressGeneratorComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly codegenService = inject(CodegenService);
  private readonly testCaseService = inject(TestCaseService);

  readonly testCases = signal<TestCase[]>([]);
  readonly selectedIds = signal<string[]>([]);
  readonly framework = signal<CodeGenFramework>("cypress");
  /** Story 1.56 — platforma urządzenia dla Appium (desired capabilities). */
  readonly platform = signal<"android" | "ios">("android");
  readonly baseUrl = signal("");
  readonly codeIdInput = signal("");

  /** Stories 1.56/1.57 — select frameworka: 5 opcji E2E + 3 natywne jednostkowe. */
  readonly frameworkOptions: ReadonlyArray<GeneratorFrameworkOption> = [
    {
      value: "cypress",
      label: "Cypress (.cy.ts, web/DOM)",
      buttonLabel: "Cypress",
    },
    {
      value: "sikulix",
      label: "SikuliX (.py, image-based)",
      buttonLabel: "SikuliX",
    },
    {
      value: "selenium",
      label: "Selenium (.py, E2E web)",
      buttonLabel: "Selenium",
    },
    {
      value: "playwright",
      label: "Playwright (.spec.ts, E2E web)",
      buttonLabel: "Playwright",
    },
    {
      value: "appium",
      label: "Appium (.py, E2E mobilne)",
      buttonLabel: "Appium",
    },
    {
      value: "unittest",
      label: "unittest (.py, TestCase)",
      buttonLabel: "unittest",
    },
    {
      value: "testng",
      label: "TestNG (.java, adnotacje)",
      buttonLabel: "TestNG",
    },
    {
      value: "mstest",
      label: "MSTest (.cs, [TestClass])",
      buttonLabel: "MSTest",
    },
  ];

  readonly selectedOption = computed(
    () =>
      this.frameworkOptions.find((o) => o.value === this.framework()) ??
      this.frameworkOptions[0],
  );

  readonly generatedCode = signal<GeneratedTestCode | null>(null);

  readonly isLoading = signal(false);
  readonly isGenerating = signal(false);
  readonly loadError = signal("");
  readonly infoMessage = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadTestCases();
    }
  }

  private loadTestCases(): void {
    this.isLoading.set(true);
    this.testCaseService
      .list({ projectId: this.projectId(), page: 1, pageSize: 100 })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.testCases.set(res.testCases);
          this.isLoading.set(false);
        },
        error: (err) => {
          this.loadError.set(
            `Błąd ładowania przypadków testowych: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
          this.isLoading.set(false);
        },
      });
  }

  toggle(id: string): void {
    const current = this.selectedIds();
    if (current.includes(id)) {
      this.selectedIds.set(current.filter((x) => x !== id));
    } else {
      this.selectedIds.set([...current, id]);
    }
  }

  isSelected(id: string): boolean {
    return this.selectedIds().includes(id);
  }

  generate(): void {
    if (this.selectedIds().length === 0) {
      this.loadError.set("Wybierz co najmniej jeden przypadek testowy.");
      return;
    }
    this.isGenerating.set(true);
    this.loadError.set("");
    this.infoMessage.set("");
    const request$ = this.dispatchRequest();
    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (task) => {
        this.isGenerating.set(false);
        this.infoMessage.set(
          `Generowanie uruchomione (zadanie: ${task.taskId ?? "—"}). Kod będzie dostępny po zakończeniu.`,
        );
        this.selectedIds.set([]);
      },
      error: (err) => {
        this.isGenerating.set(false);
        this.loadError.set(
          `Błąd generowania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
        );
      },
    });
  }

  fetchCode(): void {
    const codeId = this.codeIdInput().trim();
    if (!codeId) {
      this.loadError.set("Podaj identyfikator wygenerowanego kodu.");
      return;
    }
    this.generatedCode.set(null);
    this.codegenService
      .getCode(this.projectId(), codeId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (code) => this.generatedCode.set(code),
        error: (err) => {
          this.loadError.set(
            `Błąd pobierania kodu: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  download(code: GeneratedTestCode): void {
    const blob = new Blob([code.code], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = this.downloadFileName(code.framework, code.filePath);
    link.click();
    URL.revokeObjectURL(url);
  }

  /** Story 1.56 — nazwa pliku pobierania: ścieżka z serwera, fallback per framework. */
  downloadFileName(framework: string, filePath: string | null): string {
    if (filePath) {
      return filePath.split("/").pop()!;
    }
    return DOWNLOAD_FILE_NAMES[framework] ?? "test.txt";
  }

  /** Story 1.56 — rozszerzenie dla etykiety przycisku pobierania. */
  downloadExtension(framework: string): string {
    const name = DOWNLOAD_FILE_NAMES[framework] ?? "test.txt";
    const dot = name.indexOf(".");
    return name.slice(dot);
  }

  private dispatchRequest() {
    switch (this.framework()) {
      case "sikulix":
        return this.codegenService.generateSikulix(
          this.projectId(),
          this.selectedIds(),
        );
      case "selenium":
        return this.codegenService.generateSelenium(
          this.projectId(),
          this.selectedIds(),
        );
      case "playwright":
        return this.codegenService.generatePlaywright(
          this.projectId(),
          this.selectedIds(),
        );
      case "appium":
        return this.codegenService.generateAppium(
          this.projectId(),
          this.selectedIds(),
          this.platform(),
        );
      case "unittest":
        return this.codegenService.generateUnittest(
          this.projectId(),
          this.selectedIds(),
        );
      case "testng":
        return this.codegenService.generateTestNg(
          this.projectId(),
          this.selectedIds(),
        );
      case "mstest":
        return this.codegenService.generateMsTest(
          this.projectId(),
          this.selectedIds(),
        );
      default:
        return this.codegenService.generateCypress(
          this.projectId(),
          this.selectedIds(),
          this.baseUrl() || undefined,
        );
    }
  }
}
