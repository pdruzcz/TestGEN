import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { provideNoopAnimations } from "@angular/platform-browser/animations";

import { AdminUser } from "../../services/admin.service";
import {
  UserDialogComponent,
  UserDialogData,
  UserDialogResult,
} from "./user-dialog.component";

const USER: AdminUser = {
  id: "u1",
  tenantId: "t1",
  email: "jan@example.com",
  name: "Jan Kowalski",
  role: "user",
  isActive: true,
  isBlocked: false,
  deletedAt: null,
  createdAt: "2026-01-10T08:00:00Z",
  lastLoginAt: "2026-07-20T09:30:00Z",
};

function setup(data: UserDialogData): {
  fixture: ComponentFixture<UserDialogComponent>;
  component: UserDialogComponent;
  close: ReturnType<typeof vi.fn>;
} {
  const close = vi.fn();
  TestBed.configureTestingModule({
    imports: [UserDialogComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideNoopAnimations(),
      { provide: MAT_DIALOG_DATA, useValue: data },
      { provide: MatDialogRef, useValue: { close } },
    ],
  });
  const fixture = TestBed.createComponent(UserDialogComponent);
  fixture.detectChanges();
  return { fixture, component: fixture.componentInstance, close };
}

describe("UserDialogComponent", () => {
  afterEach(() => TestBed.resetTestingModule());

  describe("tryb dodawania", () => {
    it("startuje z pustym formularzem i domyślną rolą", () => {
      const { component } = setup({ mode: "create" });

      expect(component.form.value.email).toBe("");
      expect(component.form.value.role).toBe("user");
    });

    it("wymaga poprawnego adresu email", () => {
      const { component } = setup({ mode: "create" });

      component.form.patchValue({ email: "nie-email" });
      expect(component.form.controls.email.valid).toBe(false);

      component.form.patchValue({ email: "nowy@example.com" });
      expect(component.form.controls.email.valid).toBe(true);
    });

    it("blokuje zapis dopóki formularz jest niepoprawny", () => {
      const { component, close } = setup({ mode: "create" });

      component.submit();
      expect(close).not.toHaveBeenCalled();
    });

    it("zwraca akcję zaproszenia po poprawnym zapisie", () => {
      const { component, close } = setup({ mode: "create" });

      component.form.patchValue({ email: "nowy@example.com", role: "owner" });
      component.submit();

      const result: UserDialogResult = close.mock.calls[0][0];
      expect(result).toEqual({
        action: "invite",
        email: "nowy@example.com",
        role: "owner",
      });
    });

    it("nie pokazuje akcji blokady ani usuwania", () => {
      const { component } = setup({ mode: "create" });

      expect(component.isEdit).toBe(false);
    });
  });

  describe("tryb edycji", () => {
    it("wypełnia formularz danymi użytkownika", () => {
      const { component } = setup({ mode: "edit", user: USER });

      // Pole email jest wyłączone, więc czytamy je przez getRawValue().
      expect(component.form.getRawValue().email).toBe("jan@example.com");
      expect(component.form.value.role).toBe("user");
      expect(component.isEdit).toBe(true);
    });

    it("blokuje edycję adresu email", () => {
      const { component } = setup({ mode: "edit", user: USER });

      expect(component.form.controls.email.disabled).toBe(true);
    });

    it("zwraca zmianę roli", () => {
      const { component, close } = setup({ mode: "edit", user: USER });

      component.form.patchValue({ role: "admin" });
      component.submit();

      expect(close).toHaveBeenCalledWith({
        action: "update-role",
        userId: "u1",
        role: "admin",
      });
    });

    it("zamyka bez akcji, gdy rola się nie zmieniła", () => {
      const { component, close } = setup({ mode: "edit", user: USER });

      component.submit();

      expect(close).toHaveBeenCalledWith(undefined);
    });

    it("zwraca akcję blokady dla aktywnego użytkownika", () => {
      const { component, close } = setup({ mode: "edit", user: USER });

      component.toggleBlock();

      expect(close).toHaveBeenCalledWith({ action: "block", userId: "u1" });
    });

    it("zwraca akcję odblokowania dla zablokowanego użytkownika", () => {
      const { component, close } = setup({
        mode: "edit",
        user: { ...USER, isBlocked: true },
      });

      component.toggleBlock();

      expect(close).toHaveBeenCalledWith({ action: "unblock", userId: "u1" });
    });

    it("zwraca akcję usunięcia po potwierdzeniu", () => {
      const { component, close } = setup({ mode: "edit", user: USER });

      expect(component.confirmingDelete()).toBe(false);
      component.requestDelete();
      expect(component.confirmingDelete()).toBe(true);
      expect(close).not.toHaveBeenCalled();

      component.requestDelete();
      expect(close).toHaveBeenCalledWith({ action: "delete", userId: "u1" });
    });
  });

  it("anulowanie zamyka dialog bez wyniku", () => {
    const { component, close } = setup({ mode: "create" });

    component.cancel();

    expect(close).toHaveBeenCalledWith(undefined);
  });
});
