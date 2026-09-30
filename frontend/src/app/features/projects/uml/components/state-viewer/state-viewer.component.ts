import { Component, DestroyRef, OnInit, computed, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import {
  UmlService,
  UMLDiagramDetail,
  StateNode,
  StateTransition,
  CompositeState,
  StateScenario,
} from "../../services/uml.service";

@Component({
  selector: "app-state-viewer",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./state-viewer.component.html",
  styleUrls: ["./state-viewer.component.scss"],
})
export class StateViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly umlService = inject(UmlService);

  readonly isLoading = signal(true);
  readonly detail = signal<UMLDiagramDetail | null>(null);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );
  readonly diagramId = computed(
    () => this.route.snapshot.paramMap.get("diagramId") ?? "",
  );

  readonly states = computed<StateNode[]>(
    () =>
      ((this.detail()?.parsedModel?.elements as unknown as StateNode[]) ?? []).filter(
        (s) => !s.isInitial && !s.isFinal,
      ),
  );
  readonly transitions = computed<StateTransition[]>(
    () =>
      (this.detail()?.parsedModel?.relationships as unknown as StateTransition[]) ?? [],
  );
  readonly composites = computed<CompositeState[]>(() => {
    const fragments =
      (this.detail()?.parsedModel?.fragments as unknown as CompositeState[]) ?? [];
    return fragments.filter((f) => Array.isArray(f.childIds));
  });
  readonly scenarios = computed<StateScenario[]>(
    () => (this.detail()?.parsedModel?.flows as unknown as StateScenario[]) ?? [],
  );
  readonly warnings = computed<string[]>(() => {
    const fragments =
      (this.detail()?.parsedModel?.fragments as unknown as Record<string, unknown>[]) ??
      [];
    const entry = fragments.find((f) => "__warnings__" in f);
    return (entry?.["__warnings__"] as string[]) ?? [];
  });

  readonly transitionScenarios = computed(() =>
    this.scenarios().filter((s) => s.scenarioType === "transition"),
  );
  readonly stateScenarios = computed(() =>
    this.scenarios().filter((s) => s.scenarioType === "state"),
  );
  readonly pathScenarios = computed(() =>
    this.scenarios().filter((s) => s.scenarioType === "path"),
  );
  readonly negativeScenarios = computed(() =>
    this.scenarios().filter((s) => s.isNegative),
  );

  ngOnInit(): void {
    this.umlService
      .getDiagram(this.projectId(), this.diagramId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (detail) => {
          this.detail.set(detail);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false),
      });
  }

  stateName(id: string): string {
    return this.states().find((s) => s.id === id)?.name || id;
  }
}
