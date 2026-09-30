import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { JiraConfigComponent } from './jira-config.component';
import { JiraTmsConfig } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const PROJECT_ID = 'p1';
const CONFIG_URL = `${environment.apiUrl}/integrations/jira/config`;
const TEST_URL = `${environment.apiUrl}/integrations/jira/test`;
const JIRA_URL = 'https://firma.atlassian.net';
const TOKEN = 'token-atlassian';

function makeConfig(overrides: Partial<JiraTmsConfig> = {}): JiraTmsConfig {
  return {
    id: 'c1',
    projectId: PROJECT_ID,
    baseUrl: JIRA_URL,
    email: 'qa@firma.pl',
    projectKey: 'QA',
    plugin: 'xray',
    linkedIssue: 'QA-42',
    priorityMap: { CRITICAL: 'Highest', HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' },
    typeLabels: { FUNCTIONAL: 'typ-funkcjonalny', SECURITY: 'typ-bezpieczenstwa' },
    isActive: true,
    createdAt: '2026-09-01T10:00:00Z',
    ...overrides,
  };
}

describe('JiraConfigComponent', () => {
  let component: JiraConfigComponent;
  let fixture: ComponentFixture<JiraConfigComponent>;
  let httpTesting: HttpTestingController;

  async function build(): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [JiraConfigComponent, NoopAnimationsModule],
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

    fixture = TestBed.createComponent(JiraConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  async function setup(config: JiraTmsConfig | null = makeConfig()): Promise<void> {
    await build();
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
    expect(component.plugin()).toBe('xray');
    expect(component.projectKey()).toBe('QA');
    expect(component.linkedIssue()).toBe('QA-42');
  });

  it('brak konfiguracji to normalny stan', async () => {
    await setup(null);

    expect(component.isConfigured()).toBe(false);
    expect(component.errorMessage()).toBeNull();
  });

  it('wyjaśnia różnicę między wtyczkami', async () => {
    await setup();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Jira Xray');
    expect(text).toContain('Zephyr Scale');
    expect(component.pluginHint('xray')).toContain('etykiecie');
    expect(component.pluginHint('zephyr')).toContain('testgen_id');
  });

  it('ostrzega o polu własnym dopiero przy Zephyrze', async () => {
    await setup(makeConfig({ plugin: 'zephyr' }));

    expect(fixture.nativeElement.textContent).toContain('testgen_id');
  });

  it('pokazuje mapowania tekstowe Jiry', async () => {
    await setup();

    expect(component.priorityValue('CRITICAL')).toBe('Highest');
    expect(component.typeLabelValue('SECURITY')).toBe('typ-bezpieczenstwa');
  });

  describe('walidacja formularza', () => {
    it('wymaga https, e-maila i klucza projektu', async () => {
      await setup(null);

      expect(component.isFormValid()).toBe(false);

      component.baseUrl.set('http://firma.atlassian.net');
      component.email.set('qa@firma.pl');
      component.apiToken.set(TOKEN);
      component.projectKey.set('QA');
      expect(component.isFormValid()).toBe(false); // http odpada

      component.baseUrl.set(JIRA_URL);
      expect(component.isFormValid()).toBe(true);

      component.projectKey.set('');
      expect(component.isFormValid()).toBe(false);
    });

    it('przy istniejącej konfiguracji token nie jest wymagany', async () => {
      await setup();

      expect(component.apiToken()).toBe('');
      expect(component.isFormValid()).toBe(true);
    });
  });

  describe('zapis konfiguracji', () => {
    it('wysyła wybraną wtyczkę i mapowania', async () => {
      await setup();
      component.apiToken.set(TOKEN);
      component.selectPlugin('zephyr');
      component.setPriorityValue('CRITICAL', 'Blocker');

      component.save();

      const put = httpTesting.expectOne((r) => r.url === CONFIG_URL && r.method === 'PUT');
      expect(put.request.body.plugin).toBe('zephyr');
      expect(put.request.body.apiToken).toBe(TOKEN);
      expect(put.request.body.priorityMap.CRITICAL).toBe('Blocker');
      expect(put.request.body.linkedIssue).toBe('QA-42');
      put.flush(makeConfig({ plugin: 'zephyr' }));
      fixture.detectChanges();

      // Token znika z formularza — nie ma powodu trzymać go w pamięci przeglądarki.
      expect(component.apiToken()).toBe('');
      expect(component.infoMessage()).toContain('zapisana');
    });

    it('puste powiązane zgłoszenie idzie jako null', async () => {
      await setup();
      component.apiToken.set(TOKEN);
      component.linkedIssue.set('   ');

      component.save();

      const put = httpTesting.expectOne((r) => r.url === CONFIG_URL && r.method === 'PUT');
      expect(put.request.body.linkedIssue).toBeNull();
      put.flush(makeConfig());
    });

    it('pokazuje błąd z backendu', async () => {
      await setup();
      component.apiToken.set(TOKEN);

      component.save();
      httpTesting
        .expectOne((r) => r.url === CONFIG_URL && r.method === 'PUT')
        .flush(
          { detail: 'Adres instancji Jira musi zaczynać się od https://' },
          { status: 422, statusText: 'Unprocessable' },
        );
      fixture.detectChanges();

      expect(component.errorMessage()).toContain('https://');
    });
  });

  describe('test połączenia', () => {
    it('pokazuje konto i projekt przy powodzeniu', async () => {
      await setup();

      component.testConnection();
      httpTesting
        .expectOne((r) => r.url === TEST_URL && r.method === 'POST')
        .flush({
          connected: true,
          message: 'Połączono z projektem „Projekt QA” jako Anna QA',
          projectName: 'Projekt QA',
          account: 'Anna QA',
        });
      fixture.detectChanges();

      expect(component.testResult()?.connected).toBe(true);
      expect(fixture.nativeElement.textContent).toContain('Anna QA');
    });

    it('pokazuje komunikat przy niepowodzeniu', async () => {
      await setup();

      component.testConnection();
      httpTesting
        .expectOne((r) => r.url === TEST_URL && r.method === 'POST')
        .flush({
          connected: false,
          message: 'Jira odrzuciła poświadczenia',
          projectName: null,
          account: null,
        });
      fixture.detectChanges();

      expect(component.testResult()?.connected).toBe(false);
      expect(fixture.nativeElement.textContent).toContain('odrzuciła poświadczenia');
    });
  });
});
