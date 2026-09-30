import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { GitlabConnectComponent } from './gitlab-connect.component';
import { GitLabProjectOption, IntegrationEvent, ScmIntegration } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const BASE = `${environment.apiUrl}/integrations/gitlab`;
const PROJECTS_URL = `${BASE}/projects`;
const SELF_HOSTED = 'https://git.firma.pl';

function makeIntegration(overrides: Partial<ScmIntegration> = {}): ScmIntegration {
  return {
    id: 'i1',
    provider: 'gitlab',
    repoFullName: 'grupa/app',
    repoUrl: `${SELF_HOSTED}/grupa/app.git`,
    defaultBranch: 'main',
    projectId: null,
    webhookActive: true,
    isActive: true,
    createdAt: '2026-09-01T10:00:00Z',
    gitlabUrl: SELF_HOSTED,
    ...overrides,
  };
}

function makeEvent(overrides: Partial<IntegrationEvent> = {}): IntegrationEvent {
  return {
    id: 'e1',
    eventType: 'push',
    action: null,
    repoFullName: 'grupa/app',
    branch: 'main',
    baseBranch: null,
    commitSha: 'abcdef1234567890',
    prNumber: null,
    status: 'completed',
    taskId: 't1',
    errorMessage: null,
    createdAt: '2026-09-02T08:00:00Z',
    completedAt: '2026-09-02T08:02:00Z',
    ...overrides,
  };
}

function makeProject(overrides: Partial<GitLabProjectOption> = {}): GitLabProjectOption {
  return {
    projectId: 7,
    pathWithNamespace: 'grupa/app',
    name: 'app',
    visibility: 'private',
    defaultBranch: 'main',
    webUrl: `${SELF_HOSTED}/grupa/app`,
    httpUrlToRepo: `${SELF_HOSTED}/grupa/app.git`,
    connected: false,
    ...overrides,
  };
}

