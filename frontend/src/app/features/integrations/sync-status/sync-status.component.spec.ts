import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { SyncStatusComponent } from './sync-status.component';
import { SyncConflict, SyncStatus } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const INTEGRATION_ID = 'i1';
const STATUS_URL = `${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/status`;
const CONFLICTS_URL = `${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/conflicts`;

function makeStatus(overrides: Partial<SyncStatus> = {}): SyncStatus {
  return {
    id: 's1',
    integrationId: INTEGRATION_ID,
    projectId: 'p1',
    provider: 'testrail',
    direction: 'bidirectional',
    conflictStrategy: 'last_write_wins',
    intervalMinutes: 15,
    isActive: true,
    health: 'active',
    lastSyncAt: '2026-09-25T10:00:00Z',
    lastSyncStatus: 'success',
    lastError: null,
    consecutiveFailures: 0,
    syncedCount: 12,
    pendingConflicts: 0,
    nextSyncAt: '2026-09-25T10:15:00Z',
    ...overrides,
  };
}

function makeConflict(overrides: Partial<SyncConflict> = {}): SyncConflict {
  return {
    id: 'c1',
    syncStateId: 's1',
    testCaseId: 'tc1',
    tmsTestId: '42',
    testgenVersion: { title: 'Wersja TestGEN' },
    tmsVersion: { title: 'Wersja TMS' },
    resolution: 'pending',
    resolvedAt: null,
    resolvedBy: null,
    createdAt: '2026-09-25T09:00:00Z',
    ...overrides,
  };
}

describe('SyncStatusComponent', () => {
  let component: SyncStatusComponent;
  let fixture: ComponentFixture<SyncStatusComponent>;
  let httpTesting: HttpTestingController;

  async function setup(status: SyncStatus | null = makeStatus(), conflicts: SyncConflict[] = []): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [SyncStatusComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: convertToParamMap({ integrationId: INTEGRATION_ID }) },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SyncStatusComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const statusReq = httpTesting.expectOne(STATUS_URL);
    if (status) {
      statusReq.flush(status);
      httpTesting.expectOne(CONFLICTS_URL).flush({ items: conflicts, total: conflicts.length });
    } else {
      statusReq.flush({ detail: 'brak' }, { status: 404, statusText: 'Not Found' });
    }
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('pokazuje stan i liczbę zsynchronizowanych przypadków', async () => {
    await setup();

    expect(component.status()?.syncedCount).toBe(12);
    expect(fixture.nativeElement.textContent).toContain('Włączona');
    expect(fixture.nativeElement.textContent).toContain('W obie strony');
  });

  it('brak konfiguracji nie jest błędem', async () => {
    await setup(null);

    // 404 znaczy „jeszcze nie skonfigurowano" — komunikat o awarii
    // wystraszyłby użytkownika bez powodu.
    expect(component.errorMessage()).toBeNull();
    expect(component.isConfigured()).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('nie została jeszcze skonfigurowana');
  });

  it('wyróżnia synchronizację wymagającą uwagi', async () => {
    await setup(makeStatus({ health: 'degraded', consecutiveFailures: 3, lastError: '401 Unauthorized' }));

    expect(component.isDegraded()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Wymaga uwagi');
    expect(fixture.nativeElement.textContent).toContain('401 Unauthorized');
  });

  it('formularz startuje z zapisanych ustawień', async () => {
    await setup(makeStatus({ direction: 'pull', intervalMinutes: 60, conflictStrategy: 'manual' }));

    expect(component.draftDirection).toBe('pull');
    expect(component.draftInterval).toBe(60);
    expect(component.draftStrategy).toBe('manual');
  });

  it('zapis ustawień nie włącza synchronizacji', async () => {
    await setup(makeStatus({ isActive: false }));
    component.draftDirection = 'push';
    component.draftInterval = 30;

    component.saveConfig();
    const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/config`);

    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({
      direction: 'push',
      intervalMinutes: 30,
      conflictStrategy: 'last_write_wins',
    });
    req.flush(makeStatus({ direction: 'push', intervalMinutes: 30, isActive: false }));
    fixture.detectChanges();

    expect(component.status()?.isActive).toBe(false);
    expect(component.infoMessage()).toContain('Zapisano');
  });

  it('przełącznik wyłącza działającą synchronizację', async () => {
    await setup(makeStatus({ isActive: true }));

    component.toggleActive();
    const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/deactivate`);
    req.flush(makeStatus({ isActive: false, nextSyncAt: null }));
    fixture.detectChanges();

    expect(component.status()?.isActive).toBe(false);
  });

  it('przełącznik włącza wyłączoną synchronizację', async () => {
    await setup(makeStatus({ isActive: false }));

    component.toggleActive();
    const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/activate`);
    req.flush(makeStatus({ isActive: true }));
    fixture.detectChanges();

    expect(component.status()?.isActive).toBe(true);
  });

  it('ręczne uruchomienie zgłasza zadanie', async () => {
    await setup();

    component.runNow();
    const req = httpTesting.expectOne(`${environment.apiUrl}/integrations/${INTEGRATION_ID}/sync/run`);
    req.flush({ syncStateId: 's1', taskId: 't9', status: 'accepted', statusUrl: '/api/v1/tasks/t9' });
    fixture.detectChanges();

    expect(component.infoMessage()).toContain('uruchomiona');
  });

  it('pokazuje obie wersje konfliktu', async () => {
    await setup(makeStatus(), [makeConflict()]);

    expect(component.pendingConflicts().length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('Wersja TestGEN');
    expect(fixture.nativeElement.textContent).toContain('Wersja TMS');
    expect(fixture.nativeElement.textContent).toContain('TMS #42');
  });

  it('rozstrzygnięcie konfliktu aktualizuje listę', async () => {
    await setup(makeStatus(), [makeConflict()]);

    component.resolve(makeConflict(), 'tms_wins');
    const req = httpTesting.expectOne(`${environment.apiUrl}/sync/conflicts/c1/resolve`);
    expect(req.request.body).toEqual({ resolution: 'tms_wins' });
    req.flush(makeConflict({ resolution: 'tms_wins', resolvedAt: '2026-09-25T11:00:00Z' }));
    fixture.detectChanges();

    expect(component.pendingConflicts().length).toBe(0);
    expect(fixture.nativeElement.textContent).toContain('Wygrał TMS');
  });

  it('rozstrzygnięty konflikt nie ma już przycisków decyzji', async () => {
    await setup(makeStatus(), [makeConflict({ resolution: 'testgen_wins' })]);

    const buttons: HTMLElement[] = Array.from(fixture.nativeElement.querySelectorAll('.conflict-actions button'));
    expect(buttons.length).toBe(0);
  });

  it('opisuje odstępy po polsku', async () => {
    await setup();

    expect(component.intervalLabel(5)).toBe('co 5 minut');
    expect(component.intervalLabel(60)).toBe('co 1 godzinę');
    expect(component.intervalLabel(240)).toBe('co 4 godziny');
    expect(component.intervalLabel(1440)).toBe('co 24 godziny');
  });

  it('nie oferuje odstępu krótszego niż dopuszcza backend', async () => {
    await setup();

    // Minimum 5 minut jest wymuszone po stronie API — lista wyboru nie może
    // proponować wartości, którą serwer i tak odrzuci.
    expect(Math.min(...component.intervals)).toBe(5);
  });
});
