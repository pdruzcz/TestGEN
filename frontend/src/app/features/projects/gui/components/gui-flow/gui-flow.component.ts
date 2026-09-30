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
import { MatSelectModule } from "@angular/material/select";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { GuiService, GUIUserFlow } from "../../services/gui.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

/**
 * Story 3.9: viewer for GUI user flows reconstructed from screenshot sequences.
 * Lets the user trigger reconstruction (native / LLM / hybrid) and browse the
 * resulting transitions (screen A -> action -> screen B).
 */
@Component({
  selector: "app-gui-flow",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./gui-flow.component.html",
  styleUrls: ["./gui-flow.component.scss"],
})
export class GuiFlowComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly guiService = inject(GuiService);

  readonly flows = signal<GUIUserFlow[]>([]);
  readonly isLoading = signal(false);
  readonly isReconstructing = signal(false);
  readonly loadError = signal("");
  private readonly configService = inject(ConfigService);
  readonly infoMessage = signal("");
  readonly engineMode = computed(
    () => this.configService.configSignal().engineMode,
  );
  readonly engineModeLabel = computed(() => engineModeLabel(this.engineMode()));

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.load();
    }
  }

  private load(): void {
    this.isLoading.set(true);
    this.loadError.set("");
    this.guiService
      .listFlows(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.flows.set(res.flows);
          this.isLoading.set(false);
        },
        error: (err) => {
          this.loadError.set(
            `Błąd ładowania przepływów: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
          this.isLoading.set(false);
        },
      });
  }

  reconstruct(): void {
    this.isReconstructing.set(true);
    this.infoMessage.set("");
    this.loadError.set("");
    this.guiService
      .reconstructFlows(this.projectId(), null)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isReconstructing.set(false);
          this.infoMessage.set(
            "Rekonstrukcja przepływu została uruchomiona. Odśwież listę za chwilę.",
          );
        },
        error: (err) => {
          this.isReconstructing.set(false);
          this.loadError.set(
            `Błąd uruchamiania rekonstrukcji: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  refresh(): void {
    this.load();
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      draft: "Szkic",
      validated: "Zweryfikowany",
      tests_generated: "Wygenerowano testy",
    };
    return map[status] ?? status;
  }
}
