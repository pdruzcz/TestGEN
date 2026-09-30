import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { FocusVisibleDirective } from "./focus-visible.directive";

@Component({
  standalone: true,
  imports: [FocusVisibleDirective],
  template: `<button appFocusVisible>Akcja</button>`,
})
class HostComponent {}

describe("FocusVisibleDirective", () => {
  let fixture: ComponentFixture<HostComponent>;
  let button: HTMLButtonElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    button = fixture.nativeElement.querySelector("button");
  });

  it("pokazuje outline 2px po fokusie z klawiatury (AC3)", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    button.dispatchEvent(new FocusEvent("focus"));
    expect(button.style.outline).toContain("2px");
    expect(button.style.outlineOffset).toBe("2px");
  });

  it("nie pokazuje outline po fokusie z myszy (AC3)", () => {
    document.dispatchEvent(new MouseEvent("mousedown"));
    button.dispatchEvent(new FocusEvent("focus"));
    expect(button.style.outline).toBe("");
  });

  it("usuwa outline po utracie fokusu (AC3)", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    button.dispatchEvent(new FocusEvent("focus"));
    button.dispatchEvent(new FocusEvent("blur"));
    expect(button.style.outline).toBe("");
  });
});
