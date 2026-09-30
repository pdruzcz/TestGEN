import {
  Component,
  computed,
  inject,
  OnInit,
  signal,
  DestroyRef,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { TestCaseService } from "../../../../test-cases/services/test-case.service";
import { TestCase } from "../../../../test-cases/models/test-case.model";
import {
  CodegenService,
  GeneratedTestCode,
} from "../../services/codegen.service";

type PhpFramework = "phpunit" | "pest";

/**
 * Story 1.55 (FR24/FR12): PHPUnit/Pest (PHP) code generator view.
 *
 * Lets the user pick PHP test cases, choose the target framework
 * (PHPUnit class style or Pest DSL) and launch asynchronous code
 * generation, then preview / download the generated .php file.
 * Mirrors DatabaseGeneratorComponent (Story 1.53).
 */
@Component({
  selector: "app-php-generator",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatCheckboxModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./php-generator.component.html",
  styleUrls: ["./php-generator.component.scss"],
})
export class PhpGeneratorComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly codegenService = inject(CodegenService);
  private readonly testCaseService = inject(TestCaseService);

  readonly testCases = signal<TestCase[]>([]);
  readonly selectedIds = signal<string[]>([]);
  readonly codeIdInput = signal("");
  readonly generatedCode = signal<GeneratedTestCode | null>(null);

  readonly isLoading = signal(false);
  readonly isGenerating = signal(false);
  readonly loadError = signal("");
  readonly infoMessage = signal("");

  /** Wybrany framework docelowy: PHPUnit (klasa) albo Pest (DSL). */
  readonly phpFramework = signal<PhpFramework>("phpunit");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  /** Tylko przypadki PHP są istotne dla tego generatora. */
  readonly phpTestCases = computed(() =>
    this.testCases().filter(
      (tc) =>
        tc.framework === "PHPUNIT" ||
        tc.framework === "PEST" ||
        (tc.language ?? "").toLowerCase() === "php",
    ),
  );

  readonly frameworkLabel = computed(() =>
    this.phpFramework() === "pest" ? "Pest" : "PHPUnit",
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
      this.loadError.set(
        "Wybierz co najmniej jeden przypadek testowy dla PHP.",
      );
      return;
    }
    this.isGenerating.set(true);
    this.loadError.set("");
    this.infoMessage.set("");
    const dispatch =
      this.phpFramework() === "pest"
        ? this.codegenService.generatePest(this.projectId(), this.selectedIds())
        : this.codegenService.generatePhpUnit(
            this.projectId(),
            this.selectedIds(),
          );
    dispatch.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (task) => {
        this.isGenerating.set(false);
        this.infoMessage.set(
          `Generowanie kodu ${this.frameworkLabel()} uruchomione (zadanie: ${task.taskId ?? "—"}). Kod będzie dostępny po zakończeniu.`,
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
    const blob = new Blob([code.code], { type: "text/x-php;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = code.filePath
      ? (code.filePath.split("/").pop() ?? "test_php.php")
      : "test_php.php";
    link.click();
    URL.revokeObjectURL(url);
  }
}
