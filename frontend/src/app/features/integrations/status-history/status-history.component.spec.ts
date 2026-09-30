import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { StatusHistoryComponent } from './status-history.component';
import { IntegrationEvent } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const INTEGRATION_ID = 'i1';

function makeEvent(overrides: Partial<IntegrationEvent> = {}): IntegrationEvent {
  return {
    id: 'e1',
    eventType: 'pull_request',
    action: 'opened',
    repoFullName: 'acme/app',
    branch: 'feature/x',
    baseBranch: 'main',
    commitSha: 'abcdef1234567890',
    prNumber: 7,
    status: 'completed',
    taskId: 't1',
    errorMessage: null,
    createdAt: '2026-09-02T08:00:00Z',
    completedAt: '2026-09-02T08:02:30Z',
    ...overrides,
  };
}

describe('StatusHistoryComponent', () => {
  let component: StatusHistoryComponent;
  let fixture: ComponentFixture<StatusHistoryComponent>;
  let httpTesting: HttpTestingController;

  async function setup(events: IntegrationEvent[] = [makeEvent()], provider?: string): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [StatusHistoryComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ integrationId: INTEGRATION_ID }),
              queryParamMap: convertToParamMap(provider ? { provider } : {}),
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(StatusHistoryComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const expectedProvider = provider === 'gitlab' ? 'gitlab' : 'github';
    const req = httpTesting.expectOne((r) => r.url === `${environment.apiUrl}/integrations/${expectedProvider}/events`);
    expect(req.request.params.get('integration_id')).toBe(INTEGRATION_ID);
    expect(req.request.params.get('limit')).toBe('50');
    req.flush(events);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('pobiera zdarzenia GitHuba domyślnie', async () => {
    await setup();

    expect(component.provider()).toBe('github');
    expect(fixture.nativeElement.textContent).toContain('Pull request #7 (opened)');
  });

  it('pobiera zdarzenia GitLaba, gdy trasa tak mówi', async () => {
    await setup([makeEvent({ eventType: 'merge_request', action: 'update', prNumber: 42 })], 'gitlab');

    expect(component.provider()).toBe('gitlab');
    expect(fixture.nativeElement.textContent).toContain('Merge request !42 (update)');
  });

  it('wraca na ekran właściwego dostawcy', async () => {
    await setup([], 'gitlab');

    expect(component.backLink).toBe('/settings/integrations/gitlab');
  });

  it('pokazuje pusty stan bez zdarzeń', async () => {
    await setup([]);

    expect(fixture.nativeElement.textContent).toContain('Brak zdarzeń dla tej integracji');
  });

  it('oznacza, dla których zdarzeń status check faktycznie poszedł', async () => {
    await setup([
      makeEvent({ id: 'e1', status: 'completed' }),
      makeEvent({ id: 'e2', status: 'skipped', errorMessage: "Push na gałąź 'dev'" }),
    ]);

    expect(component.hasStatusCheck(makeEvent({ status: 'completed' }))).toBe(true);
    expect(component.hasStatusCheck(makeEvent({ status: 'failed' }))).toBe(true);
    expect(component.hasStatusCheck(makeEvent({ status: 'skipped' }))).toBe(false);
    expect(component.hasStatusCheck(makeEvent({ status: 'pending' }))).toBe(false);

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('wysłany');
    expect(text).toContain("Push na gałąź 'dev'");
  });

  it('liczy czas analizy z obu znaczników', async () => {
    await setup();

    expect(component.durationLabel(makeEvent())).toBe('2 min 30 s');
    expect(component.durationLabel(makeEvent({ completedAt: '2026-09-02T08:00:12Z' }))).toBe('12 s');
  });

  it('nie pokazuje czasu dla niedomkniętych zdarzeń', async () => {
    await setup();

    expect(component.durationLabel(makeEvent({ completedAt: null }))).toBe('—');
  });

  it('skraca sha commita', async () => {
    await setup();

    expect(component.shortSha('abcdef1234567890')).toBe('abcdef1');
    expect(component.shortSha(null)).toBe('—');
  });

  it('informuje o błędzie pobrania historii', async () => {
    await TestBed.configureTestingModule({
      imports: [StatusHistoryComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ integrationId: INTEGRATION_ID }),
              queryParamMap: convertToParamMap({}),
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(StatusHistoryComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    httpTesting
      .expectOne((r) => r.url.endsWith('/integrations/github/events'))
      .flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(component.errorMessage()).toContain('Nie udało się wczytać historii');
  });
});
