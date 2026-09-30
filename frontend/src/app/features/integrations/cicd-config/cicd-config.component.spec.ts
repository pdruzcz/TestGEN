import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { CicdConfigComponent } from './cicd-config.component';
import { CicdConfig, CicdTemplateList } from '../../../core/services/cicd.service';
import { environment } from '../../../../environments/environment';

const PROJECT_ID = 'p1';
const BASE = `${environment.apiUrl}/projects/${PROJECT_ID}/ci-cd`;

const TEMPLATES: CicdTemplateList = {
  platforms: [
    {
      platform: 'github_actions',
      label: 'GitHub Actions',
      filename: '.github/workflows/testgen.yml',
      language: 'yaml',
      description: 'Workflow uruchamiany przy push i pull request.',
      secretHint: 'Dodaj sekret repozytorium TESTGEN_API_KEY w Settings → Secrets.',
    },
    {
      platform: 'jenkins',
      label: 'Jenkins',
      filename: 'Jenkinsfile',
      language: 'groovy',
      description: 'Deklaratywny Jenkinsfile.',
      secretHint: 'Dodaj poświadczenie typu Secret text o identyfikatorze testgen_api_key.',
    },
  ],
  availableModules: ['code_analysis', 'security_scan'],
  availableEngineModes: ['native', 'llm', 'hybrid'],
  availableThresholds: ['critical', 'high', 'medium'],
  apiKeyVariable: 'TESTGEN_API_KEY',
};

function makeConfig(overrides: Partial<CicdConfig> = {}): CicdConfig {
  return {
    platform: 'github_actions',
    filename: '.github/workflows/testgen.yml',
    language: 'yaml',
    content: 'name: Analiza TestGEN\non: [push, pull_request]\n',
    secretHint: 'Dodaj sekret repozytorium TESTGEN_API_KEY.',
    ...overrides,
  };
}

