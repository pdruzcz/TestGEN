import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { GithubConnectComponent } from './github-connect.component';
import { IntegrationEvent, ScmIntegration, ScmRepoOption } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const BASE = `${environment.apiUrl}/integrations/github`;
const REPOS_URL = `${BASE}/repos`;

function makeIntegration(overrides: Partial<ScmIntegration> = {}): ScmIntegration {
  return {
    id: 'i1',
    provider: 'github',
    repoFullName: 'acme/app',
    repoUrl: 'https://github.com/acme/app.git',
    defaultBranch: 'main',
    projectId: null,
    webhookActive: true,
    isActive: true,
    createdAt: '2026-09-01T10:00:00Z',
    gitlabUrl: null, // pole wspólnego kontraktu, dla GitHuba zawsze puste
    ...overrides,
  };
}

function makeEvent(overrides: Partial<IntegrationEvent> = {}): IntegrationEvent {
  return {
    id: 'e1',
    eventType: 'push',
    action: null,
    repoFullName: 'acme/app',
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

function makeRepo(overrides: Partial<ScmRepoOption> = {}): ScmRepoOption {
  return {
    fullName: 'acme/app',
    name: 'app',
    private: true,
    defaultBranch: 'main',
    htmlUrl: 'https://github.com/acme/app',
    cloneUrl: 'https://github.com/acme/app.git',
    connected: false,
    ...overrides,
  };
}

describe('GithubConnectComponent', () => {
  let component: GithubConnectComponent;
  let fixture: ComponentFixture<GithubConnectComponent>;
  let httpTesting: HttpTestingController;

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

    await TestBed.configureTestingModule({
      imports: [GithubConnectComponent, NoopAnimationsModule],
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

    fixture = TestBed.createComponent(GithubConnectComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    httpTesting.expectOne(REPOS_URL).flush({ items: integrations, total: integrations.length, providerConfigured });
    httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush(events);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje podłączone repozytoria i zdarzenia przy starcie', async () => {
    await setup();

    expect(component.integrations().length).toBe(1);
    expect(component.events().length).toBe(1);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('acme/app');
    expect(text).toContain('Webhook aktywny');
  });

  it('pokazuje pusty stan bez repozytoriów', async () => {
    await setup({ integrations: [], events: [] });

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Nie masz jeszcze podłączonych repozytoriów');
    expect(text).toContain('Brak zdarzeń');
  });

  it('ukrywa przycisk łączenia, gdy serwer nie ma konfiguracji OAuth', async () => {
    await setup({ providerConfigured: false });

    expect(fixture.nativeElement.textContent).toContain('Integracja z GitHub nie jest skonfigurowana');
  });

  it('oznacza nieaktywny webhook', async () => {
    await setup({ integrations: [makeIntegration({ webhookActive: false })] });

    expect(fixture.nativeElement.textContent).toContain('Webhook nieaktywny');
  });

  describe('autoryzacja', () => {
    it('przekierowuje na adres zwrócony przez backend', async () => {
      await setup({ integrations: [], events: [] });
      const original = window.location.href;
      const setHref = vi.fn();
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: {
          get href() {
            return original;
          },
          set href(value: string) {
            setHref(value);
          },
        },
      });

      component.connectGitHub();
      httpTesting
        .expectOne(`${BASE}/authorize`)
        .flush({ authorizationUrl: 'https://github.com/login/oauth/authorize?state=x' });

      expect(setHref).toHaveBeenCalledWith('https://github.com/login/oauth/authorize?state=x');
    });

    it('pokazuje błąd, gdy backend odmówi autoryzacji', async () => {
      await setup({ integrations: [], events: [] });

      component.connectGitHub();
      httpTesting
        .expectOne(`${BASE}/authorize`)
        .flush(
          { detail: 'Integracja z GitHub nie jest skonfigurowana' },
          { status: 422, statusText: 'Unprocessable Entity' },
        );
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Integracja z GitHub nie jest skonfigurowana');
    });

    it('tłumaczy kod błędu z callbacku na komunikat po polsku', async () => {
      await setup({ queryParams: { error: 'invalid_state' } });

      expect(component.errorMessage()).toContain('Autoryzacja wygasła');
    });

    it('po powrocie z GitHuba od razu otwiera wybór repozytoriów', async () => {
      await TestBed.configureTestingModule({
        imports: [GithubConnectComponent, NoopAnimationsModule],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          provideRouter([]),
          {
            provide: ActivatedRoute,
            useValue: {
              snapshot: { queryParamMap: convertToParamMap({ connected: '1' }) },
            },
          },
        ],
      }).compileComponents();

      fixture = TestBed.createComponent(GithubConnectComponent);
      component = fixture.componentInstance;
      httpTesting = TestBed.inject(HttpTestingController);
      fixture.detectChanges();

      httpTesting.expectOne(REPOS_URL).flush({ items: [], total: 0, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      httpTesting
        .expectOne(`${BASE}/available-repos`)
        .flush([makeRepo(), makeRepo({ fullName: 'acme/api', connected: true })]);
      fixture.detectChanges();

      expect(component.isRepoPickerOpen()).toBe(true);
      expect(component.availableRepos().length).toBe(2);
      expect(fixture.nativeElement.textContent).toContain('Podłączone');
    });
  });

  describe('podłączanie repozytorium', () => {
    it('wysyła POST i odświeża listę', async () => {
      await setup({ integrations: [], events: [] });

      component.openRepoPicker();
      httpTesting.expectOne(`${BASE}/available-repos`).flush([makeRepo()]);
      fixture.detectChanges();

      component.connectRepo(makeRepo());
      const post = httpTesting.expectOne(REPOS_URL);
      expect(post.request.method).toBe('POST');
      expect(post.request.body.fullName).toBe('acme/app');
      post.flush(makeIntegration());

      httpTesting.expectOne(REPOS_URL).flush({ items: [makeIntegration()], total: 1, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      fixture.detectChanges();

      expect(component.isRepoPickerOpen()).toBe(false);
      expect(component.infoMessage()).toContain('zostało podłączone');
    });

    it('nie wysyła żądania dla już podłączonego repozytorium', async () => {
      await setup({ integrations: [], events: [] });

      component.openRepoPicker();
      httpTesting.expectOne(`${BASE}/available-repos`).flush([makeRepo({ connected: true })]);

      component.connectRepo(makeRepo({ connected: true }));

      httpTesting.expectNone(REPOS_URL);
      component.closeRepoPicker();
    });

    it('pokazuje konflikt z backendu', async () => {
      await setup({ integrations: [], events: [] });

      component.openRepoPicker();
      httpTesting.expectOne(`${BASE}/available-repos`).flush([makeRepo()]);

      component.connectRepo(makeRepo());
      httpTesting
        .expectOne(REPOS_URL)
        .flush({ detail: 'To repozytorium jest już podłączone' }, { status: 409, statusText: 'Conflict' });
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('To repozytorium jest już podłączone');
      expect(component.connectingRepo()).toBeNull();
      component.closeRepoPicker();
    });
  });

  describe('odłączanie repozytorium', () => {
    it('wymaga potwierdzenia przed DELETE', async () => {
      await setup();

      component.askRemove('i1');
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Odłączyć repozytorium?');
      httpTesting.expectNone(`${REPOS_URL}/i1`);

      component.confirmRemove();
      const del = httpTesting.expectOne(`${REPOS_URL}/i1`);
      expect(del.request.method).toBe('DELETE');
      del.flush(null);

      httpTesting.expectOne(REPOS_URL).flush({ items: [], total: 0, providerConfigured: true });
      httpTesting.expectOne((r) => r.url === `${BASE}/events`).flush([]);
      fixture.detectChanges();

      expect(component.pendingRemovalId()).toBeNull();
      expect(component.integrations().length).toBe(0);
    });

    it('anulowanie nie wysyła żądania', async () => {
      await setup();

      component.askRemove('i1');
      component.cancelRemove();
      fixture.detectChanges();

      expect(component.pendingRemovalId()).toBeNull();
      httpTesting.expectNone(`${REPOS_URL}/i1`);
    });
  });

  describe('etykiety zdarzeń', () => {
    it('opisuje push gałęzią, a pull request numerem', async () => {
      await setup({
        events: [
          makeEvent({ id: 'e1', eventType: 'push', branch: 'main' }),
          makeEvent({
            id: 'e2',
            eventType: 'pull_request',
            action: 'synchronize',
            prNumber: 7,
          }),
        ],
      });

      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Push na main');
      expect(text).toContain('Pull request #7 (synchronize)');
    });

    it('pokazuje powód pominięcia zdarzenia', async () => {
      await setup({
        events: [
          makeEvent({
            status: 'skipped',
            errorMessage: "Push na gałąź 'dev' — analizujemy tylko: main, master",
          }),
        ],
      });

      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Pominięte');
      expect(text).toContain('analizujemy tylko');
    });

    it('skraca sha commita do siedmiu znaków', async () => {
      await setup({ events: [makeEvent({ commitSha: 'abcdef1234567890' })] });

      expect(component.shortSha('abcdef1234567890')).toBe('abcdef1');
      expect(component.shortSha(null)).toBe('—');
      expect(fixture.nativeElement.textContent).toContain('abcdef1');
    });
  });

  describe('status check (Story 8.3)', () => {
    it('otwiera ustawienia status checka dla wiersza', async () => {
      await setup({ integrations: [makeIntegration({ id: 'i9', repoFullName: 'acme/app' })] });

      component.openStatusConfig('i9', 'acme/app');
      fixture.detectChanges();

      // Dialog sam dociąga konfigurację — to potwierdza, że został osadzony
      const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/i9/config`);
      req.flush({
        integrationId: 'i9',
        severityThreshold: 'critical',
        postComment: true,
        failOnThreshold: true,
        statusContext: 'TestGEN / Code Analysis',
      });
      fixture.detectChanges();

      expect(component.configuringId()).toBe('i9');
      expect(fixture.nativeElement.textContent).toContain('Próg blokowania');
    });

    it('zapisanie ustawień zamyka dialog i potwierdza', async () => {
      await setup();

      component.onStatusConfigSaved();
      fixture.detectChanges();

      expect(component.configuringId()).toBeNull();
      expect(component.infoMessage()).toContain('status checka');
    });

    it('wiersz prowadzi do historii status checków', async () => {
      await setup({ integrations: [makeIntegration({ id: 'i9' })] });

      const link = fixture.nativeElement.querySelector('a[href*="/history"]') as HTMLAnchorElement;

      expect(link).toBeTruthy();
      expect(link.getAttribute('href')).toContain('/settings/integrations/i9/history');
      expect(link.getAttribute('href')).toContain('provider=github');
    });
  });
});
