import { TestBed, ComponentFixture } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { NotFoundComponent } from "./not-found.component";

describe("NotFoundComponent", () => {
  let component: NotFoundComponent;
  let fixture: ComponentFixture<NotFoundComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotFoundComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(NotFoundComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("should create", () => {
    expect(component).toBeTruthy();
  });

  it("should display 404 heading", () => {
    const el = fixture.nativeElement as HTMLElement;
    const heading = el.querySelector("h1");
    expect(heading?.textContent).toContain("404");
    expect(heading?.textContent).toContain("Nie znaleziono");
  });

  it("should display descriptive message", () => {
    const el = fixture.nativeElement as HTMLElement;
    const paragraph = el.querySelector("p");
    expect(paragraph?.textContent).toContain(
      "Strona, której szukasz, nie istnieje",
    );
  });

  it("should have a navigation link to home", () => {
    const el = fixture.nativeElement as HTMLElement;
    const link = el.querySelector("a");
    expect(link).toBeTruthy();
    expect(link?.getAttribute("href")).toBe("/");
    expect(link?.textContent).toContain("Wróć na stronę główną");
  });

  it("should have role=alert on the error container", () => {
    const el = fixture.nativeElement as HTMLElement;
    const container = el.querySelector('[role="alert"]');
    expect(container).toBeTruthy();
  });
});
