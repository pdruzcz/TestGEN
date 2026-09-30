import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { IntegrationsComponent } from './integrations.component';

/**
 * Odnośniki do ekranów TMS na stronie „Integracje" projektu.
 *
 * Powód istnienia: ekrany konfiguracji TestRaila i Jira Xray/Zephyr
 * (Story 8.8/8.9) były zarejestrowane w routingu, ale nic do nich nie
 * prowadziło — komunikat błędu eksportu odsyłał do ustawień projektu,
 * w których ich nie było.
 */
describe('IntegrationsComponent — systemy zarządzania testami', () => {
  let fixture: ComponentFixture<IntegrationsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [IntegrationsComponent, NoopAnimationsModule],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ projectId: 'p1' }) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(IntegrationsComponent);
    fixture.detectChanges();
  });

  function hrefs(): string[] {
    const links: HTMLAnchorElement[] = Array.from(fixture.nativeElement.querySelectorAll('.tms-links a'));
    return links.map((link) => link.getAttribute('href') ?? '');
  }

  it('prowadzi do konfiguracji TestRaila', () => {
    expect(hrefs()).toContain('/projects/p1/integrations/testrail');
  });

  it('prowadzi do konfiguracji Jira Xray / Zephyr', () => {
    expect(hrefs()).toContain('/projects/p1/integrations/jira');
  });

  it('prowadzi do importu wymagań z Jiry', () => {
    expect(hrefs()).toContain('/projects/p1/import/jira');
  });
});
