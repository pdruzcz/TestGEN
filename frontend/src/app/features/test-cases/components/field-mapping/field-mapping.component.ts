import { Component, computed, inject, input, output } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import {
  FieldMapping,
  TESTGEN_FIELD_OPTIONS,
  TMS_FIELD_DEFS,
  TmsExportService,
  TmsFormat,
  defaultMapping,
} from "../../services/tms-export.service";

/**
 * Story 6.8, AC5 — panel mapowania pól TestGEN → pola TMS.
 * Konfiguracja zapisywana w localStorage (klucz `testgen:tms-mapping:{format}`).
 */
@Component({
  selector: "app-field-mapping",
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  templateUrl: "./field-mapping.component.html",
  styleUrls: ["./field-mapping.component.scss"],
})
export class FieldMappingComponent {
  private readonly service = inject(TmsExportService);

  readonly format = input.required<TmsFormat>();
  readonly mapping = input.required<FieldMapping>();
  readonly mappingChange = output<FieldMapping>();

  readonly fieldOptions = TESTGEN_FIELD_OPTIONS;

  readonly fieldDefs = computed(() => TMS_FIELD_DEFS[this.format()]);

  onFieldChange(tmsField: string, testgenField: string): void {
    const next = { ...this.mapping(), [tmsField]: testgenField };
    this.service.saveMapping(this.format(), next);
    this.mappingChange.emit(next);
  }

  resetToDefaults(): void {
    const defaults = defaultMapping(this.format());
    this.service.saveMapping(this.format(), defaults);
    this.mappingChange.emit(defaults);
  }
}
