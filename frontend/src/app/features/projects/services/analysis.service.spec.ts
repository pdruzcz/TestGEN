import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AnalysisConfig, AnalysisService, DEFAULT_ANALYSIS_CONFIG } from './analysis.service';
import { environment } from '../../../../environments/environment';

describe('AnalysisService (Story 6.3)', () => {
  let service: AnalysisService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalysisService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it('POSTs config with modules + test_framework', () => {
    const cfg: AnalysisConfig = {
      modules: ['code_analysis', 'security'],
      testFramework: 'pytest',
    };
    service.startProjectAnalysis('proj-1', cfg).subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/projects/proj-1/analyze`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      modules: cfg.modules,
      test_framework: 'pytest',
    });
    req.flush({ taskId: 'task-1' });
  });

  it('does NOT send engine_mode — engine is config-only (Story 6.3-zakończenie)', () => {
    const cfg: AnalysisConfig = {
      modules: ['code_analysis'],
      testFramework: null,
    };
    service.startProjectAnalysis('proj-2', cfg).subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/projects/proj-2/analyze`);
    expect(req.request.body).toEqual({ modules: cfg.modules });
    expect(req.request.body).not.toHaveProperty('engine_mode');
    expect(req.request.body).not.toHaveProperty('llm_model');
    expect(req.request.body).not.toHaveProperty('temperature');
    expect(req.request.body).not.toHaveProperty('max_tokens');
    req.flush({ taskId: 'task-2' });
  });

  it('includes test_scopes when provided (Story 1.53)', () => {
    const cfg: AnalysisConfig = {
      modules: ['code_analysis'],
      testFramework: null,
      testScopes: ['database'],
    };
    service.startProjectAnalysis('proj-3', cfg).subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/projects/proj-3/analyze`);
    expect(req.request.body).toEqual({
      modules: cfg.modules,
      test_scopes: ['database'],
    });
    req.flush({ taskId: 'task-3' });
  });

  it('falls back to DEFAULT_ANALYSIS_CONFIG when no config passed', () => {
    service.startProjectAnalysis('proj-4').subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/projects/proj-4/analyze`);
    expect(req.request.body.modules).toEqual(DEFAULT_ANALYSIS_CONFIG.modules);
    expect(req.request.body).not.toHaveProperty('engine_mode');
    req.flush({ taskId: 'task-4' });
  });

  it('cancelTask POSTs to /tasks/:id/cancel', () => {
    service.cancelTask('task-9').subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/tasks/task-9/cancel`);
    expect(req.request.method).toBe('POST');
    req.flush({ taskId: 'task-9', status: 'cancelled' });
  });

  it('getTaskStatus GETs /tasks/:id', () => {
    service.getTaskStatus('task-1').subscribe();

    const req = httpTesting.expectOne(`${environment.apiUrl}/tasks/task-1`);
    expect(req.request.method).toBe('GET');
    req.flush({
      taskId: 'task-1',
      status: 'running',
      progress: 42,
      currentStep: 'analysis',
      resultUrl: null,
      error: null,
    });
  });
});
