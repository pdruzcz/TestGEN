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
  ClassElement,
  ClassRelationship,
  ClassPackage,
  DiagramCodeComparison,
} from "../../services/uml.service";

@Component({
  selector: "app-class-viewer",
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
  templateUrl: "./class-viewer.component.html",
  styleUrls: ["./class-viewer.component.scss"],
})
export class ClassViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly umlService = inject(UmlService);

  readonly isLoading = signal(true);
  readonly detail = signal<UMLDiagramDetail | null>(null);
  readonly comparison = signal<DiagramCodeComparison | null>(null);
  readonly isComparing = signal(false);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );
  readonly diagramId = computed(
    () => this.route.snapshot.paramMap.get("diagramId") ?? "",
  );

  private readonly elements = computed<ClassElement[]>(
    () => (this.detail()?.parsedModel?.elements as unknown as ClassElement[]) ?? [],
  );

  readonly classes = computed<ClassElement[]>(
    () => this.elements().filter((e) => e.elementKind === "class"),
  );
  readonly interfaces = computed<ClassElement[]>(
    () => this.elements().filter((e) => e.elementKind === "interface"),
  );
  readonly enumerations = computed<ClassElement[]>(
    () => this.elements().filter((e) => e.elementKind === "enum"),
  );
  readonly relationships = computed<ClassRelationship[]>(
    () =>
      (this.detail()?.parsedModel?.relationships as unknown as ClassRelationship[]) ?? [],
  );
  readonly packages = computed<ClassPackage[]>(
    () => (this.detail()?.parsedModel?.fragments as unknown as ClassPackage[]) ?? [],
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

  runComparison(): void {
    this.isComparing.set(true);
    this.umlService
      .compareCode(this.projectId(), this.diagramId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.comparison.set(result);
          this.isComparing.set(false);
        },
        error: () => this.isComparing.set(false),
      });
  }

  relationshipLabel(type: string): string {
    const map: Record<string, string> = {
      inheritance: "dziedziczenie",
      implementation: "implementacja",
      association: "asocjacja",
      aggregation: "agregacja",
      composition: "kompozycja",
      dependency: "zależność",
    };
    return map[type] ?? type;
  }

  severityLabel(severity: string): string {
    const map: Record<string, string> = {
      error: "Krytyczne",
      warning: "Ostrzeżenie",
      info: "Informacja",
    };
    return map[severity] ?? severity;
  }
}
