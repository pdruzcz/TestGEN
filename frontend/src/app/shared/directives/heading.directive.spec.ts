import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { HeadingDirective } from "./heading.directive";

@Component({
  standalone: true,
  imports: [HeadingDirective],
  template: `
    <div id="ok" appHeading="3">Sekcja</div>
    <div id="bad" appHeading="9">Nieprawidłowy poziom</div>
  `,
})
class HostComponent {}

describe("HeadingDirective", () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
  });

  it("nadaje role=heading i aria-level (AC2)", () => {
    const el = fixture.nativeElement.querySelector("#ok") as HTMLElement;
    expect(el.getAttribute("role")).toBe("heading");
    expect(el.getAttribute("aria-level")).toBe("3");
  });

  it("nieprawidłowy poziom zamienia na bezpieczny poziom 2 (AC2)", () => {
    const el = fixture.nativeElement.querySelector("#bad") as HTMLElement;
    expect(el.getAttribute("aria-level")).toBe("2");
  });
});
