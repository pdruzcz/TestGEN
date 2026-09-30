import { HttpClient, HttpResponse } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, finalize, map } from "rxjs";
import { environment } from "../../../../environments/environment";

/**
 * Story 6.8 — eksport test case'ów do TMS (TestRail CSV / Jira Xray XML /
 * Ogólny JSON) z konfigurowalnym mapowaniem pól zapisywanym w localStorage.
 */

export type TmsFormat = "testrail" | "xray" | "json";

export const TMS_FORMAT_LABELS: Record<TmsFormat, string> = {
  testrail: "TestRail (CSV)",
  xray: "Jira Xray (XML)",
  json: "Ogólny (JSON)",
};

export const TMS_FORMAT_EXTENSIONS: Record<TmsFormat, string> = {
  testrail: "csv",
  xray: "xml",
  json: "json",
};

/** Mapowanie: pole TMS (klucz) → pole TestGEN (wartość, snake_case). */
export type FieldMapping = Record<string, string>;

export interface TestGenFieldOption {
  value: string;
  label: string;
}

/** Pola TestGEN dostępne w mapowaniu (wartości snake_case — jak w API). */
export const TESTGEN_FIELD_OPTIONS: TestGenFieldOption[] = [
  { value: "title", label: "Tytuł" },
  { value: "description", label: "Opis" },
  { value: "preconditions", label: "Warunki wstępne" },
  { value: "steps", label: "Kroki" },
  { value: "expected_result", label: "Oczekiwany rezultat" },
  { value: "priority", label: "Priorytet" },
  { value: "type", label: "Typ" },
  { value: "framework", label: "Framework" },
  { value: "status", label: "Status" },
  { value: "module", label: "Moduł" },
  { value: "source_class", label: "Klasa źródłowa" },
  { value: "source_function", label: "Funkcja źródłowa" },
  { value: "source_endpoint", label: "Endpoint źródłowy" },
  { value: "tags", label: "Tagi" },
];

export interface TmsFieldDef {
  /** Klucz pola TMS wysyłany do backendu (snake_case). */
  key: string;
  /** Etykieta pola w systemie TMS. */
  label: string;
  /** Domyślne pole TestGEN. */
  defaultField: string;
}

/** Definicje pól mapowania per format TMS (AC5). */
export const TMS_FIELD_DEFS: Record<TmsFormat, TmsFieldDef[]> = {
  testrail: [
    { key: "title", label: "Title", defaultField: "title" },
    { key: "section", label: "Section", defaultField: "module" },
    { key: "priority", label: "Priority", defaultField: "priority" },
    { key: "type", label: "Type", defaultField: "type" },
    { key: "preconditions", label: "Preconds", defaultField: "preconditions" },
    { key: "steps", label: "Steps", defaultField: "steps" },
    {
      key: "expected_result",
      label: "Expected Result",
      defaultField: "expected_result",
    },
    { key: "references", label: "References", defaultField: "tags" },
  ],
  xray: [
    { key: "summary", label: "Summary", defaultField: "title" },
    { key: "description", label: "Description", defaultField: "description" },
    { key: "priority", label: "Priority", defaultField: "priority" },
    { key: "preconditions", label: "Preconditions", defaultField: "preconditions" },
    { key: "steps", label: "Steps", defaultField: "steps" },
    {
      key: "expected_result",
      label: "Expected Result",
      defaultField: "expected_result",
    },
    { key: "labels", label: "Labels", defaultField: "tags" },
  ],
  json: [
    { key: "title", label: "title", defaultField: "title" },
    { key: "description", label: "description", defaultField: "description" },
    { key: "steps", label: "steps", defaultField: "steps" },
    {
      key: "expected_result",
      label: "expected_result",
      defaultField: "expected_result",
    },
    { key: "module", label: "module", defaultField: "module" },
  ],
};

const STORAGE_PREFIX = "testgen:tms-mapping:";

export function defaultMapping(format: TmsFormat): FieldMapping {
  const mapping: FieldMapping = {};
  for (const def of TMS_FIELD_DEFS[format]) {
    mapping[def.key] = def.defaultField;
  }
  return mapping;
}

@Injectable({ providedIn: "root" })
export class TmsExportService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/test-cases/export`;

  readonly exportFormatSignal = signal<TmsFormat>("testrail");
  readonly fieldMappingSignal = signal<FieldMapping>(defaultMapping("testrail"));
  readonly isExportingSignal = signal(false);

  /** AC5 — odczyt mapowania z localStorage (scalone z domyślnym). */
  loadMapping(format: TmsFormat): FieldMapping {
    const defaults = defaultMapping(format);
    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${format}`);
      if (!raw) return defaults;
      const stored = JSON.parse(raw) as FieldMapping;
      return { ...defaults, ...stored };
    } catch {
      return defaults;
    }
  }

  /** AC5 — zapis mapowania do localStorage. */
  saveMapping(format: TmsFormat, mapping: FieldMapping): void {
    this.fieldMappingSignal.set(mapping);
    try {
      localStorage.setItem(
        `${STORAGE_PREFIX}${format}`,
        JSON.stringify(mapping),
      );
    } catch {
      // localStorage niedostępny (np. tryb prywatny) — mapowanie tylko w pamięci
    }
  }

  /**
   * AC1-AC7 — eksport wskazanych test case'ów (puste ids = wszystkie)
   * i automatyczne pobranie pliku. Emituje nazwę pobranego pliku.
   */
  exportToTms(
    projectId: string,
    ids: string[],
    format: TmsFormat,
    fieldMapping: FieldMapping,
  ): Observable<string> {
    this.exportFormatSignal.set(format);
    this.isExportingSignal.set(true);
    return this.http
      .post(
        this.apiUrl,
        { format, ids, projectId, fieldMapping },
        { responseType: "blob", observe: "response" },
      )
      .pipe(
        map((response: HttpResponse<Blob>) => {
          const filename =
            this.filenameFromDisposition(
              response.headers.get("Content-Disposition"),
            ) ??
            `testgen_export_${new Date().toISOString().slice(0, 10)}_${format}.${TMS_FORMAT_EXTENSIONS[format]}`;
          this.saveBlob(response.body ?? new Blob(), filename);
          return filename;
        }),
        finalize(() => this.isExportingSignal.set(false)),
      );
  }

  private filenameFromDisposition(header: string | null): string | null {
    if (!header) return null;
    const match = /filename="?([^";]+)"?/.exec(header);
    return match ? match[1] : null;
  }

  protected saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
