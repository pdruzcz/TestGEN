import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { WebhookConfigComponent } from './webhook-config.component';
import { OutboundWebhook, WebhookDelivery } from '../../../core/services/webhook.service';
import { environment } from '../../../../environments/environment';

const BASE = `${environment.apiUrl}/webhooks`;
const URL = 'https://klient.example.com/hook';
const SECRET = 's'.repeat(32);

const ALL_EVENTS = ['analysis.completed', 'security.finding', 'gap.detected', 'export.ready', 'subscription.changed'];

function makeWebhook(overrides: Partial<OutboundWebhook> = {}): OutboundWebhook {
  return {
    id: 'w1',
    url: URL,
    description: null,
    events: ['analysis.completed'],
    isActive: true,
    lastDeliveryAt: null,
    lastDeliveryStatus: null,
    createdAt: '2026-09-01T10:00:00Z',
    ...overrides,
  };
}

function makeDelivery(overrides: Partial<WebhookDelivery> = {}): WebhookDelivery {
  return {
    id: 'd1',
    webhookId: 'w1',
    eventType: 'analysis.completed',
    status: 'delivered',
    attemptNumber: 1,
    responseStatus: 200,
    responseBody: 'ok',
    errorMessage: null,
    deliveredAt: '2026-09-02T08:00:05Z',
    nextRetryAt: null,
    createdAt: '2026-09-02T08:00:00Z',
    ...overrides,
  };
}

