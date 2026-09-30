import { Component, OnInit, inject, signal } from "@angular/core";
import {
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIcon } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { RouterLink } from "@angular/router";

import { BillingService, InvoiceData } from "../billing.service";

interface InvoiceDataForm {
  companyName: FormControl<string>;
  nip: FormControl<string>;
  street: FormControl<string>;
  city: FormControl<string>;
  postalCode: FormControl<string>;
  country: FormControl<string>;
}

/**
 * Dane fakturowe tenanta (Story 7.6, AC4) — firma do faktury VAT: nazwa,
 * NIP, adres. Edycja wyłącznie przez Ownera (backend: require_role);
 * zmiana dotyczy następnych faktur (snapshot przy wystawieniu).
 */
@Component({
  selector: "app-invoice-data",
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIcon,
    RouterLink,
  ],
  templateUrl: "./invoice-data.component.html",
  styleUrl: "./invoice-data.component.scss",
  providers: [BillingService],
})
export class InvoiceDataComponent implements OnInit {
  private readonly billing = inject(BillingService);
  private readonly fb = inject(FormBuilder);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly saved = signal(false);
  readonly saving = signal(false);

  readonly form: FormGroup<InvoiceDataForm> = this.fb.nonNullable.group({
    companyName: this.fb.nonNullable.control("", [
      Validators.required,
      Validators.maxLength(255),
    ]),
    nip: this.fb.nonNullable.control("", [Validators.maxLength(20)]),
    street: this.fb.nonNullable.control("", [Validators.maxLength(255)]),
    city: this.fb.nonNullable.control("", [Validators.maxLength(100)]),
    postalCode: this.fb.nonNullable.control("", [Validators.maxLength(20)]),
    country: this.fb.nonNullable.control("Polska", [Validators.maxLength(100)]),
  });

  ngOnInit(): void {
    this.billing.getInvoiceData().subscribe({
      next: (data) => {
        this.patchForm(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.loadErrorMessage(err?.status));
        this.loading.set(false);
      },
    });
  }

  /** AC4 — zapis danych fakturowych; użyte przy następnej generacji faktury. */
  save(): void {
    this.actionError.set(null);
    this.saved.set(false);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.billing.updateInvoiceData(this.formValue()).subscribe({
      next: (data) => {
        this.patchForm(data);
        this.saved.set(true);
        this.saving.set(false);
      },
      error: (err) => {
        this.saving.set(false);
        this.actionError.set(
          err?.status === 403
            ? "Tylko administrator konta (Owner) może edytować dane fakturowe."
            : "Nie udało się zapisać danych fakturowych. Spróbuj ponownie za chwilę.",
        );
      },
    });
  }

  private patchForm(data: InvoiceData): void {
    this.form.patchValue({
      companyName: data.companyName ?? "",
      nip: data.nip ?? "",
      street: data.address?.street ?? "",
      city: data.address?.city ?? "",
      postalCode: data.address?.postalCode ?? "",
      country: data.address?.country ?? "Polska",
    });
  }

  private formValue(): InvoiceData {
    return {
      companyName: this.form.getRawValue().companyName.trim(),
      nip: this.form.getRawValue().nip.trim() || null,
      address: {
        street: this.form.getRawValue().street.trim(),
        city: this.form.getRawValue().city.trim(),
        postalCode: this.form.getRawValue().postalCode.trim(),
        country: this.form.getRawValue().country.trim() || "Polska",
      },
    };
  }

  private loadErrorMessage(status: number | undefined): string {
    if (status === 403) {
      return "Tylko administrator konta (Owner) może zarządzać danymi fakturowymi.";
    }
    return "Nie udało się pobrać danych fakturowych. Spróbuj ponownie za chwilę.";
  }
}
