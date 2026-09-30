import { Component, DestroyRef, OnInit, inject, input, output } from "@angular/core";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { debounceTime, distinctUntilChanged } from "rxjs/operators";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatIconModule } from "@angular/material/icon";
import { MatAutocompleteModule } from "@angular/material/autocomplete";
import {
  EMPTY_FILTERS,
  ResultSeverity,
  ResultStatus,
  ResultsFilters,
} from "../../services/results.service";

export const SEVERITY_LABELS: Record<ResultSeverity, string> = {
  critical: "Krytyczny",
  high: "Wysoki",
  medium: "Średni",
  low: "Niski",
};

export const STATUS_LABELS: Record<ResultStatus, string> = {
  new: "Nowy",
  accepted: "Zaakceptowany",
  rejected: "Odrzucony",
};

/**
 * AC2 — panel filtrów: severity (multi toggle), typ (select), plik
 * (autocomplete), moduł (select), status (toggle). AC4 — wyszukiwanie
 * z debounce 300 ms (FormControl + valueChanges).
 */
@Component({
  selector: "app-filter-panel",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatButtonToggleModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatAutocompleteModule,
  ],
  templateUrl: "./filter-panel.component.html",
  styleUrls: ["./filter-panel.component.scss"],
})
export class FilterPanelComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  readonly availableTypes = input<string[]>([]);
  readonly availableModules = input<string[]>([]);
  readonly availableFiles = input<string[]>([]);

  readonly filtersChange = output<ResultsFilters>();
  readonly searchChange = output<string>();

  readonly searchControl = new FormControl("", { nonNullable: true });
  readonly fileControl = new FormControl("", { nonNullable: true });

  readonly severityOptions = Object.entries(SEVERITY_LABELS) as [
    ResultSeverity,
    string,
  ][];
  readonly statusOptions = Object.entries(STATUS_LABELS) as [
    ResultStatus,
    string,
  ][];

  private filters: ResultsFilters = { ...EMPTY_FILTERS };

  ngOnInit(): void {
    this.searchControl.valueChanges
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((value) => this.searchChange.emit(value));

    this.fileControl.valueChanges
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((value) => {
        this.filters = { ...this.filters, file: value || null };
        this.filtersChange.emit(this.filters);
      });
  }

  onSeveritiesChange(severities: ResultSeverity[]): void {
    this.filters = { ...this.filters, severities };
    this.filtersChange.emit(this.filters);
  }

  onTypeChange(type: string | null): void {
    this.filters = { ...this.filters, type: type || null };
    this.filtersChange.emit(this.filters);
  }

  onModuleChange(module: string | null): void {
    this.filters = { ...this.filters, module: module || null };
    this.filtersChange.emit(this.filters);
  }

  onStatusChange(status: ResultStatus | null): void {
    this.filters = { ...this.filters, status: status || null };
    this.filtersChange.emit(this.filters);
  }

  clearFilters(): void {
    this.filters = { ...EMPTY_FILTERS };
    this.searchControl.setValue("");
    this.fileControl.setValue("");
    this.filtersChange.emit(this.filters);
  }
}
