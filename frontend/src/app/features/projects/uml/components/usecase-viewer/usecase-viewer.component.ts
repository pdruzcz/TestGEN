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
  UseCaseActor,
  UseCaseItem,
  UseCaseRelationship,
  UseCaseSystemBoundary,
  UseCaseScenario,
} from "../../services/uml.service";

@Component({
  selector: "app-usecase-viewer",
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
  templateUrl: "./usecase-viewer.component.html",
  styleUrls: ["./usecase-viewer.component.scss"],
})
export class UsecaseViewerComponent implements OnInit {
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

  readonly actors = computed<UseCaseActor[]>(
    () => (this.detail()?.parsedModel?.participants as unknown as UseCaseActor[]) ?? [],
  );
  readonly useCases = computed<UseCaseItem[]>(
    () => (this.detail()?.parsedModel?.elements as unknown as UseCaseItem[]) ?? [],
  );
  readonly relationships = computed<UseCaseRelationship[]>(
    () =>
      (this.detail()?.parsedModel?.relationships as unknown as UseCaseRelationship[]) ?? [],
  );
  readonly systemBoundary = computed<UseCaseSystemBoundary | null>(() => {
    const fragments = this.detail()?.parsedModel?.fragments as unknown as
      | UseCaseSystemBoundary[]
      | null;
    return fragments && fragments.length > 0 ? fragments[0] : null;
  });
  readonly scenarios = computed<UseCaseScenario[]>(
    () => (this.detail()?.parsedModel?.flows as unknown as UseCaseScenario[]) ?? [],
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

  relationshipLabel(type: string): string {
    const map: Record<string, string> = {
      association: "asocjacja",
      include: "«include»",
      extend: "«extend»",
      generalization: "dziedziczenie",
    };
    return map[type] ?? type;
  }

  scenarioLabel(type: string): string {
    const map: Record<string, string> = {
      main: "Główny",
      alternative: "Alternatywny",
      included: "Współdzielony",
    };
    return map[type] ?? type;
  }
}
