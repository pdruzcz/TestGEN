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
import { MatCheckboxModule } from "@angular/material/checkbox";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { UmlService, UserFlow } from "../../../uml/services/uml.service";
import {
  GherkinService,
  GherkinFeature,
  GherkinFeatureListItem,
} from "../../services/gherkin.service";
import {
  ConfigService,
  engineModeLabel,
} from "../../../../../core/services/config.service";

/**
 * Story 3.11: Gherkin/BDD generator view. Lets the user pick one or more
 * reconstructed user flows, choose the engine mode (native / LLM / hybrid),
 * launch generation, browse generated features, preview the raw ``.feature``
 * text with inline validation warnings and download it.
 */
@Component({
  selector: "app-gherkin-generator",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatCheckboxModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./gherkin-generator.component.html",
  styleUrls: ["./gherkin-generator.component.scss"],
})
export class GherkinGeneratorComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly gherkinService = inject(GherkinService);
  private readonly umlService = inject(UmlService);

  readonly flows = signal<UserFlow[]>([]);
  private readonly configService = inject(ConfigService);
  readonly selectedFlowIds = signal<string[]>([]);
  readonly engineMode = computed(
    () => this.configService.configSignal().engineMode,
  );
  readonly engineModeLabel = computed(() => engineModeLabel(this.engineMode()));
  readonly featureName = signal("");

  readonly features = signal<GherkinFeatureListItem[]>([]);
  readonly selectedFeature = signal<GherkinFeature | null>(null);

  readonly isLoading = signal(false);
  readonly isGenerating = signal(false);
  readonly loadError = signal("");
  readonly infoMessage = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadFlows();
      this.loadFeatures();
    }
  }

  private loadFlows(): void {
    this.isLoading.set(true);
    this.umlService
      .listFlows(this.projectId(), 1, 100)
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

  loadFeatures(): void {
    this.gherkinService
      .listFeatures(this.projectId(), 1, 100)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => this.features.set(res.features),
        error: () => {
          /* listing is best-effort; generation errors are surfaced separately */
        },
      });
  }

  toggleFlow(flowId: string): void {
    const current = this.selectedFlowIds();
    if (current.includes(flowId)) {
      this.selectedFlowIds.set(current.filter((id) => id !== flowId));
    } else {
      this.selectedFlowIds.set([...current, flowId]);
    }
  }

  isFlowSelected(flowId: string): boolean {
    return this.selectedFlowIds().includes(flowId);
  }

  generate(): void {
    if (this.selectedFlowIds().length === 0) {
      this.loadError.set("Wybierz co najmniej jeden przepływ.");
      return;
    }
    this.isGenerating.set(true);
    this.loadError.set("");
    this.infoMessage.set("");
    this.gherkinService
      .generate(
        this.projectId(),
        this.selectedFlowIds(),
        this.featureName() || undefined,
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isGenerating.set(false);
          this.infoMessage.set(
            "Generowanie uruchomione. Lista funkcjonalności zostanie odświeżona za chwilę.",
          );
          this.selectedFlowIds.set([]);
        },
        error: (err) => {
          this.isGenerating.set(false);
          this.loadError.set(
            `Błąd generowania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  viewFeature(featureId: string): void {
    this.selectedFeature.set(null);
    this.gherkinService
      .getFeature(this.projectId(), featureId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (feature) => this.selectedFeature.set(feature),
        error: (err) => {
          this.loadError.set(
            `Błąd ładowania funkcjonalności: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  download(feature: GherkinFeature): void {
    const blob = new Blob([feature.rawFeature], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${this.slugify(feature.featureName)}.feature`;
    link.click();
    URL.revokeObjectURL(url);
  }

  private slugify(name: string): string {
    return (
      name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "feature"
    );
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      generated: "Wygenerowano",
      validated: "Zweryfikowano",
      approved: "Zatwierdzono",
    };
    return map[status] ?? status;
  }
}
