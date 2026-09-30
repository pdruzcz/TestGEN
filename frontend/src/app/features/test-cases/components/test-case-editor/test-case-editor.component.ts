import { Component, OnInit, inject, input, output } from "@angular/core";
import {
  FormArray,
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from "@angular/cdk/drag-drop";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import {
  TestCase,
  TestCaseStatus,
  TestCaseUpdatePayload,
  TestPriority,
} from "../../models/test-case.model";
import {
  PRIORITY_OPTIONS,
  STATUS_OPTIONS,
} from "../../models/test-case-labels";

/** Parsuje kroki z formatu BE (JSONB dict {items: []} lub string). */
export function stepsToItems(steps: TestCase["steps"]): string[] {
  if (!steps) return [];
  if (typeof steps === "string") {
    return steps
      .split("\n")
      .map((s) => s.replace(/^\d+[.)]\s*/, "").trim())
      .filter((s) => s.length > 0);
  }
  if (Array.isArray(steps.items)) {
    return steps.items.map((s) => String(s));
  }
  return [];
}

/**
 * AC4 — edytor inline: tytuł, opis, kroki, oczekiwany wynik, priorytet,
 * status. AC6 — zmiana kolejności kroków przez drag-drop (CDK) z
 * automatyczną renumeracją. AC8 — Escape zamyka edytor (anuluje).
 */
@Component({
  selector: "app-test-case-editor",
  standalone: true,
  imports: [
    ReactiveFormsModule,
    DragDropModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
  ],
  templateUrl: "./test-case-editor.component.html",
  styleUrls: ["./test-case-editor.component.scss"],
})
export class TestCaseEditorComponent implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);

  readonly testCase = input.required<TestCase>();

  readonly save = output<TestCaseUpdatePayload>();
  readonly cancelEdit = output<void>();

  readonly priorityOptions = PRIORITY_OPTIONS;
  readonly statusOptions = STATUS_OPTIONS;

  form!: FormGroup<{
    title: FormControl<string>;
    description: FormControl<string>;
    expectedResult: FormControl<string>;
    priority: FormControl<TestPriority>;
    status: FormControl<TestCaseStatus>;
    steps: FormArray<FormControl<string>>;
  }>;

  get stepsArray(): FormArray<FormControl<string>> {
    return this.form.controls.steps;
  }

  ngOnInit(): void {
    const tc = this.testCase();
    this.form = this.fb.group({
      title: this.fb.control(tc.title, [
        Validators.required,
        Validators.maxLength(500),
      ]),
      description: this.fb.control(tc.description ?? ""),
      expectedResult: this.fb.control(tc.expectedResult ?? ""),
      priority: this.fb.control<TestPriority>(tc.priority),
      status: this.fb.control<TestCaseStatus>(tc.status),
      steps: this.fb.array(
        stepsToItems(tc.steps).map((s) => this.fb.control(s)),
      ),
    });
  }

  addStep(): void {
    this.stepsArray.push(this.fb.control(""));
  }

  removeStep(index: number): void {
    this.stepsArray.removeAt(index);
  }

  onStepDrop(event: CdkDragDrop<FormControl<string>[]>): void {
    moveItemInArray(
      this.stepsArray.controls,
      event.previousIndex,
      event.currentIndex,
    );
    this.stepsArray.updateValueAndValidity();
  }

  onEscape(event: Event): void {
    event.stopPropagation();
    this.cancelEdit.emit();
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    const steps = value.steps.map((s) => s.trim()).filter((s) => s.length > 0);
    this.save.emit({
      title: value.title.trim(),
      description: value.description.trim() || null,
      expectedResult: value.expectedResult.trim() || null,
      priority: value.priority,
      status: value.status,
      steps: { items: steps },
    });
  }
}
