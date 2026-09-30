import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { StatusCheckConfigComponent } from './status-check-config.component';
import { StatusCheckConfig } from '../../../core/services/integration.service';
import { environment } from '../../../../environments/environment';

const INTEGRATION_ID = 'i1';
const CONFIG_URL = `${environment.apiUrl}/integrations/${INTEGRATION_ID}/config`;

function makeConfig(overrides: Partial<StatusCheckConfig> = {}): StatusCheckConfig {
  return {
    integrationId: INTEGRATION_ID,
    severityThreshold: 'critical',
    postComment: true,
    failOnThreshold: true,
    statusContext: 'TestGEN / Code Analysis',
    ...overrides,
  };
}

describe('StatusCheckConfigComponent', () => {
  let component: StatusCheckConfigComponent;
  let fixture: ComponentFixture<StatusCheckConfigComponent>;
  let httpTesting: HttpTestingController;

  async function setup(config: StatusCheckConfig | null = makeConfig()): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [StatusCheckConfigComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(StatusCheckConfigComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('integrationId', INTEGRATION_ID);
    fixture.componentRef.setInput('repoName', 'acme/app');
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const req = httpTesting.expectOne(CONFIG_URL);
    if (config) {
      req.flush(config);
    } else {
      req.flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
    }
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje bieżące ustawienia integracji', async () => {
    await setup(makeConfig({ severityThreshold: 'high', postComment: false }));

    expect(component.threshold()).toBe('high');
    expect(component.postComment()).toBe(false);
    expect(component.isLoading()).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('acme/app');
  });

  it('pokazuje nazwę do wpisania w regułach ochrony gałęzi', async () => {
    await setup();

    expect(fixture.nativeElement.textContent).toContain('TestGEN / Code Analysis');
    expect(fixture.nativeElement.textContent).toContain('ochrony gałęzi');
  });

  it('oferuje trzy progi z opisem po polsku', async () => {
    await setup();

    const text = fixture.nativeElement.textContent as string;
    expect(component.thresholds.map((t) => t.value)).toEqual(['critical', 'high', 'medium']);
    expect(text).toContain('Krytyczny');
    expect(text).toContain('blokuje krytyczne i wysokie');
  });

  it('zapisuje wybrane ustawienia i zgłasza je rodzicowi', async () => {
    await setup();
    const saved = vi.fn();
    component.saved.subscribe(saved);

    component.threshold.set('medium');
    component.postComment.set(false);
    component.failOnThreshold.set(false);
    component.save();

    const put = httpTesting.expectOne(CONFIG_URL);
    expect(put.request.method).toBe('PUT');
    expect(put.request.body).toEqual({
      severityThreshold: 'medium',
      postComment: false,
      failOnThreshold: false,
    });
    put.flush(makeConfig({ severityThreshold: 'medium', postComment: false }));

    expect(saved).toHaveBeenCalled();
    expect(component.isSaving()).toBe(false);
  });

  it('pokazuje błąd zapisu z backendu', async () => {
    await setup();

    component.save();
    httpTesting
      .expectOne(CONFIG_URL)
      .flush({ detail: 'Nieprawidłowy próg' }, { status: 422, statusText: 'Unprocessable' });
    fixture.detectChanges();

    expect(component.errorMessage()).toBe('Nieprawidłowy próg');
    expect(component.isSaving()).toBe(false);
  });

  it('informuje, gdy ustawień nie da się wczytać', async () => {
    await setup(null);

    expect(component.errorMessage()).toContain('Nie udało się wczytać');
    expect(component.isLoading()).toBe(false);
  });

  it('anulowanie zgłasza zamknięcie bez zapisu', async () => {
    await setup();
    const closed = vi.fn();
    component.closed.subscribe(closed);

    const cancel = fixture.nativeElement.querySelector('.dialog-actions button') as HTMLButtonElement;
    cancel.click();

    expect(closed).toHaveBeenCalled();
    httpTesting.expectNone(CONFIG_URL);
  });
});