describe('WebhookConfigComponent', () => {
  let component: WebhookConfigComponent;
  let fixture: ComponentFixture<WebhookConfigComponent>;
  let httpTesting: HttpTestingController;

  async function setup(webhooks: OutboundWebhook[] = [makeWebhook()]): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [WebhookConfigComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(WebhookConfigComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    httpTesting.expectOne(BASE).flush({
      items: webhooks,
      total: webhooks.length,
      availableEvents: ALL_EVENTS,
    });
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje webhooki i katalog zdarzeń', async () => {
    await setup();

    expect(component.webhooks().length).toBe(1);
    expect(component.availableEvents()).toEqual(ALL_EVENTS);
    expect(fixture.nativeElement.textContent).toContain(URL);
  });

  it('pokazuje pusty stan', async () => {
    await setup([]);

    expect(fixture.nativeElement.textContent).toContain('Nie masz jeszcze żadnego webhooka');
  });

  it('tłumaczy identyfikatory zdarzeń na polskie etykiety', async () => {
    await setup([makeWebhook({ events: ['security.finding', 'export.ready'] })]);

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Podatność krytyczna lub wysoka');
    expect(text).toContain('Raport gotowy');
  });

  it('pokazuje status ostatniej dostawy', async () => {
    await setup([makeWebhook({ lastDeliveryStatus: 'failed', lastDeliveryAt: '2026-09-02T08:00:00Z' })]);

    expect(fixture.nativeElement.textContent).toContain('Nieudany');
  });

  describe('formularz', () => {
    it('wymaga https, sekretu i co najmniej jednego zdarzenia', async () => {
      await setup([]);
      component.openCreateForm();

      expect(component.isFormValid()).toBe(false);

      component.formUrl.set('http://klient.example.com/hook');
      component.formSecret.set(SECRET);
      component.toggleEvent('gap.detected');
      expect(component.isFormValid()).toBe(false); // http odpada

      component.formUrl.set(URL);
      expect(component.isFormValid()).toBe(true);

      component.formSecret.set('krótki');
      expect(component.isFormValid()).toBe(false); // sekret za krótki

      component.formSecret.set(SECRET);
      component.toggleEvent('gap.detected');
      expect(component.isFormValid()).toBe(false); // brak zdarzeń
    });

    it('wysyła POST przy tworzeniu i odświeża listę', async () => {
      await setup([]);

      component.openCreateForm();
      component.formUrl.set(URL);
      component.formSecret.set(SECRET);
      component.formDescription.set('Kanał dyżuru');
      component.toggleEvent('analysis.completed');
      component.toggleEvent('security.finding');
      component.submit();

      const post = httpTesting.expectOne((r) => r.url === BASE && r.method === 'POST');
      expect(post.request.body).toEqual({
        url: URL,
        secret: SECRET,
        events: ['analysis.completed', 'security.finding'],
        description: 'Kanał dyżuru',
      });
      post.flush(makeWebhook());

      httpTesting.expectOne(BASE).flush({ items: [makeWebhook()], total: 1, availableEvents: ALL_EVENTS });
      fixture.detectChanges();

      expect(component.isFormOpen()).toBe(false);
      expect(component.infoMessage()).toContain('dodany');
    });

    it('przy edycji pomija sekret, gdy pole zostało puste', async () => {
      await setup();

      component.openEditForm(makeWebhook({ events: ['gap.detected'] }));
      expect(component.formSecret()).toBe('');
      expect(component.isFormValid()).toBe(true); // sekret nie jest wymagany

      component.submit();

      const put = httpTesting.expectOne((r) => r.url === `${BASE}/w1` && r.method === 'PUT');
      expect(put.request.body.secret).toBeUndefined();
      expect(put.request.body.events).toEqual(['gap.detected']);
      put.flush(makeWebhook());

      httpTesting.expectOne(BASE).flush({ items: [makeWebhook()], total: 1, availableEvents: ALL_EVENTS });
      fixture.detectChanges();

      expect(component.infoMessage()).toContain('zaktualizowany');
    });

    it('przy edycji wysyła sekret, gdy został podany', async () => {
      await setup();

      component.openEditForm(makeWebhook());
      component.formSecret.set(SECRET);
      component.submit();

      const put = httpTesting.expectOne((r) => r.url === `${BASE}/w1` && r.method === 'PUT');
      expect(put.request.body.secret).toBe(SECRET);
      put.flush(makeWebhook());
      httpTesting.expectOne(BASE).flush({ items: [], total: 0, availableEvents: ALL_EVENTS });
    });

    it('pokazuje błąd z backendu', async () => {
      await setup([]);

      component.openCreateForm();
      component.formUrl.set(URL);
      component.formSecret.set(SECRET);
      component.toggleEvent('gap.detected');
      component.submit();

      httpTesting
        .expectOne((r) => r.url === BASE && r.method === 'POST')
        .flush({ detail: 'Sekret musi mieć co najmniej 16 znaków' }, { status: 422, statusText: 'Unprocessable' });
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Sekret musi mieć co najmniej 16 znaków');
      expect(component.isSubmitting()).toBe(false);
    });
  });

  describe('akcje na liście', () => {
    it('test połączenia pokazuje wynik przy webhooku', async () => {
      await setup();

      component.testWebhook(makeWebhook());
      httpTesting.expectOne(`${BASE}/w1/test`).flush({
        success: true,
        statusCode: 200,
        message: 'Endpoint odpowiedział poprawnie',
        responseBody: null,
      });
      fixture.detectChanges();

      expect(component.testResultFor('w1')?.success).toBe(true);
      expect(component.testResultFor('inny')).toBeNull();
      expect(fixture.nativeElement.textContent).toContain('Endpoint odpowiedział poprawnie');
    });

    it('test połączenia pokazuje niepowodzenie', async () => {
      await setup();

      component.testWebhook(makeWebhook());
      httpTesting.expectOne(`${BASE}/w1/test`).flush({
        success: false,
        statusCode: null,
        message: 'Przekroczono limit 10 s',
        responseBody: null,
      });
      fixture.detectChanges();

      expect(component.testResultFor('w1')?.success).toBe(false);
      expect(fixture.nativeElement.textContent).toContain('Przekroczono limit 10 s');
    });

    it('przełącza aktywność webhooka', async () => {
      await setup();

      component.toggleActive(makeWebhook({ isActive: true }));

      const put = httpTesting.expectOne((r) => r.url === `${BASE}/w1` && r.method === 'PUT');
      expect(put.request.body).toEqual({ isActive: false });
      put.flush(makeWebhook({ isActive: false }));

      httpTesting.expectOne(BASE).flush({ items: [], total: 0, availableEvents: ALL_EVENTS });
    });

    it('usunięcie wymaga potwierdzenia', async () => {
      await setup();

      component.askRemove('w1');
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Usunąć webhook?');
      httpTesting.expectNone(`${BASE}/w1`);

      component.confirmRemove();
      const del = httpTesting.expectOne(`${BASE}/w1`);
      expect(del.request.method).toBe('DELETE');
      del.flush(null);

      httpTesting.expectOne(BASE).flush({ items: [], total: 0, availableEvents: ALL_EVENTS });
      fixture.detectChanges();

      expect(component.infoMessage()).toContain('usunięty');
    });

    it('anulowanie usunięcia nie wysyła żądania', async () => {
      await setup();

      component.askRemove('w1');
      component.cancelRemove();
      fixture.detectChanges();

      expect(component.pendingRemovalId()).toBeNull();
      httpTesting.expectNone(`${BASE}/w1`);
    });
  });

  describe('historia dostaw', () => {
    it('wczytuje dostawy webhooka', async () => {
      await setup();

      component.showDeliveries('w1');
      const req = httpTesting.expectOne((r) => r.url === `${BASE}/w1/deliveries`);
      expect(req.request.params.get('limit')).toBe('100');
      req.flush({ items: [makeDelivery()], total: 1 });
      fixture.detectChanges();

      expect(component.deliveries().length).toBe(1);
      expect(fixture.nativeElement.textContent).toContain('Dostarczony');
    });

    it('przekazuje filtry statusu i zdarzenia', async () => {
      await setup();

      component.showDeliveries('w1');
      httpTesting.expectOne((r) => r.url === `${BASE}/w1/deliveries`).flush({ items: [], total: 0 });

      component.deliveryStatusFilter.set('failed');
      component.deliveryEventFilter.set('gap.detected');
      component.applyDeliveryFilters();

      const req = httpTesting.expectOne((r) => r.url === `${BASE}/w1/deliveries`);
      expect(req.request.params.get('status')).toBe('failed');
      expect(req.request.params.get('event_type')).toBe('gap.detected');
      req.flush({ items: [], total: 0 });
      fixture.detectChanges();

      expect(fixture.nativeElement.textContent).toContain('Brak dostaw spełniających kryteria');
    });

    it('pokazuje numer próby i termin ponowienia', async () => {
      await setup();

      component.showDeliveries('w1');
      httpTesting
        .expectOne((r) => r.url === `${BASE}/w1/deliveries`)
        .flush({
          items: [
            makeDelivery({
              status: 'pending',
              attemptNumber: 3,
              responseStatus: 503,
              errorMessage: 'Service Unavailable',
              nextRetryAt: '2026-09-02T08:30:00Z',
            }),
          ],
          total: 1,
        });
      fixture.detectChanges();

      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Oczekuje');
      expect(text).toContain('503');
      expect(text).toContain('Ponowienie:');
    });

    it('zamknięcie historii czyści filtry', async () => {
      await setup();

      component.showDeliveries('w1');
      httpTesting.expectOne((r) => r.url === `${BASE}/w1/deliveries`).flush({ items: [], total: 0 });

      component.deliveryStatusFilter.set('failed');
      component.closeDeliveries();

      expect(component.deliveriesFor()).toBeNull();
      expect(component.deliveryStatusFilter()).toBe('');
      expect(component.deliveries()).toEqual([]);
    });
  });
});
