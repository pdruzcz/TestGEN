import { Component, signal } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { LiveRegionComponent } from "./live-region.component";

@Component({
  standalone: true,
  imports: [LiveRegionComponent],
  template: `<app-live-region [message]="msg()" [priority]="prio()" />`,
})
class HostComponent {
  readonly msg = signal("");
  readonly prio = signal<"polite" | "assertive">("polite");
}

describe("LiveRegionComponent", () => {
  let fixture: ComponentFixture<HostComponent>;

  const region = (): HTMLElement =>
    fixture.nativeElement.querySelector("[aria-live]");

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
  });

  it("renderuje ukryty live region polite/status z aria-atomic (AC3)", () => {
    expect(region().getAttribute("aria-live")).toBe("polite");
    expect(region().getAttribute("role")).toBe("status");
    expect(region().getAttribute("aria-atomic")).toBe("true");
    expect(region().classList.contains("visually-hidden")).toBe(true);
  });

  it("ogłasza zmieniony komunikat (AC3)", () => {
    fixture.componentInstance.msg.set("Analiza zakończona");
    fixture.detectChanges();
    expect(region().textContent?.trim()).toBe("Analiza zakończona");
  });

  it("priorytet assertive ustawia role=alert (AC3)", () => {
    fixture.componentInstance.prio.set("assertive");
    fixture.detectChanges();
    expect(region().getAttribute("aria-live")).toBe("assertive");
    expect(region().getAttribute("role")).toBe("alert");
  });
});
