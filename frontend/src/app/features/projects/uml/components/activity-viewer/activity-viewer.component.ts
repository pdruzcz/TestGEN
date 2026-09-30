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
  ActivityNode,
  ActivityEdge,
  ActivitySwimlane,
  ActivityScenario,
} from "../../services/uml.service";

@Component({
  selector: "app-activity-viewer",
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
  templateUrl: "./activity-viewer.component.html",
  styleUrls: ["./activity-viewer.component.scss"],
})
export class ActivityViewerComponent implements OnInit {
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

  readonly nodes = computed<ActivityNode[]>(
    () => (this.detail()?.parsedModel?.elements as unknown as ActivityNode[]) ?? [],
  );
  readonly edges = computed<ActivityEdge[]>(
    () =>
      (this.detail()?.parsedModel?.relationships as unknown as ActivityEdge[]) ?? [],
  );
  readonly swimlanes = computed<ActivitySwimlane[]>(() => {
    const fragments =
      (this.detail()?.parsedModel?.fragments as unknown as ActivitySwimlane[]) ?? [];
    // The last fragment may carry parser warnings under __warnings__; skip it.
    return fragments.filter((f) => Array.isArray(f.nodeIds));
  });
  readonly scenarios = computed<ActivityScenario[]>(
    () => (this.detail()?.parsedModel?.flows as unknown as ActivityScenario[]) ?? [],
  );
  readonly warnings = computed<string[]>(() => {
    const fragments =
      (this.detail()?.parsedModel?.fragments as unknown as Record<string, unknown>[]) ??
      [];
    const entry = fragments.find((f) => "__warnings__" in f);
    return (entry?.["__warnings__"] as string[]) ?? [];
  });

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

  nodeLabel(type: string): string {
    const map: Record<string, string> = {
      start: "Start",
      stop: "Koniec",
      action: "Akcja",
      decision: "Decyzja",
      merge: "Złączenie",
      fork: "Rozdzielenie",
      join: "Synchronizacja",
    };
    return map[type] ?? type;
  }

  scenarioLabel(type: string): string {
    const map: Record<string, string> = {
      main: "Główny",
      alternative: "Alternatywny",
    };
    return map[type] ?? type;
  }

  nodeName(id: string): string {
    return this.nodes().find((n) => n.id === id)?.name || id;
  }
}
