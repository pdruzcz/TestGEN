import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { ApiKeysComponent } from './api-keys.component';
import { ApiKeyItem, ApiKeyListResponse } from '../../../core/services/api-key.service';
import { environment } from '../../../../environments/environment';

const API_URL = `${environment.apiUrl}/api-keys`;

function makeKey(overrides: Partial<ApiKeyItem> = {}): ApiKeyItem {
  return {
    id: 'k1',
    name: 'Jenkins — produkcja',
    scope: 'read_only',
    keyPrefix: 'tgn_a1b2',
    status: 'active',
    expiresAt: null,
    lastUsedAt: null,
    revokedAt: null,
    createdAt: '2026-09-01T10:00:00Z',
    ...overrides,
  };
}

describe('ApiKeysComponent', () => {
  let component: ApiKeysComponent;
  let fixture: ComponentFixture<ApiKeysComponent>;
  let httpTesting: HttpTestingController;

  async function setup(items: ApiKeyItem[] = [makeKey()]): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [ApiKeysComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(ApiKeysComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    const req = httpTesting.expectOne(API_URL);
    expect(req.request.method).toBe('GET');
    req.flush({ items, total: items.length } as ApiKeyListResponse);
    fixture.detectChanges();
  }

  afterEach(() => {
    httpTesting?.verify();
  });

  it('wczytuje listę kluczy przy inicjalizacji', async () => {
    await setup([makeKey({ name: 'CI' })]);

    expect(component.keys().length).toBe(1);
    expect(component.keys()[0].name).toBe('CI');
    expect(fixture.nativeElement.textContent).toContain('CI');
  });

  it('pokazuje pusty stan, gdy nie ma kluczy', async () => {
    await setup([]);

    expect(fixture.nativeElement.textContent).toContain('Nie masz jeszcze żadnych kluczy API');
  });

  it('renderuje tylko prefiks klucza, nigdy pełną wartość', async () => {
    await setup([makeKey({ keyPrefix: 'tgn_9f8e' })]);

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('tgn_9f8e');
    expect(text).not.toContain('tgn_9f8e1234567890');
  });

  it('tłumaczy status i zakres na polskie etykiety', async () => {
    await setup([
      makeKey({ id: 'k1', status: 'revoked', scope: 'full_access' }),
      makeKey({ id: 'k2', status: 'expired' }),
    ]);

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Odwołany');
    expect(text).toContain('Wygasły');
    expect(text).toContain('Pełny dostęp');
  });

  it('ukrywa akcję odwołania dla klucza już odwołanego', async () => {
    await setup([makeKey({ status: 'revoked' })]);

    const revokeButtons = fixture.nativeElement.querySelectorAll('.actions .icon-btn');
    expect(revokeButtons.length).toBe(0);
  });

  describe('tworzenie klucza', () => {
    it('wysyła POST z nazwą i zakresem, po czym odświeża listę', async () => {
      await setup([]);

      component.openDialog();
      component.formName.set('  Jenkins  ');
      component.formScope.set('full_access');
      component.submit();

      const post = httpTesting.expectOne(API_URL);
      expect(post.request.method).toBe('POST');
      expect(post.request.body.name).toBe('Jenkins'); // nazwa przycięta
      expect(post.request.body.scope).toBe('full_access');
      expect(post.request.body.expiresAt).toBeNull();

      post.flush({ key: 'tgn_' + 'a'.repeat(64), apiKey: makeKey() });
      httpTesting.expectOne(API_URL).flush({ items: [makeKey()], total: 1 });
      fixture.detectChanges();

      expect(component.isDialogOpen()).toBe(false);
    });

    it('pokazuje klucz jeden raz z ostrzeżeniem', async () => {
      await setup([]);
      const rawKey = 'tgn_' + 'b'.repeat(64);

      component.openDialog();
      component.formName.set('CI');
      component.submit();
      httpTesting.expectOne(API_URL).flush({ key: rawKey, apiKey: makeKey() });
      httpTesting.expectOne(API_URL).flush({ items: [makeKey()], total: 1 });
      fixture.detectChanges();

      expect(component.createdKey()).toBe(rawKey);
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain(rawKey);
      expect(text).toContain('Skopiuj klucz teraz');

      component.dismissCreatedKey();
      fixture.detectChanges();

      expect(component.createdKey()).toBeNull();
      expect(fixture.nativeElement.textContent).not.toContain(rawKey);
    });

    it('zamienia wybraną datę na ISO w payloadzie', async () => {
      await setup([]);

      component.openDialog();
      component.formName.set('CI');
      component.formExpiresAt.set('2027-01-15');
      component.submit();

      const post = httpTesting.expectOne(API_URL);
      expect(post.request.body.expiresAt).toContain('2027-01-15');

      post.flush({ key: 'tgn_' + 'c'.repeat(64), apiKey: makeKey() });
      httpTesting.expectOne(API_URL).flush({ items: [], total: 0 });
    });

    it('blokuje wysyłkę przy pustej nazwie', async () => {
      await setup([]);

      component.openDialog();
      component.formName.set('   ');

      expect(component.isFormValid()).toBe(false);
      component.submit();
      httpTesting.expectNone(API_URL); // brak requestu
    });

    it('pokazuje komunikat błędu z backendu', async () => {
      await setup([]);

      component.openDialog();
      component.formName.set('CI');
      component.submit();
      httpTesting
        .expectOne(API_URL)
        .flush(
          { detail: 'Data wygaśnięcia nie może przekraczać 2 lat' },
          { status: 422, statusText: 'Unprocessable Entity' },
        );
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Data wygaśnięcia nie może przekraczać 2 lat');
      expect(component.isSubmitting()).toBe(false);
    });

    it('ogranicza datepicker do 2 lat w przód', async () => {
      await setup([]);

      const max = new Date(component.maxExpiryDate());
      const limit = new Date();
      limit.setDate(limit.getDate() + 731);

      expect(max.getTime()).toBeLessThan(limit.getTime());
      expect(new Date(component.minExpiryDate()).getTime()).toBeGreaterThan(Date.now() - 1000);
    });

    it('kopiuje klucz do schowka', async () => {
      await setup([]);
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      component.openDialog();
      component.formName.set('CI');
      component.submit();
      const rawKey = 'tgn_' + 'd'.repeat(64);
      httpTesting.expectOne(API_URL).flush({ key: rawKey, apiKey: makeKey() });
      httpTesting.expectOne(API_URL).flush({ items: [], total: 0 });

      component.copyKey();
      await Promise.resolve();

      expect(writeText).toHaveBeenCalledWith(rawKey);
      expect(component.isKeyCopied()).toBe(true);
    });
  });

  describe('odwoływanie klucza', () => {
    it('wymaga potwierdzenia przed wysłaniem DELETE', async () => {
      await setup([makeKey({ id: 'k9' })]);

      component.askRevoke('k9');
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Odwołać klucz API?');
      httpTesting.expectNone(`${API_URL}/k9`);

      component.confirmRevoke();
      const del = httpTesting.expectOne(`${API_URL}/k9`);
      expect(del.request.method).toBe('DELETE');
      del.flush(makeKey({ id: 'k9', status: 'revoked' }));

      httpTesting.expectOne(API_URL).flush({ items: [makeKey({ id: 'k9', status: 'revoked' })], total: 1 });
      fixture.detectChanges();

      expect(component.pendingRevokeId()).toBeNull();
      expect(component.keys()[0].status).toBe('revoked');
    });

    it('anulowanie zamyka okno bez żądania', async () => {
      await setup([makeKey({ id: 'k9' })]);

      component.askRevoke('k9');
      component.cancelRevoke();
      fixture.detectChanges();

      expect(component.pendingRevokeId()).toBeNull();
      httpTesting.expectNone(`${API_URL}/k9`);
    });

    it('pokazuje błąd, gdy odwołanie się nie powiedzie', async () => {
      await setup([makeKey({ id: 'k9' })]);

      component.askRevoke('k9');
      component.confirmRevoke();
      httpTesting.expectOne(`${API_URL}/k9`).flush({ detail: 'boom' }, { status: 500, statusText: 'Server Error' });
      fixture.detectChanges();

      expect(component.errorMessage()).toBe('Nie udało się odwołać klucza API.');
    });
  });
});
