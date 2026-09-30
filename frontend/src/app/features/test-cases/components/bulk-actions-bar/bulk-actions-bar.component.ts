import { Component, input, output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatMenuModule } from "@angular/material/menu";
import {
  TestCaseStatus,
  TestPriority,
} from "../../models/test-case.model";
import {
  PRIORITY_OPTIONS,
  STATUS_OPTIONS,
} from "../../models/test-case-labels";

/**
 * AC5 — pasek akcji zbiorczych: "Zaznaczono: N", zmiana statusu,
 * zmiana priorytetu, usunięcie, eksport zaznaczonych.
 */
@Component({
  selector: "app-bulk-actions-bar",
  standalone: true,
  imports: [MatButtonModule, MatIconModule, MatMenuModule],
  templateUrl: "./bulk-actions-bar.component.html",
  styleUrls: ["./bulk-actions-bar.component.scss"],
})
export class BulkActionsBarComponent {
  readonly selectedCount = input.required<number>();

  readonly statusChange = output<TestCaseStatus>();
  readonly priorityChange = output<TestPriority>();
  readonly deleteSelected = output<void>();
  readonly exportSelected = output<void>();
  readonly clearSelection = output<void>();

  readonly statusOptions = STATUS_OPTIONS;
  readonly priorityOptions = PRIORITY_OPTIONS;
}
