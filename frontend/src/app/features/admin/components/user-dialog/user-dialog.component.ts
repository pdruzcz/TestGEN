import { Component, inject, signal } from "@angular/core";
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";

import { AdminUser } from "../../services/admin.service";

export interface UserDialogData {
  mode: "create" | "edit";
  user?: AdminUser;
}

export type UserDialogResult =
  | { action: "invite"; email: string; role: string }
  | { action: "update-role"; userId: string; role: string }
  | { action: "block"; userId: string }
  | { action: "unblock"; userId: string }
  | { action: "delete"; userId: string };

export const USER_ROLES: readonly { value: string; label: string }[] = [
  { value: "user", label: "Użytkownik" },
  { value: "owner", label: "Właściciel" },
  { value: "admin", label: "Administrator" },
];

/**
 * Dialog dodawania i edycji użytkownika (Story 6.15, AC2, AC3).
 *
 * Dialog nie wykonuje żądań HTTP — zwraca opis akcji, a wywołanie API
 * i odświeżenie tabeli należą do komponentu listy.
 */
@Component({
  selector: "app-user-dialog",
  standalone: true,
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    ReactiveFormsModule,
  ],
  templateUrl: "./user-dialog.component.html",
})
export class UserDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly dialogRef =
    inject<MatDialogRef<UserDialogComponent, UserDialogResult | undefined>>(
      MatDialogRef,
    );
  readonly data = inject<UserDialogData>(MAT_DIALOG_DATA);

  readonly roles = USER_ROLES;
  readonly isEdit = this.data.mode === "edit";
  readonly confirmingDelete = signal(false);

  readonly form = this.fb.nonNullable.group({
    email: [
      { value: this.data.user?.email ?? "", disabled: this.isEdit },
      [Validators.required, Validators.email],
    ],
    name: [{ value: this.data.user?.name ?? "", disabled: this.isEdit }],
    role: [this.data.user?.role ?? "user", Validators.required],
  });

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const role = this.form.getRawValue().role;

    if (!this.isEdit) {
      this.dialogRef.close({
        action: "invite",
        email: this.form.getRawValue().email.trim(),
        role,
      });
      return;
    }

    const user = this.data.user;
    if (!user || user.role === role) {
      // Brak zmiany — nie zaśmiecamy logu audytu pustą aktualizacją.
      this.dialogRef.close(undefined);
      return;
    }
    this.dialogRef.close({ action: "update-role", userId: user.id, role });
  }

  toggleBlock(): void {
    const user = this.data.user;
    if (!user) return;
    this.dialogRef.close({
      action: user.isBlocked ? "unblock" : "block",
      userId: user.id,
    });
  }

  /** Pierwsze kliknięcie odsłania ostrzeżenie, drugie potwierdza usunięcie. */
  requestDelete(): void {
    const user = this.data.user;
    if (!user) return;
    if (!this.confirmingDelete()) {
      this.confirmingDelete.set(true);
      return;
    }
    this.dialogRef.close({ action: "delete", userId: user.id });
  }

  cancel(): void {
    this.dialogRef.close(undefined);
  }
}
