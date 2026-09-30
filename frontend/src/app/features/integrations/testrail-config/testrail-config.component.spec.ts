import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { TestrailConfigComponent } from './testrail-config.component';
import { TestRailConfig } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const PROJECT_ID = 'p1';
const CONFIG_URL = `${environment.apiUrl}/integrations/testrail/config`;
const TEST_URL = `${environment.apiUrl}/integrations/testrail/test`;
const TESTRAIL_URL = 'https://firma.testrail.io';
const API_KEY = 'klucz-api-testrail';

function makeConfig(overrides: Partial<TestRailConfig> = {}): TestRailConfig {
  return {
    id: 'c1',
    projectId: PROJECT_ID,
    baseUrl: TESTRAIL_URL,
    email: 'qa@firma.pl',
    testrailProjectId: 12,
    suiteId: null,
    priorityMap: { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 },
    typeMap: { FUNCTIONAL: 7, SECURITY: 12 },
    fieldMapping: {},
    isActive: true,
    createdAt: '2026-09-01T10:00:00Z',
    ...overrides,
  };
}

describe('TestrailConfigComponent', () => {
  let component: TestrailConfigComponent;
  let fixture: ComponentFixture<TestrailConfigComponent>;
  let httpTesting: HttpTestingController;

  async function setup(config: TestRailConfig | null = makeConfig()): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [TestrailConfigComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ projectId: PROJECT_ID }) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestrailConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const req = httpTesting.expectOne((r) => r.url === CONFIG_URL && r.method === 'GET');
    expect(req.request.params.get('project_id')).toBe(PROJECT_ID);
    if (config) {
      req.flush(config);
    } else {
      req.flush({ detail: 'brak' }, { status: 404, statusText: 'Not Found' });
    }
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje istniejącą konfigurację', async () => {
    await setup();

    expect(component.isConfigured()).toBe(true);
    expect(component.baseUrl()).toBe(TESTRAIL_URL);
    expect(component.testrailProjectId()).toBe(12);
    expect(fixture.nativeElement.textContent).toContain('Integracja z TestRail');
  });

  it('brak konfiguracji to normalny stan, nie błąd', async () => {
    await setup(null);

    expect(component.isConfigured()).toBe(false);
    expect(component.errorMessage()).toBeNull();
  });

  it('inny błąd niż 404 pokazuje komunikat', async () => {
    await TestBed.configureTestingModule({
      imports: [TestrailConfigComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ projectId: PROJECT_ID }) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestrailConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    httpTesting
      .expectOne((r) => r.url === CONFIG_URL && r.method === 'GET')
      .flush({ detail: 'awaria' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(component.errorMessage()).toContain('Nie udało się wczytać');
  });

  it('pokazuje mapowanie priorytetów i typów z backendu', async () => {
    await setup();

    expect(component.priorityValue('CRITICAL')).toBe(4);
    expect(component.typeValue('SECURITY')).toBe(12);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Krytyczny');
    expect(text).toContain('Bezpieczeństwa');
  });

  it('wyjaśnia wymóg pola testgen_id po stronie TestRaila', async () => {
    await setup();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('testgen_id');
    expect(text).toContain('Customizations');
  });

  describe('walidacja formularza', () => {
    it('wymaga https, e-maila i identyfikatora projektu', async () => {
      await setup(null);

      expect(component.isFormValid()).toBe(false);

      component.baseUrl.set('http://firma.testrail.io');
      component.email.set('qa@firma.pl');
      component.apiKey.set(API_KEY);
      component.setNumber('project', 12);
      expect(component.isFormValid()).toBe(false); // http odpada

      component.baseUrl.set(TESTRAIL_URL);
      expect(component.isFormValid()).toBe(true);

      component.email.set('bez-malpy');
      expect(component.isFormValid()).toBe(false);
    });

    it('przy istniejącej konfiguracji klucz API nie jest wymagany', async () => {
      await setup();

      expect(component.apiKey()).toBe('');
      expect(component.isFormValid()).toBe(true);
    });

    it('odrzuca niepoprawne identyfikatory', async () => {
      await setup();

      component.setNumber('project', 0);
      component.setNumber('project', 'nie-liczba');
      expect(component.testrailProjectId()).toBe(12);

      component.setPriorityValue('CRITICAL', -1);
      expect(component.priorityValue('CRITICAL')).toBe(4);
    });

    it('puste pole suite czyści wartość', async () => {
      await setup(makeConfig({ suiteId: 3 }));

      component.setNumber('suite', '');

      expect(component.suiteId()).toBeNull();
    });
  });

  describe('zapis konfiguracji', () => {
    it('wysyła PUT z mapowaniami i czyści pole klucza', async () => {
      await setup();
      component.apiKey.set(API_KEY);
      component.setPriorityValue('HIGH', 8);

      component.save();

      const put = httpTesting.expectOne((r) => r.url === CONFIG_URL && r.method === 'PUT');
      expect(put.request.params.get('project_id')).toBe(PROJECT_ID);
      expect(put.request.body.apiKey).toBe(API_KEY);
      expect(put.request.body.priorityMap.HIGH).toBe(8);
      put.flush(makeConfig());
      fixture.detectChanges();

      // Klucz znika z formularza — nie ma powodu trzymać go w pamięci przeglądarki.
      expect(component.apiKey()).toBe('');
      expect(component.infoMessage()).toContain('zapisana');
    });

    it('pokazuje błąd z backendu', async () => {
      await setup();
      component.apiKey.set(API_KEY);

      component.save();
      httpTesting
        .expectOne((r) => r.url === CONFIG_URL && r.method === 'PUT')
        .flush(
          { detail: 'Adres instancji TestRail musi zaczynać się od https://' },
          { status: 422, statusText: 'Unprocessable' },
        );
      fixture.detectChanges();

      expect(component.errorMessage()).toContain('https://');
      expect(component.isSaving()).toBe(false);
    });
  });

  describe('test połączenia', () => {
    it('pokazuje nazwę projektu przy powodzeniu', async () => {
      await setup();

      component.testConnection();
      httpTesting
        .expectOne((r) => r.url === TEST_URL && r.method === 'POST')
        .flush({ connected: true, message: 'Połączono z projektem „QA”', projectName: 'QA' });
      fixture.detectChanges();

      expect(component.testResult()?.connected).toBe(true);
      expect(fixture.nativeElement.textContent).toContain('Połączono z projektem');
    });

    it('pokazuje komunikat przy niepowodzeniu', async () => {
      await setup();

      component.testConnection();
      httpTesting
        .expectOne((r) => r.url === TEST_URL && r.method === 'POST')
        .flush({ connected: false, message: 'TestRail odrzucił poświadczenia', projectName: null });
      fixture.detectChanges();

      expect(component.testResult()?.connected).toBe(false);
      expect(fixture.nativeElement.textContent).toContain('odrzucił poświadczenia');
    });
  });

  describe('odnośnik do synchronizacji (Story 8.11)', () => {
    it('pokazuje odnośnik po wczytaniu konfiguracji', async () => {
      await setup();

      const link: HTMLAnchorElement | null = fixture.nativeElement.querySelector('.sync-link a');
      expect(component.integrationId()).toBe('c1');
      expect(link?.getAttribute('href')).toBe('/settings/integrations/c1/sync');
    });

    it('bez konfiguracji nie ma czego synchronizować', async () => {
      await setup(null);

      // Ekran synchronizacji potrzebuje identyfikatora integracji, którego
      // przy braku konfiguracji po prostu nie ma.
      expect(component.integrationId()).toBeNull();
      expect(fixture.nativeElement.querySelector('.sync-link')).toBeNull();
    });
  });
});
