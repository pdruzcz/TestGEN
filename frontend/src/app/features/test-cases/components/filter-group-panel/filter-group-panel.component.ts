import { Component, input, output } from "@angular/core";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import {
  TestCaseStatus,
  TestPriority,
  TestType,
} from "../../models/test-case.model";
import {
  PRIORITY_OPTIONS,
  STATUS_OPTIONS,
  TYPE_OPTIONS,
} from "../../models/test-case-labels";

export type TestCaseGroupBy = "none" | "module" | "priority" | "type";

export interface TestCaseFilters {
  priorities: TestPriority[];
  types: TestType[];
  statuses: TestCaseStatus[];
  modules: string[];
}

export const EMPTY_TC_FILTERS: TestCaseFilters = {
  priorities: [],
  types: [],
  statuses: [],
  modules: [],
};

/**
 * AC2 — multi-select filtry: priorytet, typ, moduł, status.
 * AC3 — wybór grupowania: moduł / priorytet / typ / brak.
 */
@Component({
  selector: "app-filter-group-panel",
  standalone: true,
  imports: [
    MatFormFieldModule,
    MatSelectModule,
    MatIconModule,
    MatButtonModule,
  ],
  templateUrl: "./filter-group-panel.component.html",
  styleUrls: ["./filter-group-panel.component.scss"],
})
export class FilterGroupPanelComponent {
  readonly availableModules = input<string[]>([]);
  readonly filters = input<TestCaseFilters>(EMPTY_TC_FILTERS);
  readonly groupBy = input<TestCaseGroupBy>("none");

  readonly filtersChange = output<TestCaseFilters>();
  readonly groupByChange = output<TestCaseGroupBy>();

  readonly priorityOptions = PRIORITY_OPTIONS;
  readonly typeOptions = TYPE_OPTIONS;
  readonly statusOptions = STATUS_OPTIONS;

  readonly groupByOptions: [TestCaseGroupBy, string][] = [
    ["none", "Brak grupowania"],
    ["module", "Moduł"],
    ["priority", "Priorytet"],
    ["type", "Typ"],
  ];

  onPrioritiesChange(priorities: TestPriority[]): void {
    this.filtersChange.emit({ ...this.filters(), priorities });
  }

  onTypesChange(types: TestType[]): void {
    this.filtersChange.emit({ ...this.filters(), types });
  }

  onStatusesChange(statuses: TestCaseStatus[]): void {
    this.filtersChange.emit({ ...this.filters(), statuses });
  }

  onModulesChange(modules: string[]): void {
    this.filtersChange.emit({ ...this.filters(), modules });
  }

  clearFilters(): void {
    this.filtersChange.emit({ ...EMPTY_TC_FILTERS });
  }

  hasActiveFilters(): boolean {
    const f = this.filters();
    return (
      f.priorities.length > 0 ||
      f.types.length > 0 ||
      f.statuses.length > 0 ||
      f.modules.length > 0
    );
  }
}
