import { Component, DestroyRef, OnInit, computed, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import { UmlService, UserFlow } from "../../services/uml.service";

@Component({
  selector: "app-flows-viewer",
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
  templateUrl: "./flows-viewer.component.html",
  styleUrls: ["./flows-viewer.component.scss"],
})
export class FlowsViewerComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly umlService = inject(UmlService);

  readonly isLoading = signal(true);
  readonly loadError = signal("");
  readonly flows = signal<UserFlow[]>([]);
  readonly total = signal(0);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  ngOnInit(): void {
    this.umlService
      .listFlows(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.flows.set(response.flows);
          this.total.set(response.total);
          this.isLoading.set(false);
        },
        error: () => {
          this.loadError.set("Błąd ładowania user flows");
          this.isLoading.set(false);
        },
      });
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      draft: "Szkic",
      validated: "Zwalidowany",
      tests_generated: "Testy wygenerowane",
    };
    return map[status] ?? status;
  }

  sourceLabel(source: string): string {
    const map: Record<string, string> = {
      uml: "UML",
      gui: "GUI",
      uml_and_gui: "UML + GUI",
    };
    return map[source] ?? source;
  }
}