describe('CicdConfigComponent', () => {
  let component: CicdConfigComponent;
  let fixture: ComponentFixture<CicdConfigComponent>;
  let httpTesting: HttpTestingController;

  async function setup(): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [CicdConfigComponent, NoopAnimationsModule],
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

    fixture = TestBed.createComponent(CicdConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    httpTesting.expectOne(`${BASE}/templates`).flush(TEMPLATES);
    // Podgląd generuje się od razu po wczytaniu katalogu platform.
    httpTesting.expectOne(`${BASE}/generate`).flush(makeConfig());
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje katalog platform i od razu generuje podgląd', async () => {
    await setup();

    expect(component.platforms().length).toBe(2);
    expect(component.config()?.filename).toBe('.github/workflows/testgen.yml');
    expect(fixture.nativeElement.textContent).toContain('Analiza TestGEN');
  });

  it('pokazuje instrukcję dodania klucza dla wybranej platformy', async () => {
    await setup();

    expect(fixture.nativeElement.textContent).toContain('TESTGEN_API_KEY');
    expect(component.platformInfo()?.label).toBe('GitHub Actions');
  });

  it('tłumaczy parametry na polskie etykiety', async () => {
    await setup();

    expect(component.moduleLabel('code_analysis')).toBe('Analiza kodu');
    expect(component.moduleLabel('security_scan')).toBe('Skan bezpieczeństwa');
    expect(component.thresholdLabel('critical')).toBe('Krytyczny');
    expect(component.engineLabel('native')).toContain('Natywny');
    // Nieznana wartość wraca bez zmian, zamiast znikać z interfejsu
    expect(component.moduleLabel('nowy_modul')).toBe('nowy_modul');
  });

  it('pokazuje nazwę pliku docelowego', async () => {
    await setup();

    expect(fixture.nativeElement.textContent).toContain('.github/workflows/testgen.yml');
  });

  describe('regeneracja po zmianie parametrów (AC6)', () => {
    it('zmiana platformy generuje nową konfigurację', async () => {
      await setup();

      component.selectPlatform('jenkins');
      const req = httpTesting.expectOne(`${BASE}/generate`);
      expect(req.request.body.platform).toBe('jenkins');
      req.flush(makeConfig({ platform: 'jenkins', filename: 'Jenkinsfile', language: 'groovy' }));
      fixture.detectChanges();

      expect(component.config()?.filename).toBe('Jenkinsfile');
      expect(fixture.nativeElement.textContent).toContain('Jenkinsfile');
    });

    it('zmiana progu trafia do żądania', async () => {
      await setup();

      component.setThreshold('high');
      const req = httpTesting.expectOne(`${BASE}/generate`);
      expect(req.request.body.severityThreshold).toBe('high');
      req.flush(makeConfig());
    });

    it('zmiana trybu silnika trafia do żądania', async () => {
      await setup();

      component.setEngineMode('hybrid');
      const req = httpTesting.expectOne(`${BASE}/generate`);
      expect(req.request.body.engineMode).toBe('hybrid');
      req.flush(makeConfig());
    });

    it('zaznaczenie modułu trafia do żądania', async () => {
      await setup();

      component.toggleModule('security_scan');
      const req = httpTesting.expectOne(`${BASE}/generate`);
      expect(req.request.body.modules).toEqual(['code_analysis', 'security_scan']);
      req.flush(makeConfig());
    });

    it('nie pozwala odznaczyć ostatniego modułu', async () => {
      await setup();

      expect(component.modules()).toEqual(['code_analysis']);
      component.toggleModule('code_analysis');

      expect(component.modules()).toEqual(['code_analysis']);
      httpTesting.expectNone(`${BASE}/generate`);
    });

    it('odrzuca timeout spoza zakresu bez wysyłania żądania', async () => {
      await setup();

      component.setTimeout(0);
      component.setTimeout(500);
      component.setTimeout('nie-liczba');

      expect(component.timeoutMinutes()).toBe(30);
      httpTesting.expectNone(`${BASE}/generate`);
    });

    it('przyjmuje poprawny timeout', async () => {
      await setup();

      component.setTimeout('45');
      const req = httpTesting.expectOne(`${BASE}/generate`);
      expect(req.request.body.timeoutMinutes).toBe(45);
      req.flush(makeConfig());
    });

    it('pokazuje błąd generowania z backendu', async () => {
      await setup();

      component.setThreshold('high');
      httpTesting
        .expectOne(`${BASE}/generate`)
        .flush({ detail: 'Nieprawidłowy próg' }, { status: 422, statusText: 'Unprocessable' });
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Nieprawidłowy próg');
      expect(component.isGenerating()).toBe(false);
    });
  });

  describe('kopiowanie i pobieranie (AC5)', () => {
    it('kopiuje treść konfiguracji do schowka', async () => {
      await setup();
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      component.copy();
      await Promise.resolve();
      await Promise.resolve();

      expect(writeText).toHaveBeenCalledWith(makeConfig().content);
      expect(component.copyMessage()).toContain('Skopiowano');
    });

    it('informuje, gdy przeglądarka odmówi dostępu do schowka', async () => {
      await setup();
      Object.assign(navigator, {
        clipboard: { writeText: vi.fn().mockRejectedValue(new Error('odmowa')) },
      });

      component.copy();
      await Promise.resolve();
      await Promise.resolve();

      expect(component.copyMessage()).toContain('ręcznie');
    });

    it('pobiera plik pod samą nazwą, bez ścieżki', async () => {
      await setup();
      const click = vi.fn();
      const anchor = { href: '', download: '', click } as unknown as HTMLAnchorElement;
      vi.spyOn(document, 'createElement').mockReturnValue(anchor);
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:testgen');
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);

      component.download();

      expect(anchor.download).toBe('testgen.yml');
      expect(click).toHaveBeenCalled();
      vi.restoreAllMocks();
    });
  });
});
