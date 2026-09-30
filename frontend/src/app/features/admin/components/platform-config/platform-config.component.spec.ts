import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";

import { environment } from "../../../../../environments/environment";
import { PlatformConfig } from "../../services/admin.service";
import { PlatformConfigComponent } from "./platform-config.component";

const API = environment.apiUrl;

const CONFIG: PlatformConfig = {
  limits: {
    maxFileSizeMb: 100,
    maxProjectsPerTenant: 50,
    maxUsersPerTenant: 25,
    llmCostLimitUsd: 100,
  },
  llm: {
    provider: "anthropic",
    model: "claude-sonnet-4-20250514",
    temperature: 0.2,
    maxTokens: 4096,
    timeoutSeconds: 60,
  },
  maintenance: { enabled: false, message: "" },
  featureFlags: { aiAssistant: true, selfHealing: false },
};

describe("PlatformConfigComponent", () => {
  let fixture: ComponentFixture<PlatformConfigComponent>;
  let component: PlatformConfigComponent;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [PlatformConfigComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
      ],
    });
    fixture = TestBed.createComponent(PlatformConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  function initialLoad(config: PlatformConfig = CONFIG): void {
    fixture.detectChanges();
    httpTesting.expectOne(`${API}/admin/config`).flush(config);
    fixture.detectChanges();
  }

  it("pobiera konfigurację i wypełnia formularz", () => {
    initialLoad();

    expect(component.form.value.limits?.maxFileSizeMb).toBe(100);
    expect(component.form.value.llm?.provider).toBe("anthropic");
    expect(component.form.value.maintenance?.enabled).toBe(false);
  });

  it("buduje kontrolki dla flag funkcji zwróconych przez backend", () => {
    initialLoad();

    expect(component.featureFlagKeys()).toEqual(["aiAssistant", "selfHealing"]);
    expect(component.featureFlags.value).toEqual({
      aiAssistant: true,
      selfHealing: false,
    });
  });

  it("waliduje limity jako liczby dodatnie", () => {
    initialLoad();

    component.form.controls.limits.controls.maxFileSizeMb.setValue(0);
    expect(component.form.controls.limits.controls.maxFileSizeMb.valid).toBe(false);

    component.form.controls.limits.controls.maxFileSizeMb.setValue(250);
    expect(component.form.controls.limits.controls.maxFileSizeMb.valid).toBe(true);
  });

  it("waliduje temperaturę LLM w zakresie 0–2", () => {
    initialLoad();

    component.form.controls.llm.controls.temperature.setValue(3);
    expect(component.form.controls.llm.controls.temperature.valid).toBe(false);
  });

  it("wysyła tylko zmienione sekcje", () => {
    initialLoad();

    component.form.controls.maintenance.patchValue({
      enabled: true,
      message: "Przerwa techniczna",
    });
    component.save();

    const req = httpTesting.expectOne(`${API}/admin/config`);
    expect(req.request.method).toBe("PUT");
    expect(req.request.body).toEqual({
      maintenance: { enabled: true, message: "Przerwa techniczna" },
    });
    req.flush({
      ...CONFIG,
      maintenance: { enabled: true, message: "Przerwa techniczna" },
    });
  });

  it("wysyła zmienione flagi funkcji", () => {
    initialLoad();

    component.featureFlags.controls["selfHealing"].setValue(true);
    component.save();

    const req = httpTesting.expectOne(`${API}/admin/config`);
    expect(req.request.body).toEqual({
      featureFlags: { aiAssistant: true, selfHealing: true },
    });
    req.flush(CONFIG);
  });

  it("nie wysyła żądania, gdy nic się nie zmieniło", () => {
    initialLoad();

    component.save();

    httpTesting.verify();
    expect(component.infoMessage()).toContain("Brak zmian");
  });

  it("nie wysyła żądania, gdy formularz jest niepoprawny", () => {
    initialLoad();

    component.form.controls.limits.controls.maxUsersPerTenant.setValue(0);
    component.save();

    httpTesting.verify();
  });

  it("potwierdza zapis komunikatem", () => {
    initialLoad();

    component.form.controls.maintenance.patchValue({ enabled: true, message: "x" });
    component.save();
    httpTesting.expectOne(`${API}/admin/config`).flush({
      ...CONFIG,
      maintenance: { enabled: true, message: "x" },
    });
    fixture.detectChanges();

    expect(component.infoMessage()).toContain("zapisana");
  });

  it("pokazuje komunikat błędu przy nieudanym pobraniu", () => {
    fixture.detectChanges();
    httpTesting
      .expectOne(`${API}/admin/config`)
      .flush(null, { status: 500, statusText: "Server Error" });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain("konfiguracji");
  });
});
