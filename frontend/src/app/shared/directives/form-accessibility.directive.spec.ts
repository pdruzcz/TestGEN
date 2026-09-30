import { Component, signal } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { FormAccessibilityDirective } from "./form-accessibility.directive";

@Component({
  standalone: true,
  imports: [FormAccessibilityDirective],
  template: `
    <form appFormAccessibility>
      <div class="form-field">
        <label>
          Nazwa projektu
          <input type="text" />
        </label>
        @if (showError()) {
          <span class="error-message">Pole jest wymagane</span>
        }
      </div>
    </form>
  `,
})
class HostComponent {
  // Sygnał, nie zwykłe pole — aplikacja jest zoneless, więc mutacja pola
  // nie oznacza widoku jako brudnego i `detectChanges()` kończy się NG0100.
  readonly showError = signal(false);
}

describe("FormAccessibilityDirective", () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
  });

  const input = (): HTMLInputElement =>
    fixture.nativeElement.querySelector("input");
  const label = (): HTMLLabelElement =>
    fixture.nativeElement.querySelector("label");

  it("wiąże programowo label z polem przez for/id (AC5)", () => {
    expect(input().id).toBeTruthy();
    expect(label().htmlFor).toBe(input().id);
  });

  it("dowiązuje błąd walidacji przez aria-describedby i aria-live (AC5)", () => {
    fixture.componentInstance.showError.set(true);
    fixture.detectChanges();
    // MutationObserver jest asynchroniczny — wymuszamy synchronizację
    // przez ponowne wywołanie apply() poprzez zmianę DOM + microtask.
    return Promise.resolve().then(() => {
      const error = fixture.nativeElement.querySelector(
        ".error-message",
      ) as HTMLElement;
      expect(error.id).toBeTruthy();
      expect(error.getAttribute("aria-live")).toBe("polite");
      expect(input().getAttribute("aria-describedby")).toBe(error.id);
      expect(input().getAttribute("aria-invalid")).toBe("true");
    });
  });

  it("usuwa aria-invalid po zniknięciu błędu (AC5)", () => {
    fixture.componentInstance.showError.set(true);
    fixture.detectChanges();
    return Promise.resolve()
      .then(() => {
        fixture.componentInstance.showError.set(false);
        fixture.detectChanges();
        return Promise.resolve();
      })
      .then(() => {
        expect(input().getAttribute("aria-invalid")).toBeNull();
        expect(input().getAttribute("aria-describedby")).toBeNull();
      });
  });
});
