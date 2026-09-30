import { ComponentFixture, TestBed } from "@angular/core/testing";
import {
  HIGH_CONTRAST_CLASS,
  HIGH_CONTRAST_STORAGE_KEY,
  REDUCED_MOTION_CLASS,
  REDUCED_MOTION_STORAGE_KEY,
} from "../../services/theme.service";
import { AccessibilityToolbarComponent } from "./accessibility-toolbar.component";

describe("AccessibilityToolbarComponent", () => {
  let fixture: ComponentFixture<AccessibilityToolbarComponent>;

  beforeEach(async () => {
    localStorage.removeItem(HIGH_CONTRAST_STORAGE_KEY);
    localStorage.removeItem(REDUCED_MOTION_STORAGE_KEY);
    document.body.classList.remove(HIGH_CONTRAST_CLASS, REDUCED_MOTION_CLASS);
    await TestBed.configureTestingModule({
      imports: [AccessibilityToolbarComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(AccessibilityToolbarComponent);
    fixture.detectChanges();
  });

  const expandPanel = (): void => {
    (
      fixture.nativeElement.querySelector(".a11y-toggle") as HTMLButtonElement
    ).click();
    fixture.detectChanges();
  };

  const panelButtons = (): HTMLButtonElement[] =>
    Array.from(fixture.nativeElement.querySelectorAll(".a11y-btn"));

  it("rozwija panel z przyciskami po kliknięciu (aria-expanded)", () => {
    const toggle = fixture.nativeElement.querySelector(
      ".a11y-toggle",
    ) as HTMLButtonElement;
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expandPanel();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(panelButtons().length).toBe(2);
  });

  it("przełącza wysoki kontrast: klasa na body + localStorage + aria-pressed (AC6)", () => {
    expandPanel();
    const [contrastBtn] = panelButtons();
    contrastBtn.click();
    fixture.detectChanges();

    expect(document.body.classList.contains(HIGH_CONTRAST_CLASS)).toBe(true);
    expect(localStorage.getItem(HIGH_CONTRAST_STORAGE_KEY)).toBe("true");
    expect(contrastBtn.getAttribute("aria-pressed")).toBe("true");
  });

  it("przełącza wyłączenie animacji: klasa na body + localStorage + aria-pressed (AC7)", () => {
    expandPanel();
    const [, motionBtn] = panelButtons();
    motionBtn.click();
    fixture.detectChanges();

    expect(document.body.classList.contains(REDUCED_MOTION_CLASS)).toBe(true);
    expect(localStorage.getItem(REDUCED_MOTION_STORAGE_KEY)).toBe("true");
    expect(motionBtn.getAttribute("aria-pressed")).toBe("true");
  });

  it("ponowne kliknięcie wyłącza tryb (AC6)", () => {
    expandPanel();
    const [contrastBtn] = panelButtons();
    contrastBtn.click();
    contrastBtn.click();
    fixture.detectChanges();

    expect(document.body.classList.contains(HIGH_CONTRAST_CLASS)).toBe(false);
    expect(localStorage.getItem(HIGH_CONTRAST_STORAGE_KEY)).toBe("false");
  });
});
