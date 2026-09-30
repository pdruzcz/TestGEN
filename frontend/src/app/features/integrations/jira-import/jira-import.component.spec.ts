import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { JiraImportComponent } from './jira-import.component';
import { JiraImportState, JiraProjectOption } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const PROJECT_ID = 'p1';
const PROJECTS_URL = `${environment.apiUrl}/projects/${PROJECT_ID}/import/jira/projects`;
const STATUS_URL = `${environment.apiUrl}/projects/${PROJECT_ID}/import/jira/status`;
const IMPORT_URL = `${environment.apiUrl}/projects/${PROJECT_ID}/import/jira`;

function makeState(overrides: Partial<JiraImportState> = {}): JiraImportState {
  return {
    id: 'i1',
    projectId: PROJECT_ID,
    integrationId: 'int1',
    jiraProjectKey: 'QA',
    issueTypes: ['Story', 'Epic'],
    status: 'completed',
    lastImportAt: '2026-09-25T10:00:00Z',
    totalImported: 12,
    totalAttachments: 3,
    totalSkipped: 0,
    lastError: null,
    taskId: 't1',
    documentFileId: 'd1',
    createdAt: '2026-09-20T10:00:00Z',
    ...overrides,
  };
}

describe('JiraImportComponent', () => {
  let component: JiraImportComponent;
  let fixture: ComponentFixture<JiraImportComponent>;
  let httpTesting: HttpTestingController;

  async function setup(
    projects: JiraProjectOption[] | null = [{ key: 'QA', name: 'Jakość' }],
    imports: JiraImportState[] = [],
  ): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [JiraImportComponent, NoopAnimationsModule],
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

    fixture = TestBed.createComponent(JiraImportComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const projectsReq = httpTesting.expectOne(PROJECTS_URL);
    if (projects) {
      projectsReq.flush({ items: projects, total: projects.length });
    } else {
      projectsReq.flush({ detail: 'brak' }, { status: 404, statusText: 'Not Found' });
    }
    httpTesting.expectOne(STATUS_URL).flush(imports);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('pokazuje projekty Jiry do wyboru', async () => {
    await setup();

    expect(component.jiraProjects().length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('QA — Jakość');
  });

  it('brak integracji tłumaczy się po polsku', async () => {
    await setup(null);

    expect(component.errorMessage()).toContain('nie jest skonfigurowana');
  });

  it('bez wybranego projektu nie da się zaimportować', async () => {
    await setup();

    expect(component.canImport()).toBe(false);
  });

  it('domyślnie importuje tylko zmiany', async () => {
    await setup();
    component.selectedProjectKey = 'QA';

    component.startImport();
    const req = httpTesting.expectOne(IMPORT_URL);

    // Pełny import przy dużym projekcie Jiry trwa znacznie dłużej,
    // więc musi być wyborem świadomym.
    expect(req.request.body.fullReimport).toBe(false);
    expect(req.request.body.updatedAfter).toBeNull();
    req.flush({ importId: 'i2', taskId: 't2', status: 'accepted', statusUrl: '/api/v1/tasks/t2' });
    httpTesting.expectOne(STATUS_URL).flush([]);
  });

  it('pełny import zaznacza się w żądaniu', async () => {
    await setup();
    component.selectedProjectKey = 'QA';
    component.scope = 'full';

    component.startImport();
    const req = httpTesting.expectOne(IMPORT_URL);

    expect(req.request.body.fullReimport).toBe(true);
    req.flush({ importId: 'i2', taskId: 't2', status: 'accepted', statusUrl: null });
    httpTesting.expectOne(STATUS_URL).flush([]);
  });

  it('import od daty wysyła znacznik czasu', async () => {
    await setup();
    component.selectedProjectKey = 'QA';
    component.scope = 'since';
    component.sinceDate = '2026-01-15';

    component.startImport();
    const req = httpTesting.expectOne(IMPORT_URL);

    expect(req.request.body.updatedAfter).toBe('2026-01-15T00:00:00Z');
    req.flush({ importId: 'i2', taskId: 't2', status: 'accepted', statusUrl: null });
    httpTesting.expectOne(STATUS_URL).flush([]);
  });

  it('typy zgłoszeń da się odznaczyć', async () => {
    await setup();

    component.toggleType('Bug');

    expect(component.isTypeSelected('Bug')).toBe(false);
    expect(component.selectedTypes).toEqual(['Story', 'Epic']);
  });

  it('po uruchomieniu importu pokazuje komunikat', async () => {
    await setup();
    component.selectedProjectKey = 'QA';

    component.startImport();
    httpTesting.expectOne(IMPORT_URL).flush({ importId: 'i2', taskId: 't2', status: 'accepted', statusUrl: null });
    httpTesting.expectOne(STATUS_URL).flush([]);
    fixture.detectChanges();

    expect(component.infoMessage()).toContain('Import uruchomiony');
  });

  it('błąd backendu trafia do komunikatu', async () => {
    await setup();
    component.selectedProjectKey = 'QA';

    component.startImport();
    httpTesting
      .expectOne(IMPORT_URL)
      .flush({ detail: 'Nieobsługiwane typy zgłoszeń: Spike' }, { status: 422, statusText: 'x' });
    fixture.detectChanges();

    expect(component.errorMessage()).toContain('Spike');
  });

  it('historia importów podsumowuje wynik po polsku', async () => {
    await setup([{ key: 'QA', name: 'Jakość' }], [makeState()]);

    expect(component.summaryOf(makeState())).toBe('Zaimportowano 12 wymagań i 3 załączniki.');
    expect(fixture.nativeElement.textContent).toContain('Zakończony');
  });

  it('pominięte zgłoszenia są wymienione w podsumowaniu', async () => {
    await setup([{ key: 'QA', name: 'Jakość' }], [makeState({ totalSkipped: 2 })]);

    expect(component.summaryOf(makeState({ totalSkipped: 2 }))).toContain('pominięto 2 zgłoszenia');
    expect(fixture.nativeElement.textContent).toContain('pominięto 2 zgłoszenia');
  });

  it('odmienia liczebniki zgodnie z polską gramatyką', async () => {
    await setup();

    expect(component.summaryOf(makeState({ totalImported: 1, totalAttachments: 1 }))).toContain(
      '1 wymaganie i 1 załącznik',
    );
    expect(component.summaryOf(makeState({ totalImported: 5, totalAttachments: 22 }))).toContain(
      '5 wymagań i 22 załączniki',
    );
  });

  it('nieudany import pokazuje powód', async () => {
    await setup(
      [{ key: 'QA', name: 'Jakość' }],
      [makeState({ status: 'failed', lastError: 'Jira odrzuciła poświadczenia' })],
    );

    expect(fixture.nativeElement.textContent).toContain('Nieudany');
    expect(fixture.nativeElement.textContent).toContain('Jira odrzuciła poświadczenia');
  });
});
