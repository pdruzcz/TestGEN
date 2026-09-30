import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { ForbiddenComponent } from "./forbidden.component";

describe("ForbiddenComponent", () => {
  let component: ForbiddenComponent;
  let fixture: ComponentFixture<ForbiddenComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ForbiddenComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(ForbiddenComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should display 403 heading", () => {
    const el = fixture.nativeElement as HTMLElement;
    const heading = el.querySelector("h1");
    expect(heading?.textContent).toContain("403");
    expect(heading?.textContent).toContain("Brak uprawnień");
  });

  it("should display descriptive message", () => {
    const el = fixture.nativeElement as HTMLElement;
    const paragraph = el.querySelector("p");
    expect(paragraph?.textContent).toContain(
      "Nie masz uprawnień do wyświetlenia tej strony",
    );
  });

  it("should have a navigation link to profile", () => {
    const el = fixture.nativeElement as HTMLElement;
    const link = el.querySelector("a");
    expect(link).toBeTruthy();
    expect(link?.getAttribute("href")).toBe("/settings/profile");
    expect(link?.textContent).toContain("Wróć do profilu");
  });

  it("should have role=alert on the error container", () => {
    const el = fixture.nativeElement as HTMLElement;
    const container = el.querySelector('[role="alert"]');
    expect(container).toBeTruthy();
  });
});
