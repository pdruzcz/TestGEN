import { Component, inject, signal, computed, OnInit, DestroyRef } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import {
  GuiService,
  GUIAnalysisResponse,
  LayoutNode,
} from "../../services/gui.service";

interface FlatLayoutNode {
  type: string;
  label: string | null;
  depth: number;
}

@Component({
  selector: "app-gui-result",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./gui-result.component.html",
  styleUrls: ["./gui-result.component.scss"],
})
export class GuiResultComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly guiService = inject(GuiService);

  readonly result = signal<GUIAnalysisResponse | null>(null);
  readonly isLoading = signal(false);
  readonly loadError = signal("");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );
  readonly screenshotId = computed(
    () => this.route.snapshot.paramMap.get("screenshotId") ?? "",
  );

  readonly flatLayout = computed<FlatLayoutNode[]>(() => {
    const tree = this.result()?.layoutTree;
    if (!tree) return [];
    const out: FlatLayoutNode[] = [];
    const walk = (node: LayoutNode, depth: number): void => {
      out.push({ type: node.type, label: node.label, depth });
      for (const child of node.children) {
        walk(child, depth + 1);
      }
    };
    walk(tree, 0);
    return out;
  });

  ngOnInit(): void {
    if (this.projectId() && this.screenshotId()) {
      this.load();
    }
  }

  private load(): void {
    this.isLoading.set(true);
    this.loadError.set("");
    this.guiService
      .getResult(this.projectId(), this.screenshotId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.result.set(res);
          this.isLoading.set(false);
        },
        error: (err) => {
          this.loadError.set(
            `Błąd ładowania wyniku: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
          this.isLoading.set(false);
        },
      });
  }

  componentTypeLabel(type: string): string {
    const map: Record<string, string> = {
      button: "Przycisk",
      input: "Pole tekstowe",
      dropdown: "Lista rozwijana",
      checkbox: "Pole wyboru",
      radio: "Przycisk opcji",
      menu: "Menu",
      link: "Łącze",
      table: "Tabela",
      form: "Formularz",
      modal: "Okno modalne",
      tab: "Zakładka",
      unknown: "Nieznany",
      screen: "Ekran",
    };
    return map[type] ?? type;
  }
}