describe('GitlabConnectComponent', () => {
  let component: GitlabConnectComponent;
  let fixture: ComponentFixture<GitlabConnectComponent>;
  let httpTesting: HttpTestingController;

  async function build(queryParams: Record<string, string> = {}): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [GitlabConnectComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap(queryParams) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(GitlabConnectComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  async function setup(
    options: {
      integrations?: ScmIntegration[];
      events?: IntegrationEvent[];
      providerConfigured?: boolean;
      queryParams?: Record<string, string>;
    } = {},
  ): Promise<void> {
    const {
      integrations = [makeIntegration()],
      events = [makeEvent()],
      providerConfigured = true,
      queryParams = {},
    } = options;

    await build(queryParams);

    httpTesting.expectOne(PROJECTS_URL).flush({ items: integrations, total: integrations.length, providerConfigured });
    httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush(events);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje podłączone projekty i zdarzenia przy starcie', async () => {
    await setup();

    expect(component.integrations().length).toBe(1);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('grupa/app');
    expect(text).toContain('Webhook aktywny');
  });

  it('podpowiada adres instancji z już podłączonego projektu', async () => {
    await setup({ integrations: [makeIntegration({ gitlabUrl: SELF_HOSTED })] });

    expect(component.gitlabUrl()).toBe(SELF_HOSTED);
    expect(fixture.nativeElement.textContent).toContain(SELF_HOSTED);
  });

  it('domyślnie proponuje gitlab.com', async () => {
    await setup({ integrations: [], events: [] });

    expect(component.gitlabUrl()).toBe('https://gitlab.com');
  });

  it('pokazuje pusty stan bez projektów', async () => {
    await setup({ integrations: [], events: [] });

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Nie masz jeszcze podłączonych projektów');
    expect(text).toContain('Brak zdarzeń');
  });

  it('ukrywa formularz, gdy serwer nie ma konfiguracji OAuth', async () => {
    await setup({ providerConfigured: false });

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Integracja z GitLab nie jest skonfigurowana');
    expect(text).not.toContain('Połącz z GitLab');
  });

  describe('autoryzacja', () => {
    it('przekazuje adres instancji do backendu i przekierowuje', async () => {
      await setup({ integrations: [], events: [] });
      const setHref = vi.fn();
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: {
          get href() {
            return '';
          },
          set href(value: string) {
            setHref(value);
          },
        },
      });

      component.gitlabUrl.set(SELF_HOSTED);
      component.connectGitLab();

      const req = httpTesting.expectOne(
        (r) => r.url === `${BASE}/authorize` && r.params.get('gitlab_url') === SELF_HOSTED,
      );
      req.flush({ authorizationUrl: `${SELF_HOSTED}/oauth/authorize?state=x` });

      expect(setHref).toHaveBeenCalledWith(`${SELF_HOSTED}/oauth/authorize?state=x`);
    });

    it('obcina końcowy ukośnik w adresie instancji', async () => {
      await setup({ integrations: [], events: [] });
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: { href: '' },
      });

      component.gitlabUrl.set('https://git.firma.pl/');
      component.connectGitLab();

      const req = httpTesting.expectOne(
        (r) => r.url === `${BASE}/authorize` && r.params.get('gitlab_url') === SELF_HOSTED,
      );
      req.flush({ authorizationUrl: 'https://x' });
    });

    it('odrzuca adres bez https bez wysyłania żądania', async () => {
      await setup({ integrations: [], events: [] });

      component.gitlabUrl.set('http://git.firma.pl');
      component.connectGitLab();

      expect(component.errorMessage()).toContain('https://');
      httpTesting.expectNone((r) => r.url === `${BASE}/authorize`);
    });

    it('tłumaczy kod błędu z callbacku na komunikat po polsku', async () => {
      await setup({ queryParams: { error: 'token_exchange' } });

      expect(component.errorMessage()).toContain('GitLab odrzucił autoryzację');
    });

    it('po powrocie z GitLaba otwiera wybór projektów', async () => {
      await build({ connected: '1' });

      httpTesting.expectOne(PROJECTS_URL).flush({ items: [], total: 0, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      httpTesting
        .expectOne((r) => r.url === `${BASE}/available-projects`)
        .flush([makeProject(), makeProject({ projectId: 8, pathWithNamespace: 'grupa/inny', connected: true })]);
      fixture.detectChanges();

      expect(component.isProjectPickerOpen()).toBe(true);
      expect(component.availableProjects().length).toBe(2);
      expect(fixture.nativeElement.textContent).toContain('Podłączony');
    });
  });

  describe('podłączanie projektu', () => {
    it('wysyła identyfikator liczbowy projektu i adres instancji', async () => {
      await setup({ integrations: [], events: [] });
      component.gitlabUrl.set(SELF_HOSTED);

      component.openProjectPicker();
      httpTesting.expectOne((r) => r.url === `${BASE}/available-projects`).flush([makeProject()]);
      fixture.detectChanges();

      component.connectProject(makeProject());
      const post = httpTesting.expectOne((r) => r.url === PROJECTS_URL && r.method === 'POST');
      expect(post.request.body.projectId).toBe(7);
      expect(post.request.params.get('gitlab_url')).toBe(SELF_HOSTED);
      post.flush(makeIntegration());

      httpTesting.expectOne(PROJECTS_URL).flush({ items: [makeIntegration()], total: 1, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      fixture.detectChanges();

      expect(component.isProjectPickerOpen()).toBe(false);
      expect(component.infoMessage()).toContain('został podłączony');
    });

    it('nie wysyła żądania dla już podłączonego projektu', async () => {
      await setup({ integrations: [], events: [] });

      component.openProjectPicker();
      httpTesting.expectOne((r) => r.url === `${BASE}/available-projects`).flush([makeProject({ connected: true })]);

      component.connectProject(makeProject({ connected: true }));

      httpTesting.expectNone((r) => r.url === PROJECTS_URL && r.method === 'POST');
      component.closeProjectPicker();
    });

    it('pokazuje konflikt z backendu', async () => {
      await setup({ integrations: [], events: [] });

      component.openProjectPicker();
      httpTesting.expectOne((r) => r.url === `${BASE}/available-projects`).flush([makeProject()]);

      component.connectProject(makeProject());
      httpTesting
        .expectOne((r) => r.url === PROJECTS_URL && r.method === 'POST')
        .flush({ detail: 'Ten projekt jest już podłączony' }, { status: 409, statusText: 'Conflict' });
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Ten projekt jest już podłączony');
      expect(component.connectingProjectId()).toBeNull();
      component.closeProjectPicker();
    });
  });

  describe('odłączanie projektu', () => {
    it('wymaga potwierdzenia przed DELETE', async () => {
      await setup();

      component.askRemove('i1');
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Odłączyć projekt?');
      httpTesting.expectNone(`${PROJECTS_URL}/i1`);

      component.confirmRemove();
      const del = httpTesting.expectOne(`${PROJECTS_URL}/i1`);
      expect(del.request.method).toBe('DELETE');
      del.flush(null);

      httpTesting.expectOne(PROJECTS_URL).flush({ items: [], total: 0, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      fixture.detectChanges();

      expect(component.integrations().length).toBe(0);
    });

    it('anulowanie nie wysyła żądania', async () => {
      await setup();

      component.askRemove('i1');
      component.cancelRemove();
      fixture.detectChanges();

      expect(component.pendingRemovalId()).toBeNull();
      httpTesting.expectNone(`${PROJECTS_URL}/i1`);
    });
  });

  describe('etykiety zdarzeń', () => {
    it('opisuje merge request numerem z wykrzyknikiem, jak GitLab', async () => {
      await setup({
        events: [
          makeEvent({ id: 'e1', eventType: 'push', branch: 'main' }),
          makeEvent({
            id: 'e2',
            eventType: 'merge_request',
            action: 'update',
            prNumber: 42,
          }),
        ],
      });

      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Push na main');
      expect(text).toContain('Merge request !42 (update)');
    });

    it('pokazuje powód pominięcia zdarzenia', async () => {
      await setup({
        events: [
          makeEvent({
            status: 'skipped',
            errorMessage: "Akcja merge requesta 'close' nie wymaga analizy",
          }),
        ],
      });

      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Pominięte');
      expect(text).toContain('nie wymaga analizy');
    });
  });

  describe('status check (Story 8.3)', () => {
    it('otwiera ustawienia status checka dla wiersza', async () => {
      await setup({ integrations: [makeIntegration({ id: 'i9' })] });

      component.openStatusConfig('i9', 'grupa/app');
      fixture.detectChanges();

      const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/i9/config`);
      req.flush({
        integrationId: 'i9',
        severityThreshold: 'high',
        postComment: false,
        failOnThreshold: true,
        statusContext: 'TestGEN / Code Analysis',
      });
      fixture.detectChanges();

      expect(component.configuringId()).toBe('i9');
      expect(fixture.nativeElement.textContent).toContain('Próg blokowania');
    });

    it('wiersz prowadzi do historii status checków dostawcy', async () => {
      await setup({ integrations: [makeIntegration({ id: 'i9' })] });

      const link = fixture.nativeElement.querySelector('a[href*="/history"]') as HTMLAnchorElement;

      expect(link.getAttribute('href')).toContain('/settings/integrations/i9/history');
      expect(link.getAttribute('href')).toContain('provider=gitlab');
    });
  });
});
