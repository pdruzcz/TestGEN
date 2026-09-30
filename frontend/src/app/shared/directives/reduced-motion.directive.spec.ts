import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ThemeService } from "../services/theme.service";
import { ReducedMotionDirective } from "./reduced-motion.directive";

@Component({
  standalone: true,
  imports: [ReducedMotionDirective],
  template: `<div appReducedMotion class="animated"></div>`,
})
class HostComponent {}

describe("ReducedMotionDirective", () => {
  let fixture: ComponentFixture<HostComponent>;
  let theme: ThemeService;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HostComponent],
    }).compileComponents();
    theme = TestBed.inject(ThemeService);
    theme.isReducedMotionSignal.set(false);
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    element = fixture.nativeElement.querySelector(".animated");
  });

  it("wyłącza animation i transition przy aktywnej redukcji animacji (AC4)", () => {
    theme.isReducedMotionSignal.set(true);
    fixture.detectChanges();
    expect(element.style.animation).toBe("none");
    expect(element.style.transition).toBe("none");
  });

  it("przywraca animacje po wyłączeniu redukcji (AC4)", () => {
    theme.isReducedMotionSignal.set(true);
    fixture.detectChanges();
    theme.isReducedMotionSignal.set(false);
    fixture.detectChanges();
    expect(element.style.animation).toBe("");
    expect(element.style.transition).toBe("");
  });
});
