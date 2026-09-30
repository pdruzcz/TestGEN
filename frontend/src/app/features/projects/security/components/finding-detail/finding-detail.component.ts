import {
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import {
  Recommendation,
  SecurityFinding,
  SecurityScanService,
} from "../../services/security-scan.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

type DiffLine = { text: string; kind: "add" | "del" | "meta" | "context" };

/**
 * Story 4.9: vulnerability detail with an on-demand remediation recommendation.
 * Renders the problem / risk / fix narrative plus a GitHub-style unified diff
 * (vulnerable lines red, fixed lines green) and a copy-code action.
 */
@Component({
  selector: "app-finding-detail",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./finding-detail.component.html",
  styleUrls: ["./finding-detail.component.scss"],
})
export class FindingDetailComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();
  readonly finding = input.required<SecurityFinding>();

  readonly recommendation = signal<Recommendation | null>(null);
  private readonly configService = inject(ConfigService);
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly engineMode = computed(
    () => this.configService.configSignal().engineMode,
  );
  readonly engineModeLabel = computed(() => engineModeLabel(this.engineMode()));
  readonly copied = signal(false);

  readonly diffLines = computed<DiffLine[]>(() => {
    const diff = this.recommendation()?.diff ?? "";
    if (!diff) return [];
    return diff
      .split("\n")
      .map((text) => ({ text, kind: this.classify(text) }));
  });

  private classify(line: string): DiffLine["kind"] {
    if (
      line.startsWith("+++") ||
      line.startsWith("---") ||
      line.startsWith("@@")
    ) {
      return "meta";
    }
    if (line.startsWith("+")) return "add";
    if (line.startsWith("-")) return "del";
    return "context";
  }

  generate(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.copied.set(false);
    this.service
      .generateRecommendation(this.projectId(), this.finding().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.recommendation.set(res);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się wygenerować rekomendacji.");
          this.isLoading.set(false);
        },
      });
  }

  copyCode(): void {
    const code = this.recommendation()?.fixedCodeSnippet;
    if (!code) return;
    void navigator.clipboard?.writeText(code).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }
}
