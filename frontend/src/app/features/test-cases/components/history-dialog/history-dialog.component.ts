import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { DatePipe } from "@angular/common";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatDialogModule, MAT_DIALOG_DATA } from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { TestCaseService } from "../../services/test-case.service";
import { TestCaseHistoryEntry } from "../../models/test-case.model";

export interface HistoryDialogData {
  testCaseId: string;
  title: string;
}

const FIELD_LABELS: Record<string, string> = {
  title: "Tytuł",
  description: "Opis",
  priority: "Priorytet",
  type: "Typ",
  framework: "Framework",
  test_code: "Kod testu",
  imports: "Importy",
  setup_code: "Setup",
  teardown_code: "Teardown",
  preconditions: "Warunki wstępne",
  steps: "Kroki",
  expected_result: "Oczekiwany wynik",
  test_data: "Dane testowe",
  status: "Status",
  tags: "Tagi",
  metadata: "Metadane",
};

/**
 * AC7 — historia zmian test case'a: data, autor, pole, wartość przed i po.
 * Dane z audit logu BE (GET /test-cases/:id/history).
 */
@Component({
  selector: "app-history-dialog",
  standalone: true,
  imports: [
    DatePipe,
    MatButtonModule,
    MatDialogModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./history-dialog.component.html",
  styleUrls: ["./history-dialog.component.scss"],
})
export class HistoryDialogComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);
  private readonly service = inject(TestCaseService);
  readonly data = inject<HistoryDialogData>(MAT_DIALOG_DATA);

  readonly entries = signal<TestCaseHistoryEntry[]>([]);
  readonly isLoading = signal(true);
  readonly hasError = signal(false);

  ngOnInit(): void {
    this.service
      .getHistory(this.data.testCaseId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.entries.set(resp.entries);
          this.isLoading.set(false);
        },
        error: () => {
          this.hasError.set(true);
          this.isLoading.set(false);
        },
      });
  }

  fieldLabel(field: string): string {
    return FIELD_LABELS[field] ?? field;
  }

  truncate(value: string | null): string {
    if (!value) return "—";
    return value.length > 120 ? `${value.slice(0, 120)}…` : value;
  }
}
