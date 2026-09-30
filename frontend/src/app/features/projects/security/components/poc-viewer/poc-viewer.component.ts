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
  ProofOfConcept,
  SecurityFinding,
  SecurityScanService,
} from "../../services/security-scan.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

/**
 * Story 4.10: proof-of-concept viewer. Generates a safe, non-destructive PoC for
 * an injection finding on demand and renders the payload (copyable), numbered
 * reproduction steps, the expected effect and a mandatory safety disclaimer.
 */
@Component({
  selector: "app-poc-viewer",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./poc-viewer.component.html",
  styleUrls: ["./poc-viewer.component.scss"],
})
export class PocViewerComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();
  readonly finding = input.required<SecurityFinding>();

  readonly poc = signal<ProofOfConcept | null>(null);
  readonly isLoading = signal(false);
  private readonly configService = inject(ConfigService);
  readonly errorMessage = signal<string | null>(null);
  readonly engineMode = computed(
    () => this.configService.configSignal().engineMode,
  );
  readonly engineModeLabel = computed(() => engineModeLabel(this.engineMode()));
  readonly copied = signal(false);

  generate(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.copied.set(false);
    this.service
      .generatePoc(this.projectId(), this.finding().id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.poc.set(res);
          this.isLoading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(
            err?.status === 422
              ? "Generowanie PoC nie jest wspierane dla tego typu podatności."
              : "Nie udało się wygenerować PoC.",
          );
          this.isLoading.set(false);
        },
      });
  }

  copyPayload(): void {
    const payload = this.poc()?.payload;
    if (!payload) return;
    void navigator.clipboard?.writeText(payload).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }
}
