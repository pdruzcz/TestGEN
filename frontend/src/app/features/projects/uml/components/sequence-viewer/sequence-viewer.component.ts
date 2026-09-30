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
  SequenceParticipant,
  SequenceMessage,
  SequenceFragment,
  SequenceTestPath,
} from "../../services/uml.service";

@Component({
  selector: "app-sequence-viewer",
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
  templateUrl: "./sequence-viewer.component.html",
  styleUrls: ["./sequence-viewer.component.scss"],
})
export class SequenceViewerComponent implements OnInit {
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

  readonly participants = computed<SequenceParticipant[]>(
    () => this.detail()?.parsedModel?.participants ?? [],
  );
  readonly messages = computed<SequenceMessage[]>(
    () => this.detail()?.parsedModel?.relationships ?? [],
  );
  readonly fragments = computed<SequenceFragment[]>(
    () => this.detail()?.parsedModel?.fragments ?? [],
  );
  readonly testPaths = computed<SequenceTestPath[]>(
    () => this.detail()?.parsedModel?.flows ?? [],
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

  pathLabel(pathType: string): string {
    const map: Record<string, string> = {
      happy: "Ścieżka główna",
      alternative: "Alternatywa",
      iterative: "Iteracja",
    };
    return map[pathType] ?? pathType;
  }
}
