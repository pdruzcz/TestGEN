import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { KeyboardNavDirective } from "./keyboard-nav.directive";

@Component({
  standalone: true,
  imports: [KeyboardNavDirective],
  template: `
    <div
      appKeyboardNav
      trapFocus
      arrowNavigation
      (escapePressed)="escaped = true"
    >
      <button id="first">Pierwszy</button>
      <button id="middle">Środkowy</button>
      <button id="last">Ostatni</button>
      <ul>
        <li role="option" tabindex="0" id="opt-1">Opcja 1</li>
        <li role="option" tabindex="0" id="opt-2">Opcja 2</li>
      </ul>
    </div>
  `,
})
class HostComponent {
  escaped = false;
}

describe("KeyboardNavDirective", () => {
  let fixture: ComponentFixture<HostComponent>;
  let container: HTMLElement;

  const key = (name: string, options: KeyboardEventInit = {}): void => {
    container.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: name,
        bubbles: true,
        cancelable: true,
        ...options,
      }),
    );
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    container = fixture.nativeElement.querySelector("[appKeyboardNav]");
  });

  it("emituje escapePressed po naciśnięciu Escape (AC2)", () => {
    key("Escape");
    expect(fixture.componentInstance.escaped).toBe(true);
  });

  it("zawija Tab z ostatniego elementu do pierwszego (pułapka fokusu, AC2)", () => {
    const last = fixture.nativeElement.querySelector(
      "#opt-2",
    ) as HTMLElement;
    last.focus();
    key("Tab");
    expect(document.activeElement?.id).toBe("first");
  });

  it("zawija Shift+Tab z pierwszego elementu do ostatniego (AC2)", () => {
    const first = fixture.nativeElement.querySelector(
      "#first",
    ) as HTMLElement;
    first.focus();
    key("Tab", { shiftKey: true });
    expect(document.activeElement?.id).toBe("opt-2");
  });

  it("przenosi fokus strzałką w dół na kolejny element listy (AC2)", () => {
    const opt1 = fixture.nativeElement.querySelector("#opt-1") as HTMLElement;
    opt1.focus();
    key("ArrowDown");
    expect(document.activeElement?.id).toBe("opt-2");
  });

  it("zawija strzałkę w górę z pierwszego elementu listy na ostatni (AC2)", () => {
    const opt1 = fixture.nativeElement.querySelector("#opt-1") as HTMLElement;
    opt1.focus();
    key("ArrowUp");
    expect(document.activeElement?.id).toBe("opt-2");
  });
});
